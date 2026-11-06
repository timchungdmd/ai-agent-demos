# Validator checklist — Demo 3

Applies to every agent draft before it ships. All five gates must pass
or the draft is flagged; a flagged draft is never silently edited.

- **G1 — Required fields present.** draft_id, question, answer_text,
  cited_doc_id, confidence, routing. Missing field = flag.
- **G2 — Citation present.** A policy claim must cite a doc ID that
  exists in the knowledge base. No citation, or an unknown doc = flag.
- **G3 — No invented numbers.** Every number in the answer body must
  appear in the cited doc's text. (The citation prefix itself, e.g.
  `[D02 Returns]`, is stripped before this check so its doc number is
  not mistaken for a policy number.) Any invented number = flag.
- **G4 — Confidence matches routing.** High confidence pairs with an
  answer; anything lower pairs with a handoff/clarification. A mismatch
  = flag.
- **G5 — No unexplained duplicate.** An answer identical to a previous
  output, with no reason recorded, = flag.

After the gates, a blind re-check re-derives the answer's numbers from
the cited doc without seeing the validator verdict. If the two verdicts
disagree, a neutral third check — is the quoted sentence verbatim in
the cited doc? — decides, and the disagreement is logged with the
decision.
