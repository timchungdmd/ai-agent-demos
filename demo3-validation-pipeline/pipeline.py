#!/usr/bin/env python3
"""
Demo 3 — Validation Pipeline. Personal pipeline project, not client work.

Repackages the multi-agent pipeline pattern (scripted validator gates,
fresh blind re-check, adjudication, defect log, fix, retest) and applies
it to demo agent outputs: two drafts answering a Demo 2 support question
(Harbor Outdoor Gear, fictional). One draft is clean; the other carries
one SEEDED defect, labelled as seeded in the input file — a support
answer that cites the wrong return window (60 days instead of the
documented 30 days).

Pipeline: draft -> scripted validator gates -> blind re-check (a
separate reviewer that never sees the validator verdict) -> adjudication
-> defect log -> fix -> retest.

Honest scope note, same as Demos 1-2: the validator and the blind
re-check are deterministic scripted checks against the fictional docs,
not a different LLM model. The gates, the separation of verdicts, the
adjudication rule, and the defect-log discipline are what is
demonstrated. Do not claim a different-model blind review or a measured
defect rate from this demo alone until that step is actually added
and measured.

Usage:
  python3 pipeline.py
  python3 -m unittest test_pipeline.py -v
"""

import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DOCS_JSON = BASE.parent / "demo2-support-rag" / "docs_fictional.json"
DRAFTS_JSON = BASE / "drafts_fictional.json"
REPORT_JSON = BASE / "outputs" / "validation_report.json"
DEFECT_CSV = BASE / "outputs" / "defect_log.csv"
BEFORE_AFTER_MD = BASE / "outputs" / "before_after.md"

REQUIRED_FIELDS = ["draft_id", "question", "answer_text", "cited_doc_id",
                   "confidence", "routing"]


def load_docs():
    with open(DOCS_JSON, encoding="utf-8") as f:
        return {d["doc_id"]: d for d in json.load(f)}


def load_drafts():
    with open(DRAFTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def numbers_in(text):
    return re.findall(r"\d+", strip_citation(text))


def strip_citation(text):
    """Remove a leading [Dxx Title] citation prefix so its doc number
    is not mistaken for a policy number in the answer body."""
    return re.sub(r"^\[[^\]]+\]\s*", "", text)


def validator_gates(draft, docs, seen_answer_texts):
    """Scripted gates. Returns a list of {gate, passed, evidence}."""
    results = []

    # G1: required fields present.
    missing = [f for f in REQUIRED_FIELDS if not draft.get(f)]
    results.append({"gate": "G1_required_fields_present",
                    "passed": not missing,
                    "evidence": f"missing={missing}" if missing else "all present"})

    # G2: citation present for a policy claim.
    cited = draft.get("cited_doc_id", "")
    results.append({"gate": "G2_citation_present",
                    "passed": bool(cited) and cited in docs,
                    "evidence": f"cited_doc_id={cited}"})

    # G3: no invented policy/date/number — every number in the answer
    # must appear in the cited doc's text.
    doc_text = docs[cited]["content"] if cited in docs else ""
    invented = [n for n in numbers_in(draft.get("answer_text", ""))
                if n not in numbers_in(doc_text)]
    results.append({"gate": "G3_no_invented_numbers",
                    "passed": not invented,
                    "evidence": f"invented_numbers={invented}" if invented
                    else "all numbers appear in cited doc"})

    # G4: confidence/threshold field consistent with the routing decision.
    consistent = (draft.get("confidence") == "high" and draft.get("routing") == "answer") \
        or (draft.get("confidence") != "high" and draft.get("routing") != "answer")
    results.append({"gate": "G4_confidence_matches_routing",
                    "passed": consistent,
                    "evidence": f"confidence={draft.get('confidence')} routing={draft.get('routing')}"})

    # G5: no duplicate of a previous output without a reason.
    dup = draft.get("answer_text") in seen_answer_texts
    results.append({"gate": "G5_no_unexplained_duplicate",
                    "passed": not dup,
                    "evidence": "duplicate of an earlier draft" if dup else "no duplicate"})

    return results


def blind_recheck(draft, docs):
    """Independent re-check. It receives only the draft and the docs —
    never the validator verdict — and re-derives the answer's numbers
    from the cited doc. Returns {verdict, evidence}."""
    cited = draft.get("cited_doc_id", "")
    if cited not in docs:
        return {"verdict": "fail",
                "evidence": f"cited doc {cited} not found"}
    doc_numbers = set(numbers_in(docs[cited]["content"]))
    answer_numbers = numbers_in(draft.get("answer_text", ""))
    bad = [n for n in answer_numbers if n not in doc_numbers]
    if bad:
        return {"verdict": "fail",
                "evidence": f"answer numbers {bad} not in cited doc {cited}"}
    return {"verdict": "pass",
            "evidence": f"all answer numbers {answer_numbers} found in {cited}"}


def adjudicate(validator_passed, blind_verdict):
    """If the two verdicts agree, that verdict stands. If they disagree,
    a neutral third check decides: is the answer's quoted sentence
    verbatim in the cited doc? Both the disagreement and the decision
    are returned so they can be logged."""
    if validator_passed == (blind_verdict == "pass"):
        return {"decision": "pass" if validator_passed else "fail",
                "method": "validator_and_blind_agree",
                "disagreement": False}
    return {"decision": "adjudication_needed",
            "method": "verdicts_disagree_third_check_required",
            "disagreement": True}


def third_check_verbatim(draft, docs):
    """Neutral third check: strip the citation prefix and test whether
    the remaining sentence appears verbatim in the cited doc."""
    cited = draft.get("cited_doc_id", "")
    text = re.sub(r"^\[[^\]]+\]\s*", "", draft.get("answer_text", ""))
    if cited in docs and text.strip() in docs[cited]["content"]:
        return "pass"
    return "fail"


def fix_seeded_defect(draft, docs):
    """Fix only the seeded defect: replace an invented number with the
    documented number from the cited doc. Returns the fixed draft."""
    fixed = dict(draft)
    cited = draft.get("cited_doc_id", "")
    doc_numbers = numbers_in(docs[cited]["content"]) if cited in docs else []
    answer = draft.get("answer_text", "")
    for bad in numbers_in(answer):
        if bad not in doc_numbers and doc_numbers:
            # The return-window number is the first number in the doc text.
            answer = answer.replace(bad, doc_numbers[0], 1)
    fixed["answer_text"] = answer
    fixed["draft_id"] = draft["draft_id"] + "-FIXED"
    return fixed


def run(drafts_json=DRAFTS_JSON, report_json=REPORT_JSON,
        defect_csv=DEFECT_CSV, before_after_md=BEFORE_AFTER_MD):
    docs = load_docs()
    drafts = load_drafts()
    seen = set()
    report = []
    defects = []
    fixed_drafts = []

    for draft in drafts:
        gates = validator_gates(draft, docs, seen)
        seen.add(draft.get("answer_text", ""))
        validator_passed = all(g["passed"] for g in gates)
        blind = blind_recheck(draft, docs)
        adj = adjudicate(validator_passed, blind["verdict"])
        if adj["disagreement"]:
            decision = third_check_verbatim(draft, docs)
            adj = {"decision": decision,
                   "method": "third_check_verbatim_sentence",
                   "disagreement": True}
        else:
            decision = adj["decision"]

        entry = {"draft_id": draft["draft_id"],
                 "seeded_defect": draft.get("seeded_defect", False),
                 "validator_passed": validator_passed,
                 "gates": gates,
                 "blind_verdict": blind["verdict"],
                 "blind_evidence": blind["evidence"],
                 "adjudication": adj,
                 "final_decision": decision}
        report.append(entry)

        if decision == "fail":
            failed = [g for g in gates if not g["passed"]]
            fixed = fix_seeded_defect(draft, docs)
            fixed_gates = validator_gates(fixed, docs, set())
            fixed_blind = blind_recheck(fixed, docs)
            retest_passed = all(g["passed"] for g in fixed_gates) \
                and fixed_blind["verdict"] == "pass"
            defects.append({
                "id": "DEF-001",
                "severity": "High",
                "finding": "Seeded defect: answer cites a 60-day return window; "
                            "the cited doc (D02 Returns) documents 30 days.",
                "evidence": "validator: " + "; ".join(
                    f"{g['gate']}: {g['evidence']}" for g in failed)
                    + f" | blind re-check: {blind['evidence']}",
                "fix_applied": "Replaced 60 with the documented 30 from D02.",
                "retest_result": "PASS" if retest_passed else "FAIL",
                "gate_added": "None new — G3 (no invented numbers) already "
                              "catches this; the defect proves the gate fires.",
            })
            fixed_drafts.append({"original": draft, "fixed": fixed,
                                 "retest_passed": retest_passed})

    report_json.parent.mkdir(parents=True, exist_ok=True)
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(defect_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "severity", "finding", "evidence", "fix_applied",
            "retest_result", "gate_added"])
        writer.writeheader()
        writer.writerows(defects)

    with open(before_after_md, "w", encoding="utf-8") as f:
        f.write("# Before / after — seeded defect\n\n")
        for pair in fixed_drafts:
            f.write(f"## {pair['original']['draft_id']}\n\n")
            f.write(f"Before: {pair['original']['answer_text']}\n\n")
            f.write(f"After: {pair['fixed']['answer_text']}\n\n")
            f.write(f"What changed and why: the 60-day window was invented "
                    f"— D02 documents 30 days — so the fix restores the "
                    f"documented figure. Retest: "
                    f"{'PASS' if pair['retest_passed'] else 'FAIL'}.\n\n")

    print(f"Validated {len(report)} drafts: "
          f"{sum(1 for r in report if r['final_decision'] == 'pass')} pass, "
          f"{sum(1 for r in report if r['final_decision'] == 'fail')} fail.")
    print(f"Defects logged: {len(defects)} (all labelled seeded).")
    print(f"Report: {report_json}")
    print(f"Defect log: {defect_csv}")
    print(f"Before/after: {before_after_md}")
    return report, defects


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
