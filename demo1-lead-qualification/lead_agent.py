#!/usr/bin/env python3
"""
Demo 1 — Lead-Qualification Agent. Demo — fictional data.

Pipeline: intake -> extract/score against a written rubric -> validate
-> route -> log. No lead is silently dropped, and no low-confidence
lead is auto-written as Qualified.

Scoring rubric (0-100, written before scoring):
  Budget fit:    30 points
  Timeline fit:  25 points
  Service match: 25 points
  Intent signal: 20 points

Routing:
  70+       -> Qualified (CRM mock + alert)
  40-69     -> Human queue (with the uncertain field / reason)
  Below 40  -> Archive with reason (still logged)

Disqualifiers cap the score at 39 and force Archive, except a
duplicate, which forces Human queue so it is never double-counted
as a new Qualified lead.

In a production version, the extraction step (structured fields
from free-text messages) would be done by an LLM. In this demo the
structured fields are supplied in the CSV so scoring is fully
reproducible and testable; the rubric, validation, routing, and
logging are the parts being demonstrated.

Usage:
  python3 lead_agent.py
  python3 -m unittest test_lead_agent.py -v
"""

import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
INPUT_CSV = BASE / "leads_fictional.csv"
OUTPUT_CSV = BASE / "outputs" / "decision_log.csv"
SUMMARY_JSON = BASE / "outputs" / "summary.json"

BUDGET_POINTS = {
    "high": 30,
    "medium": 20,
    "low": 10,
    "unknown": 5,
    "below_minimum": 0,
}
TIMELINE_POINTS = {
    "this_week": 25,
    "this_month": 20,
    "next_2_months": 12,
    "just_browsing": 5,
    "unknown": 5,
}
SERVICE_POINTS = {
    "exact": 25,
    "related": 15,
    "not_offered": 0,
}
INTENT_POINTS = {
    "ready_to_book": 20,
    "request_quote": 15,
    "general_question": 8,
    "spam_probe": 0,
}

REQUIRED_FIELDS = [
    "lead_id", "name", "email", "channel", "service_requested",
    "service_match", "budget_band", "timeline", "location_status", "intent",
]


def score_lead(lead, seen_emails):
    """Score one lead. Returns a dict with breakdown, score, route, reason."""
    # Validation: required fields present and mappings known.
    missing = [f for f in REQUIRED_FIELDS if not lead.get(f)]
    unknown = []
    for field, table in [
        ("budget_band", BUDGET_POINTS),
        ("timeline", TIMELINE_POINTS),
        ("service_match", SERVICE_POINTS),
        ("intent", INTENT_POINTS),
    ]:
        if lead.get(field) and lead[field] not in table:
            unknown.append(field)
    if missing or unknown:
        raise ValueError(
            f"{lead.get('lead_id', '?')}: missing={missing} unknown={unknown}"
        )

    breakdown = {
        "budget": BUDGET_POINTS[lead["budget_band"]],
        "timeline": TIMELINE_POINTS[lead["timeline"]],
        "service": SERVICE_POINTS[lead["service_match"]],
        "intent": INTENT_POINTS[lead["intent"]],
    }
    raw_score = sum(breakdown.values())
    assert raw_score == breakdown["budget"] + breakdown["timeline"] \
        + breakdown["service"] + breakdown["intent"]

    reasons = []
    # Disqualifiers.
    if lead["location_status"] == "out_of_area":
        reasons.append("out_of_area")
    if lead["service_match"] == "not_offered":
        reasons.append("service_not_offered")
    if lead["budget_band"] == "below_minimum":
        reasons.append("budget_below_minimum")
    if lead["intent"] == "spam_probe":
        reasons.append("spam_probe")

    is_duplicate = lead["email"] in seen_emails
    if is_duplicate:
        reasons.append(f"duplicate_of_earlier_lead_with_same_email")

    if is_duplicate:
        route = "Human queue"
        score = raw_score  # Score is preserved for transparency; routing is overridden.
        if "duplicate_of_earlier_lead_with_same_email" not in reasons:
            reasons.append("duplicate")
    elif reasons:
        route = "Archive"
        score = min(raw_score, 39)
    elif raw_score >= 70:
        route = "Qualified"
        score = raw_score
    elif raw_score >= 40:
        route = "Human queue"
        score = raw_score
        # Name the uncertain field for every human-queue item.
        if lead["budget_band"] == "unknown":
            reasons.append("uncertain_field:budget")
        if lead["timeline"] in ("just_browsing", "unknown"):
            reasons.append("uncertain_field:timeline")
        if lead["intent"] == "general_question":
            reasons.append("uncertain_field:intent")
        if lead["budget_band"] == "low":
            reasons.append("uncertain_field:budget_low")
        if not reasons:
            reasons.append("uncertain_field:score_in_middle_band")
    else:
        route = "Archive"
        score = raw_score
        reasons.append("score_below_threshold")

    destination = {
        "Qualified": "CRM mock + alert",
        "Human queue": "Human queue",
        "Archive": "Archive (logged)",
    }[route]

    return {
        "lead_id": lead["lead_id"],
        "name": lead["name"],
        "email": lead["email"],
        "service_requested": lead["service_requested"],
        "budget_points": breakdown["budget"],
        "timeline_points": breakdown["timeline"],
        "service_points": breakdown["service"],
        "intent_points": breakdown["intent"],
        "raw_score": raw_score,
        "score": score,
        "route": route,
        "destination": destination,
        "reason": ";".join(reasons) if reasons else "meets_qualified_threshold",
    }


def run(input_csv=INPUT_CSV, output_csv=OUTPUT_CSV, summary_json=SUMMARY_JSON):
    with open(input_csv, newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    seen_emails = set()
    results = []
    for lead in leads:
        result = score_lead(lead, seen_emails)
        results.append(result)
        seen_emails.add(lead["email"])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].keys()) if results else []
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    counts = {}
    for r in results:
        counts[r["route"]] = counts.get(r["route"], 0) + 1
    summary = {
        "total_leads": len(results),
        "counts_by_route": counts,
        "qualified_ids": [r["lead_id"] for r in results if r["route"] == "Qualified"],
        "human_queue_ids": [r["lead_id"] for r in results if r["route"] == "Human queue"],
        "archive_ids": [r["lead_id"] for r in results if r["route"] == "Archive"],
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Processed {len(results)} fictional leads.")
    print(f"Counts: {counts}")
    print(f"Decision log: {output_csv}")
    print(f"Summary: {summary_json}")
    return results, summary


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # Keep the failure visible, do not silently log.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
