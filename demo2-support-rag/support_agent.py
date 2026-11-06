#!/usr/bin/env python3
"""
Demo 2 — Support RAG Agent. Demo — fictional data.

Company: Harbor Outdoor Gear (fictional, Shopify-style store).
Knowledge base: 12 short fictional help docs (docs_fictional.json).
Test set: 10 questions (questions_fictional.csv) with the expected
source / outcome written first; the agent never reads the expected
columns when deciding — tests compare its output against them.

Pipeline: question -> retrieve top 3 doc chunks (keyword overlap)
-> confidence check -> answer with citation, or refuse to guess
and hand off.

Hard guardrails (code, not just a prompt instruction):
  - No refund approval, no order change, no cancellation — always handoff.
  - No answer without a source for a policy question.
  - A grounded answer quotes a sentence from the cited doc; it never
    invents a policy, date, price, or shipping time.
  - Every handoff carries: question, sources found, missing info,
    reason, and a suggested human reply.

Honest scope note, same as Demo 1: retrieval here is deterministic
keyword overlap and the "answer" is a cited excerpt from the
retrieved doc, so the run is fully reproducible and testable.
The retrieval gate, citation rule, and handoff are what is
demonstrated. Do not list LLM retrieval or LLM drafting as built
experience from this demo alone until an embedding + LLM step is
actually added and tested.

Usage:
  python3 support_agent.py
  python3 -m unittest test_support_agent.py -v
"""

import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DOCS_JSON = BASE / "docs_fictional.json"
QUESTIONS_CSV = BASE / "questions_fictional.csv"
OUTPUT_CSV = BASE / "outputs" / "qa_log.csv"
SUMMARY_JSON = BASE / "outputs" / "summary.json"

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "can", "could", "should", "would", "i", "you", "we", "they", "it",
    "my", "your", "our", "me", "how", "what", "when", "where", "why",
    "and", "or", "for", "to", "of", "in", "on", "with", "by", "at",
    "from", "after", "within", "have", "has", "had", "be", "been",
    "if", "than", "then", "there", "this", "that", "these", "those",
}

# Hard handoff triggers: actions the agent must never approve itself.
HANDOFF_PATTERNS = [
    r"\brefund\b", r"\bcancel\b", r"\bcancellation\b",
    r"\border change\b", r"\bchange my order\b", r"\bapprove\b",
]

MIN_GROUNDED_SCORE = 2   # Distinct matched content tokens in the top doc.
AMBIGUITY_GAP = 1        # Top two docs this close -> clarify / hand off.


def tokenize(text):
    tokens = re.findall(r"[a-z]+", text.lower())
    out = []
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        # Light singularisation so cards/card, items/item, returns/return match.
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        out.append(tok)
    return out


def load_docs():
    with open(DOCS_JSON, encoding="utf-8") as f:
        return json.load(f)


def retrieve(question, docs, top_n=3):
    """Score docs by distinct matched content tokens. Returns ranked list."""
    q_tokens = set(tokenize(question))
    scored = []
    for doc in docs:
        d_tokens = set(tokenize(doc["title"] + " " + doc["content"]))
        matched = sorted(q_tokens & d_tokens)
        scored.append({
            "doc_id": doc["doc_id"], "title": doc["title"],
            "content": doc["content"], "score": len(matched),
            "matched": matched,
        })
    scored.sort(key=lambda d: (-d["score"], d["doc_id"]))
    return scored[:top_n]


def pick_sentence(doc_content, matched):
    """First sentence containing a matched token, else the first sentence."""
    sentences = [s.strip() for s in doc_content.split(".") if s.strip()]
    for sentence in sentences:
        s_tokens = set(tokenize(sentence))
        if s_tokens & set(matched):
            return sentence + "."
    return sentences[0] + "." if sentences else doc_content


def answer_question(question, docs):
    """Returns a dict: outcome in {answer, clarify_or_handoff, handoff}."""
    ranked = retrieve(question, docs)
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    sources = [d["doc_id"] for d in ranked if d["score"] > 0]

    # Hard guardrail first: refund / cancellation / order change always hands off.
    hard_hit = any(re.search(p, question.lower()) for p in HANDOFF_PATTERNS)
    if hard_hit:
        return {
            "outcome": "handoff",
            "reason": "action_requires_human_approval",
            "sources": ";".join(sources),
            "answer": "",
            "missing_info": "Human approval for a refund, cancellation, or order change.",
            "suggested_human_reply": (
                "Thanks for asking — I cannot approve that change here, so "
                "I have passed your request to a team member with the details."
            ),
        }

    # Low retrieval: nothing in the docs grounds an answer -> refuse to guess.
    if top["score"] < MIN_GROUNDED_SCORE:
        return {
            "outcome": "handoff",
            "reason": "no_grounding_doc",
            "sources": ";".join(sources),
            "answer": "",
            "missing_info": "No help doc covers this question.",
            "suggested_human_reply": (
                "Thanks for asking — that is not covered in our help docs, "
                "so I have passed your question to a team member."
            ),
        }

    # Ambiguity: two docs score close together -> clarify, do not pick one.
    if second and second["score"] >= MIN_GROUNDED_SCORE \
            and (top["score"] - second["score"]) <= AMBIGUITY_GAP:
        return {
            "outcome": "clarify_or_handoff",
            "reason": "ambiguous_between_docs",
            "sources": ";".join(sources),
            "answer": "",
            "missing_info": (
                f"Question matches both {top['doc_id']} ({top['title']}) and "
                f"{second['doc_id']} ({second['title']}); which one applies?"
            ),
            "suggested_human_reply": (
                "Could you clarify which of these you mean, so I can give "
                "you the right policy? A team member can also pick this up."
            ),
        }

    # Grounded answer: a quoted sentence from the cited doc, nothing invented.
    sentence = pick_sentence(top["content"], top["matched"])
    return {
        "outcome": "answer",
        "reason": "grounded_in_doc",
        "sources": top["doc_id"],
        "answer": f"[{top['doc_id']} {top['title']}] {sentence}",
        "missing_info": "",
        "suggested_human_reply": "",
    }


def run(questions_csv=QUESTIONS_CSV, output_csv=OUTPUT_CSV,
        summary_json=SUMMARY_JSON):
    docs = load_docs()
    with open(questions_csv, newline="", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))

    results = []
    for q in questions:
        r = answer_question(q["question"], docs)
        results.append({
            "question_id": q["question_id"],
            "question": q["question"],
            "outcome": r["outcome"],
            "reason": r["reason"],
            "sources": r["sources"],
            "answer": r["answer"],
            "missing_info": r["missing_info"],
            "suggested_human_reply": r["suggested_human_reply"],
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    summary = {
        "total_questions": len(results),
        "counts_by_outcome": counts,
        "answered_ids": [r["question_id"] for r in results if r["outcome"] == "answer"],
        "clarify_ids": [r["question_id"] for r in results if r["outcome"] == "clarify_or_handoff"],
        "handoff_ids": [r["question_id"] for r in results if r["outcome"] == "handoff"],
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Processed {len(results)} fictional questions.")
    print(f"Counts: {counts}")
    print(f"Q&A log: {output_csv}")
    print(f"Summary: {summary_json}")
    return results, summary


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
