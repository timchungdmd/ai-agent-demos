# Demo 3 — Validation Pipeline

**Label: Personal pipeline project, not a client engagement. Demo — fictional data.**

A pipeline that catches its own mistakes before they ship. An agent draft
passes through scripted validator gates, then a fresh blind re-check that
has not seen the first verdict. Discrepancies are adjudicated, defects
are logged, and the fix is retested — so a failure found once becomes a
permanent gate, not a one-off edit.

## How to run

```bash
cd demo3-validation-pipeline
python3 pipeline.py
python3 -m unittest test_pipeline.py -v
```

Outputs:
- `outputs/validation_report.json` — every draft scored against every
  gate, plus the blind verdict recorded separately and the adjudication
- `outputs/defect_log.csv` — defect log (ID, severity, finding,
  evidence, fix, retest, gate added)
- `outputs/before_after.md` — flagged draft vs. fixed draft, with what
  changed and why

## Pipeline

```
draft → scripted validator gates → blind re-check → adjudication
      → defect log → fix → retest
```

Validator gates (see `validator_checklist.md` for the full checklist):
- G1 required fields present
- G2 citation present for policy claims
- G3 no invented numbers — every number in the answer must appear in
  the cited doc
- G4 confidence consistent with the routing decision
- G5 no unexplained duplicate of a previous output

## Worked example — the seeded defect, labelled as seeded

Input is a Demo 2 support answer (Harbor Outdoor Gear, fictional):
- **DRAFT-OK** — the real Demo 2 Q02 answer, 30-day return window
  cited to D02 Returns. Passes all five gates and the blind re-check.
- **DRAFT-SEEDED** — the same answer with the window changed to
  60 days. This defect was planted on purpose and is labelled as
  seeded in `drafts_fictional.json`; it is not a real client failure.

What happens: G3 flags the invented 60, the blind re-check
independently fails it (60 is not in D02), adjudication records
agreement, DEF-001 is logged at High severity, the fix restores the
documented 30 days, and the retest passes. No new gate was needed —
G3 already catches this, and the demo proves the gate fires.

Honest scope note, same as Demos 1–2: the validator and the blind
re-check are deterministic scripted checks against the fictional docs,
not a different LLM model. The gates, the separation of verdicts, the
adjudication rule, and the defect-log discipline are what is
demonstrated. Do not list different-model blind review or a measured
defect rate as built experience from this demo alone until that step
is actually added and measured.

## Acceptance criteria (checked by the tests)

- Validator checklist is published and each draft is scored against
  every gate, not a summary
- Blind re-check verdict is recorded separately from the first verdict
- The seeded defect is caught, logged, fixed, and retested to pass
- No defect is silently edited away without a log entry

## Files

- `pipeline.py` — validator gates, blind re-check, adjudication,
  defect log, fix, retest
- `drafts_fictional.json` — two drafts, one clean, one seeded
  (labelled as seeded)
- `validator_checklist.md` — the five gates, publishable as-is
- `test_pipeline.py` — acceptance tests (7 tests)
- `outputs/` — generated report, defect log, and before/after
