# AI Agent Demos — Portfolio

**Demo — fictional data. This is not client work.**

Four small, working AI-agent demos to show what I can build for a client.
All companies, people, and data are fictional. Each demo is runnable
Python, with tests and a log a buyer can inspect.

## The demos

| Demo | What it does | Result |
|---|---|---|
| [demo1-lead-qualification](demo1-lead-qualification/) | Scores 20 fictional leads against a written rubric, routes Qualified to a CRM mock, uncertain leads to a human queue, the rest to archive | 8 Qualified / 7 Human queue / 5 Archive, 8 tests pass |
| [demo2-support-rag](demo2-support-rag/) | Answers questions only from 12 fictional help docs, cites the source, hands off out-of-scope questions | 6 answered / 2 clarified / 2 handed off, 8 tests pass |
| [demo3-validation-pipeline](demo3-validation-pipeline/) | Checks an agent draft through 5 scripted gates, then a blind re-check; defects are logged, fixed, and retested | Seeded 60-day defect caught, fixed to 30 days, retested PASS, 7 tests pass |
| [demo4-document-processing](demo4-document-processing/) | Extracts fields from 10 fictional invoices, validates them in code, sends mismatches to a human exception queue — never auto-corrects | 8 Clean / 2 Exception, 9 tests pass |

**Total: 32 tests pass.**

## How to run

```bash
cd demo1-lead-qualification && python3 lead_agent.py && python3 -m unittest test_lead_agent.py -v
cd ../demo2-support-rag && python3 support_agent.py && python3 -m unittest test_support_agent.py -v
cd ../demo3-validation-pipeline && python3 pipeline.py && python3 -m unittest test_pipeline.py -v
cd ../demo4-document-processing && python3 doc_processor.py && python3 -m unittest test_doc_processor.py -v
```

Python 3 only, no extra dependencies.

## Honest limits

These are demos, and the limits are stated in each demo's README:

- Demo 1: scoring is from structured fields; LLM extraction from free text is not built yet.
- Demo 2: retrieval is deterministic keyword overlap, answers are cited excerpts; LLM retrieval/drafting is not built yet.
- Demo 3: validator and blind re-check are deterministic scripted checks, not a different-model LLM review; no defect rate is claimed. This one is a personal pipeline project, not a client engagement.
- Demo 4: PDF and LLM extraction are not built; no accuracy claim beyond the 10-document demo set.
