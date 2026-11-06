#!/usr/bin/env python3
"""Acceptance tests for Demo 4. Run: python3 -m unittest test_doc_processor.py -v"""
import copy
import csv
import json
import unittest
from pathlib import Path

from doc_processor import run, validate_document, INPUT_JSON, OUTPUT_CSV

BASE = Path(__file__).resolve().parent


class TestDocProcessor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results, cls.summary = run()
        with open(INPUT_JSON, encoding="utf-8") as f:
            cls.docs = json.load(f)

    def test_all_documents_logged(self):
        self.assertEqual(len(self.results), 10)
        self.assertEqual(len(self.docs), 10)
        self.assertEqual(
            [r["doc_id"] for r in self.results],
            [d["doc_id"] for d in self.docs],
        )

    def test_expected_distribution(self):
        # Spec target: 8 Clean, 2 Exception.
        self.assertEqual(self.summary["counts_by_status"].get("Clean"), 8)
        self.assertEqual(self.summary["counts_by_status"].get("Exception"), 2)
        self.assertEqual(self.summary["exception_ids"], ["DOC-09", "DOC-10"])

    def test_mismatched_total_is_exception_on_total(self):
        by_id = {r["doc_id"]: r for r in self.results}
        row = by_id["DOC-09"]
        self.assertEqual(row["status"], "Exception")
        self.assertEqual(row["failing_field"], "total")
        self.assertIn("expected=540.00", row["reason"])
        self.assertIn("stated=560.00", row["reason"])

    def test_missing_po_is_exception_on_po_number(self):
        by_id = {r["doc_id"]: r for r in self.results}
        row = by_id["DOC-10"]
        self.assertEqual(row["status"], "Exception")
        self.assertEqual(row["failing_field"], "po_number")
        self.assertEqual(row["reason"], "po_missing")

    def test_exceptions_are_never_auto_corrected(self):
        # Extracted values in the log must match the input exactly.
        by_id = {r["doc_id"]: r for r in self.results}
        self.assertEqual(by_id["DOC-09"]["total"], "560.00")
        self.assertEqual(by_id["DOC-10"]["po_number"], "")
        self.assertEqual(by_id["DOC-10"]["total"], "324.00")

    def test_clean_documents_pass_all_validations(self):
        by_id = {r["doc_id"]: r for r in self.results}
        for doc_id in self.summary["clean_ids"]:
            row = by_id[doc_id]
            self.assertEqual(row["status"], "Clean", doc_id)
            self.assertEqual(row["line_items_sum"], row["subtotal"], doc_id)
            self.assertEqual(row["reason"], "all_validations_pass", doc_id)

    def test_duplicate_po_is_detected(self):
        doc = copy.deepcopy(self.docs[0])
        failing_field, reason = validate_document(doc, seen_pos={"PO-1001"})
        self.assertEqual(failing_field, "po_number")
        self.assertIn("duplicate_po", reason)

    def test_invalid_date_is_detected(self):
        doc = copy.deepcopy(self.docs[0])
        doc["date"] = "2026-13-40"
        failing_field, _ = validate_document(doc, seen_pos=set())
        self.assertEqual(failing_field, "date")

    def test_extraction_log_file_matches_results(self):
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["doc_id"], "DOC-01")


if __name__ == "__main__":
    unittest.main()
