# Write-up

## 1. AI vs. rules
- **AI:** reading messy proposal text and extracting fields into JSON; drafting plain-English reasons. Unstructured text is what AI is good at.
- **Rules (code):** the mandatory pass/fail checks (licence, WSIB, $5M insurance), per-criterion scoring from a fixed rubric, the weighted sum, and the ranking. These must be exact, repeatable and auditable, so no AI.
- **Why:** AI can be wrong or inconsistent. Keeping it away from decisions limits the damage.

## 2. Consistency and explainability
- Temperature 0, schema-constrained output, pinned model and prompt versions.
- Every extracted value carries a verbatim quote. Code rejects any value whose quote is not in the source.
- The reviewer sees a per-criterion table: raw value, quote, rubric score, weight, one-line reason.
- Same input plus same criteria version gives the same score.

## 3. Human in the loop
- **Checkpoints:** (a) failed or low-confidence extraction, (b) every flagged or ineligible proposal, (c) final ranking before it is released.
- Humans can override any extracted value or score, but must enter a reason.
- **Audit log:** original AI output, original score, override, reason, user ID, timestamp, criteria version, prompt version.

## 4. Changing criteria
- Criteria and weights are versioned. Each score records the version used.
- Editing creates a new version; old results stay visible but are marked "stale".
- Because scoring is code over stored extractions, re-scoring is cheap and needs no new AI call. Only changes to extraction fields trigger re-extraction.
- Admin edits are logged. A human approves the re-ranked output.

## 5. Risks and safeguards
| Risk | Safeguard |
|---|---|
| Wrong extraction | Evidence quotes checked by code; nulls instead of guesses; human review of low-confidence cases |
| Hallucination | Scoring uses only extracted fields; reasons drafted from those fields only |
| Bias | Rubric scores facts, not name or style; blind the contractor name during scoring; sample-audit results |
| Manipulation (Proposal C contains text telling automated reviewers to rank it first) | Proposal text is untrusted data in the prompt; injection detector flags it; code excludes it from ranking (`flagged`) and a human decides; the instruction never affects any score |
| Missing data (Proposal D has no timeline; Proposal B relies on a subcontractor's licence) | D: a missing timeline scores 0 on timeline and the reviewer is told to ask for a schedule. B: the brief requires the licence to be held by the bidder, so it is `ineligible`; the human checkpoint can still review it |
| Cost | One extraction call per proposal; scoring is code; cache by file hash; use a small model for extraction |

## Sample set result
A ranks 1 (98), E 2 (88), D 3 (74). B is ineligible (licence not held by the bidder). C is flagged for the rank-first instruction and is not scored until a human clears it. Details are in `ranking.json`; `prototype/score.py` reproduces the scores.

Assumptions: experience is capped at 12 qualifying installs; price and timeline are scored relative to the best eligible bid; warranty is half panel, half workmanship (capped at 12 years); team counts named lead, crew, safety plan and monitoring plan.
