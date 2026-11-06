#!/usr/bin/env python3
"""Acceptance tests for Demo 1. Run: python3 -m unittest test_lead_agent.py -v"""
import csv
import unittest
from pathlib import Path

from lead_agent import run, INPUT_CSV, OUTPUT_CSV

BASE = Path(__file__).resolve().parent


class TestLeadAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results, cls.summary = run()
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            cls.leads = list(csv.DictReader(f))

    def test_all_leads_logged(self):
        self.assertEqual(len(self.results), 20)
        self.assertEqual(len(self.leads), 20)
        self.assertEqual(
            [r["lead_id"] for r in self.results],
            [lead["lead_id"] for lead in self.leads],
        )

    def test_expected_distribution(self):
        # Spec target: 8 Qualified, 7 Human queue, 5 Archive.
        self.assertEqual(self.summary["counts_by_route"].get("Qualified"), 8)
        self.assertEqual(self.summary["counts_by_route"].get("Human queue"), 7)
        self.assertEqual(self.summary["counts_by_route"].get("Archive"), 5)

    def test_score_breakdowns_sum(self):
        for r in self.results:
            total = (
                r["budget_points"] + r["timeline_points"]
                + r["service_points"] + r["intent_points"]
            )
            self.assertEqual(r["raw_score"], total, r["lead_id"])

    def test_no_low_confidence_auto_qualified(self):
        for r in self.results:
            if r["route"] == "Qualified":
                self.assertGreaterEqual(r["score"], 70, r["lead_id"])
                self.assertNotIn("duplicate", r["reason"])
                self.assertNotIn("out_of_area", r["reason"])
                self.assertNotIn("service_not_offered", r["reason"])
                self.assertNotIn("budget_below_minimum", r["reason"])
                self.assertNotIn("spam_probe", r["reason"])

    def test_human_queue_items_name_a_reason(self):
        for r in self.results:
            if r["route"] == "Human queue":
                self.assertTrue(r["reason"], r["lead_id"])

    def test_duplicate_is_not_double_counted_as_qualified(self):
        by_id = {r["lead_id"]: r for r in self.results}
        # L015 duplicates L001's email.
        self.assertEqual(by_id["L015"]["route"], "Human queue")
        self.assertIn("duplicate", by_id["L015"]["reason"])
        self.assertEqual(by_id["L001"]["route"], "Qualified")

    def test_disqualifiers_are_archived_not_lost(self):
        by_id = {r["lead_id"]: r for r in self.results}
        self.assertEqual(by_id["L016"]["route"], "Archive")  # out of area
        self.assertEqual(by_id["L018"]["route"], "Archive")  # service not offered
        self.assertEqual(by_id["L019"]["route"], "Archive")  # below minimum
        self.assertEqual(by_id["L017"]["route"], "Archive")  # spam probe

    def test_decision_log_file_matches_results(self):
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["lead_id"], "L001")


if __name__ == "__main__":
    unittest.main()
