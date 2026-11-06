#!/usr/bin/env python3
"""Acceptance tests for Demo 2 — Support RAG Agent. Demo — fictional data.

Tests compare the agent's output against the expected outcome written
in questions_fictional.csv; the agent itself never reads those columns.
"""

import csv
import unittest
from pathlib import Path

from support_agent import answer_question, load_docs, run

BASE = Path(__file__).resolve().parent


def load_expected():
    with open(BASE / "questions_fictional.csv", newline="", encoding="utf-8") as f:
        return {row["question_id"]: row for row in csv.DictReader(f)}


def load_log():
    with open(BASE / "outputs" / "qa_log.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestSupportAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = load_docs()
        cls.expected = load_expected()
        cls.results, cls.summary = run()

    def test_all_10_logged_in_order(self):
        log = load_log()
        self.assertEqual(len(log), 10)
        self.assertEqual(
            [r["question_id"] for r in log],
            [f"Q{ i:02d}" for i in range(1, 11)],
        )

    def test_distribution_matches_spec(self):
        self.assertEqual(self.summary["counts_by_outcome"]["answer"], 6)
        self.assertEqual(self.summary["counts_by_outcome"]["clarify_or_handoff"], 2)
        self.assertEqual(self.summary["counts_by_outcome"]["handoff"], 2)

    def test_in_scope_answers_cite_expected_doc(self):
        log = {r["question_id"]: r for r in load_log()}
        for qid in ["Q01", "Q02", "Q03", "Q04", "Q05", "Q06"]:
            row = log[qid]
            self.assertEqual(row["outcome"], "answer", qid)
            expected_doc = self.expected[qid]["expected_source"]
            self.assertEqual(row["sources"], expected_doc, qid)
            # Quoted sentence must come verbatim from the cited doc.
            doc = next(d for d in self.docs if d["doc_id"] == expected_doc)
            quoted = row["answer"].split("] ", 1)[1]
            self.assertIn(quoted.rstrip("."), doc["content"], qid)

    def test_both_out_of_scope_hand_off_not_guessed(self):
        log = {r["question_id"]: r for r in load_log()}
        for qid in ["Q09", "Q10"]:
            self.assertEqual(log[qid]["outcome"], "handoff", qid)
            self.assertEqual(log[qid]["answer"], "", qid)

    def test_ambiguous_questions_do_not_pick_one_policy(self):
        log = {r["question_id"]: r for r in load_log()}
        for qid in ["Q07", "Q08"]:
            self.assertEqual(log[qid]["outcome"], "clarify_or_handoff", qid)
            self.assertEqual(log[qid]["answer"], "", qid)
            self.assertTrue(log[qid]["missing_info"], qid)

    def test_every_handoff_carries_template(self):
        log = load_log()
        for row in log:
            if row["outcome"] in ("handoff", "clarify_or_handoff"):
                self.assertTrue(row["question"], row["question_id"])
                self.assertTrue(row["reason"], row["question_id"])
                self.assertTrue(row["missing_info"], row["question_id"])
                self.assertTrue(row["suggested_human_reply"], row["question_id"])

    def test_refund_cancel_order_change_always_hand_off(self):
        for q in [
            "Can you approve a refund for my order?",
            "Please cancel my order before it ships.",
            "Change my order to a different colour.",
        ]:
            r = answer_question(q, self.docs)
            self.assertEqual(r["outcome"], "handoff", q)
            self.assertEqual(r["answer"], "", q)

    def test_no_answer_without_source(self):
        log = load_log()
        for row in log:
            if row["outcome"] == "answer":
                self.assertTrue(row["sources"], row["question_id"])
                self.assertTrue(row["answer"].startswith("["), row["question_id"])


if __name__ == "__main__":
    unittest.main()
