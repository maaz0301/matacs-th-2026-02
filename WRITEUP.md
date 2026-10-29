# Write-up

**Design in one line:** AI reads the proposals, code makes the decisions, and a person signs off. See the [flow diagram](diagram/process-flow.png).

## 1. AI vs. rules

| Step | Done by | Why |
|---|---|---|
| Extract facts from proposal text into JSON | **AI** | Free text in varied wording is what AI reads well. |
| Check each value's quote against the source | **Code** | A string match cheaply catches made-up values. |
| Detect instructions aimed at reviewers | **AI + code** | AI spots odd wording; a keyword scan backs it up. |
| Mandatory pass/fail (licence, WSIB, $5M insurance) | **Code** | Yes/no rules must never vary between runs. |
| Score each criterion 0–100 and apply weights | **Code** | Arithmetic should be exact, repeatable and easy to audit. |
| Write a reason for each score | **AI** | Good at wording; sees only facts, cannot change scores. |
| Final award | **Human** | The brief says a person decides. |

**Where I drew the line:** AI never decides anything. It turns text into facts and facts into sentences. Everything that changes a status, score or rank is code a reviewer can read.

## 2. Consistency and explainability

- **Repeatable:** pinned model, versioned prompt, enforced JSON schema; each file is extracted once and cached by hash.
- **Same result twice?** Yes. Scoring is code over stored facts, so the same facts and criteria version always give the same rank.
- **Explainable:** per criterion the reviewer sees the extracted value, its source quote, score, weight and a one-line reason. Ineligible or flagged items show the exact rule that fired.

**Rubric (version 1)**, all on 0–100:
- **Experience:** qualifying installs (≥100 kW, last 5 years) ÷ 12, capped at 100.
- **Price:** lowest eligible price ÷ this price. Over the $260,000 ceiling makes the proposal ineligible.
- **Timeline:** fastest eligible weeks ÷ these weeks. Over 16 weeks makes it ineligible; not stated scores 0 and is flagged to the reviewer.
- **Warranty:** half for panel years (out of 25), half for workmanship years (out of 12).
- **Team:** 25 points each for a named lead, a defined crew, a safety plan and a monitoring plan.

## 3. Human in the loop

- **Checkpoint 1, extraction:** a value whose quote is not in the source goes to a reviewer to confirm or correct.
- **Checkpoint 2, exceptions:** every `flagged` and `ineligible` proposal is shown with its reason. The reviewer can clear, confirm or override it.
- **Checkpoint 3, release:** the reviewer approves the ranked list before release. The award stays with a person.
- **Overrides** need a written reason. The original value is kept, not replaced.
- **Audit log, one entry per change:** proposal, field, AI value, evidence quote, rule or score result, override value, reason, user ID, timestamp, criteria version, prompt version, model version. The log is append-only.

## 4. Changing criteria

- Criteria and weights are stored as numbered versions. Every score records the version it used.
- An edit creates a new version. Existing results are marked **stale**, not silently changed.
- **Weights or thresholds changed:** code re-scores stored facts instantly, with no new AI call.
- **New criterion added:** the AI extracts only that new field.
- The reviewer sees old and new ranks side by side and approves before the new ranking replaces the old one. The edit itself goes in the audit log.

## 5. Risks and safeguards

| Risk | Safeguard |
|---|---|
| **Wrong extraction** (e.g. counting "since 2020" as within 5 years) | Code verifies every source quote; unclear values go to a human; extraction is tested on known samples first. |
| **Made-up facts** | Missing means `null`, never a guess. Scores use only verified fields. Reasons are written from those fields only. |
| **Bias** (favouring polished writing or familiar names) | Scores use facts, not tone; the name is hidden from the reason step; reviewers spot-check results. |
| **Manipulation:** Proposal C tells automated reviewers it is pre-approved and should rank first | The prompt treats proposal text as data and ignores embedded instructions; the AI reports the text and a keyword scan catches it too. C is `flagged` until a person clears it. Even if missed, the AI cannot set scores. |
| **Incomplete bids:** D gives no timeline; B leaves its licence to a subcontractor | D scores 0 for timeline and the reviewer is prompted to request a schedule. B fails "held by the bidder" and is `ineligible`, shown to a reviewer. |
| **Cost** | One extraction call and one short reason call per proposal; re-scoring is free; hash caching avoids paying twice. |

## Sample set result

| Rank | Proposal | Status | Exp. (30) | Price (25) | Time (15) | Warranty (15) | Team (15) | Score |
|---|---|---|---|---|---|---|---|---|
| 1 | A | ranked | 100 | 97 | 100 | 92 | 100 | **98** |
| 2 | E | ranked | 67 | 95 | 92 | 100 | 100 | **88** |
| 3 | D | ranked | 92 | 100 | 0 | 92 | 50 | **74** |
| – | B | ineligible | – | – | – | – | – | – |
| – | C | flagged | – | – | – | – | – | – |

`prototype/score.py --breakdown` reproduces this table from `criteria.v1.json`.

**Assumptions** (to confirm with the admin):
- Price compares to the best *eligible* bid, so B's low price does not affect others.
- A missing timeline scores 0 rather than making D ineligible, because timeline is weighted, not mandatory.
- If a reviewer clears C, it would score about 80 and rank third. Its installs are counted "since 2020", so the 5-year window needs checking.
