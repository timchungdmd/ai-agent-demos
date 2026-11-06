"""Acceptance tests for Demo 3 — Validation Pipeline.

The spec's acceptance criteria, as tests:
  - Validator checklist is published and each draft is scored against
    every gate, not a summary.
  - Blind re-check verdict is recorded separately from the first verdict.
  - At least one seeded defect is caught, logged, fixed, and retested
    to pass.
  - No defect is silently edited away without a log entry.
"""

import csv
import json
import unittest
from pathlib import Path

from pipeline import (adjudicate, blind_recheck, fix_seeded_defect,
                      load_docs, run, third_check_verbatim,
                      validator_gates)

BASE = Path(__file__).resolve().parent


class TestValidationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.defects = run()
        cls.docs = load_docs()
        cls.drafts = json.loads((BASE / "drafts_fictional.json").read_text())

    def test_both_drafts_scored_against_every_gate(self):
        for entry in self.report:
            self.assertEqual(len(entry["gates"]), 5)
            self.assertEqual(
                {g["gate"] for g in entry["gates"]},
                {"G1_required_fields_present", "G2_citation_present",
                 "G3_no_invented_numbers", "G4_confidence_matches_routing",
                 "G5_no_unexplained_duplicate"})

    def test_clean_draft_passes_both_checks(self):
        clean = next(r for r in self.report if r["draft_id"] == "DRAFT-OK")
        self.assertTrue(clean["validator_passed"])
        self.assertEqual(clean["blind_verdict"], "pass")
        self.assertEqual(clean["final_decision"], "pass")

    def test_seeded_defect_caught_by_both_checks_independently(self):
        seeded = next(r for r in self.report
                      if r["draft_id"] == "DRAFT-SEEDED")
        self.assertFalse(seeded["validator_passed"])
        self.assertEqual(seeded["blind_verdict"], "fail")
        self.assertFalse(seeded["adjudication"]["disagreement"])
        self.assertEqual(seeded["final_decision"], "fail")
        g3 = next(g for g in seeded["gates"]
                  if g["gate"] == "G3_no_invented_numbers")
        self.assertFalse(g3["passed"])
        self.assertIn("60", g3["evidence"])

    def test_blind_verdict_recorded_separately(self):
        for entry in self.report:
            self.assertIn("blind_verdict", entry)
            self.assertIn("blind_evidence", entry)
            # Blind verdict is not just a copy of the validator result:
            # it is computed by a different function over docs + draft.
            draft = next(d for d in self.drafts
                         if d["draft_id"] == entry["draft_id"])
            self.assertEqual(entry["blind_verdict"],
                             blind_recheck(draft, self.docs)["verdict"])

    def test_seeded_defect_logged_fixed_and_retested(self):
        self.assertEqual(len(self.defects), 1)
        defect = self.defects[0]
        self.assertEqual(defect["id"], "DEF-001")
        self.assertEqual(defect["retest_result"], "PASS")
        self.assertIn("60-day", defect["finding"])
        # The fix itself re-passes: check the fixed draft directly.
        seeded = next(d for d in self.drafts
                      if d["draft_id"] == "DRAFT-SEEDED")
        fixed = fix_seeded_defect(seeded, self.docs)
        self.assertIn("30-day", fixed["answer_text"])
        self.assertTrue(all(g["passed"]
                            for g in validator_gates(fixed, self.docs, set())))
        self.assertEqual(blind_recheck(fixed, self.docs)["verdict"], "pass")

    def test_no_silent_edit(self):
        # Every failed draft has exactly one defect-log row, and the
        # before/after file names the change.
        failed = [r for r in self.report if r["final_decision"] == "fail"]
        self.assertEqual(len(failed), len(self.defects))
        before_after = (BASE / "outputs" / "before_after.md").read_text()
        self.assertIn("60-day", before_after)
        self.assertIn("30-day", before_after)
        # The defect log on disk matches the in-memory log.
        with open(BASE / "outputs" / "defect_log.csv",
                  newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "DEF-001")

    def test_adjudication_disagreement_path(self):
        # Disagreeing verdicts must surface as a disagreement, not be
        # silently resolved by either side.
        adj = adjudicate(True, "fail")
        self.assertTrue(adj["disagreement"])
        self.assertEqual(adj["decision"], "adjudication_needed")
        # Third check: verbatim sentence passes, invented one fails.
        clean = next(d for d in self.drafts if d["draft_id"] == "DRAFT-OK")
        seeded = next(d for d in self.drafts
                      if d["draft_id"] == "DRAFT-SEEDED")
        self.assertEqual(third_check_verbatim(clean, self.docs), "pass")
        self.assertEqual(third_check_verbatim(seeded, self.docs), "fail")


if __name__ == "__main__":
    unittest.main()
