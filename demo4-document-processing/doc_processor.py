#!/usr/bin/env python3
"""
Demo 4 — Document Processing. Demo — fictional data.

Pipeline: mock document -> extract fields (supplied here as the
extracted JSON, so validation is fully reproducible) -> validate
in code -> route Clean to the sheet, or Exception to a human queue.

Validation rules (code, not a prompt hope):
  V1  total == subtotal + tax, within $0.01
  V2  line items sum to subtotal, within $0.01
  V3  date is a valid YYYY-MM-DD date
  V4  PO number present and not a duplicate of an earlier document
  V5  no extracted field has confidence below 0.70

Exceptions are NEVER auto-corrected. The extracted values stay
exactly as extracted; the log names the failing field and reason,
and a human decides what to do.

In a production version, PDF -> text extraction and LLM/structured
extraction would produce the JSON this demo starts from. That
extraction step is not built here; do not list PDF extraction or
LLM extraction as built experience from this demo alone.

Usage:
  python3 doc_processor.py
  python3 -m unittest test_doc_processor.py -v
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
INPUT_JSON = BASE / "documents_fictional.json"
OUTPUT_CSV = BASE / "outputs" / "extraction_log.csv"
SUMMARY_JSON = BASE / "outputs" / "summary.json"
BEFORE_AFTER_MD = BASE / "outputs" / "before_after.md"

TOLERANCE = 0.01
MIN_CONFIDENCE = 0.70


def validate_document(doc, seen_pos):
    """Validate one document. Returns (failing_field, reason) or (None, None)."""
    line_sum = round(sum(item["amount"] for item in doc["line_items"]), 2)
    expected_total = round(doc["subtotal"] + doc["tax"], 2)

    # V3: valid date.
    try:
        datetime.strptime(doc["date"], "%Y-%m-%d")
    except (ValueError, TypeError):
        return "date", f"invalid_date:{doc.get('date')}"

    # V4: PO present.
    if not doc.get("po_number"):
        return "po_number", "po_missing"
    # V4: PO not a duplicate.
    if doc["po_number"] in seen_pos:
        return "po_number", f"duplicate_po:{doc['po_number']}"

    # V2: line items sum to subtotal.
    if abs(line_sum - doc["subtotal"]) > TOLERANCE:
        return "subtotal", (
            f"line_items_sum_mismatch:items_sum={line_sum:.2f} "
            f"subtotal={doc['subtotal']:.2f}"
        )

    # V1: total = subtotal + tax.
    if abs(doc["total"] - expected_total) > TOLERANCE:
        return "total", (
            f"total_mismatch:expected={expected_total:.2f} "
            f"stated={doc['total']:.2f}"
        )

    # V5: low-confidence field.
    for field, conf in doc.get("confidence", {}).items():
        if conf < MIN_CONFIDENCE:
            return field, f"low_confidence:{field}={conf:.2f}"

    return None, None


def run(input_json=INPUT_JSON, output_csv=OUTPUT_CSV,
        summary_json=SUMMARY_JSON, before_after_md=BEFORE_AFTER_MD):
    with open(input_json, encoding="utf-8") as f:
        docs = json.load(f)

    seen_pos = set()
    results = []
    for doc in docs:
        failing_field, reason = validate_document(doc, seen_pos)
        if doc.get("po_number"):
            seen_pos.add(doc["po_number"])
        line_sum = round(sum(item["amount"] for item in doc["line_items"]), 2)
        min_conf = min(doc.get("confidence", {}).values()) if doc.get("confidence") else 0.0
        status = "Exception" if failing_field else "Clean"
        results.append({
            "doc_id": doc["doc_id"],
            "vendor": doc["vendor"],
            "date": doc["date"],
            "po_number": doc["po_number"],
            "subtotal": f"{doc['subtotal']:.2f}",
            "tax": f"{doc['tax']:.2f}",
            "total": f"{doc['total']:.2f}",
            "line_items_sum": f"{line_sum:.2f}",
            "min_confidence": f"{min_conf:.2f}",
            "status": status,
            "destination": "Human exception queue" if status == "Exception" else "Sheet (Clean)",
            "failing_field": failing_field or "",
            "reason": reason or "all_validations_pass",
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = {
        "total_documents": len(results),
        "counts_by_status": counts,
        "clean_ids": [r["doc_id"] for r in results if r["status"] == "Clean"],
        "exception_ids": [r["doc_id"] for r in results if r["status"] == "Exception"],
        "note": "No accuracy percentage is claimed beyond this 10-document test set.",
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    lines = [
        "# Before / after — Demo 4",
        "",
        "Raw extraction is never auto-corrected. Clean rows flow to the sheet",
        "as extracted. Exception rows go to the human queue unchanged,",
        "with the failing field and reason named.",
        "",
        "| doc_id | total (as extracted) | status | failing_field | reason |",
        "|--------|----------------------|--------|---------------|--------|",
    ]
    for r in results:
        lines.append(
            f"| {r['doc_id']} | {r['total']} | {r['status']} | "
            f"{r['failing_field'] or '-'} | {r['reason']} |"
        )
    lines.append("")
    lines.append("Exception queue: DOC-09 (total) and DOC-10 (po_number).")
    with open(before_after_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Processed {len(results)} fictional documents.")
    print(f"Counts: {counts}")
    print(f"Extraction log: {output_csv}")
    print(f"Summary: {summary_json}")
    return results, summary


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
