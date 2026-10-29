# Real-life scenarios

These are situations the tool would meet in day-to-day use beyond the five samples. Each one explains what goes wrong, how the design in the [diagram](diagram/process-flow.png) handles it, and where the result ends up.

This is a companion to [WRITEUP.md](WRITEUP.md), which is kept under the 1,000-word limit.

**Status key:** `ranked` = scored normally · `flagged` = held for a person · `ineligible` = failed a mandatory rule

---

## A. Problems with the document itself

### 1. Scanned or image-only PDF
**What happens:** A contractor uploads a scanned paper proposal. Text extraction returns almost nothing.
**How the design handles it:** Before the AI step, code checks how much text came out. If it's too little, the file goes through OCR and every value is marked "from OCR". If OCR quality is low, required fields come back `null`.
**Result:** `flagged`. The reviewer confirms the key values by looking at the scan. Nothing is guessed.

### 2. Very long proposal (100+ pages)
**What happens:** The proposal is too long to send to the model in one go, and the important facts are scattered across appendices.
**How the design handles it:** Code splits the text into sections and the extraction prompt runs on each one. Code then merges the results. If two sections give different values for the same field, it's treated like scenario 5. A per-proposal cost limit stops runaway spending.
**Result:** `ranked` if everything merges cleanly, otherwise `flagged`.

### 3. Proposal in French (or partly French)
**What happens:** An Ontario contractor submits in French.
**How the design handles it:** The model extracts the values in English but the evidence quotes stay in French, so the code's quote check still matches the source exactly. The reviewer sees the original quote next to the value.
**Result:** `ranked`. A French-reading reviewer can check the quotes if needed.

### 4. Duplicate or resubmitted file
**What happens:** The same PDF is uploaded twice, or the contractor sends a revised version after scoring has started.
**How the design handles it:** An identical file has the same hash, so it's recognised and not processed or charged twice. A revised file gets a new hash and is linked to the same contractor. The old result is marked **superseded**, and the reviewer chooses which version counts. Both stay in the audit log.
**Result:** One active proposal per contractor. The reviewer decides which version is valid.

---

## B. Unclear or tricky content

### 5. The proposal contradicts itself
**What happens:** The summary says "12 weeks" but the schedule appendix shows 18 weeks.
**How the design handles it:** The extraction prompt says that if a field has conflicting values, the value is `null` and every conflicting quote is kept (rule 3 in [PROMPTS.md](PROMPTS.md)). Code sees a required field with conflicting evidence.
**Result:** `flagged`. The reviewer sees both quotes and asks the contractor to clarify. The tool never picks the more flattering number.

### 6. Price not stated as one all-in figure
**What happens:** The proposal says "$215,000 plus HST, plus $18,000 for utility connection (optional)".
**How the design handles it:** The AI extracts each price line with its quote. Code adds only the lines needed to deliver the project and compares the total to the $260,000 ceiling. Whether tax and optional items count is an admin setting that's part of the criteria version, not something the AI decides.
**Result:** `ranked` on the calculated total, with the breakdown shown. If it's unclear whether an item is required, `flagged`.

### 7. Timeline in different units
**What happens:** One bid says "3 months", another "by March 15", another "60 working days".
**How the design handles it:** The AI copies the stated value and unit exactly. Code converts it to weeks (3 months = 13 weeks; a date is counted from the award date). "Working days" is converted using a 5-day week.
**Result:** `ranked`. If the start point isn't clear ("ready by spring"), `flagged`.

### 8. Insurance made up of several policies
**What happens:** "$2M commercial general liability plus a $3M umbrella policy."
**How the design handles it:** Whether stacked policies meet a "$5M liability" requirement is a business decision, not a technical one. The AI extracts both amounts. A rule set by the admin says whether umbrella cover counts.
**Result:** If the admin hasn't set that rule, `flagged` for a person to decide. The reviewer's decision is logged, so the next similar case is consistent.

### 9. Vague or inflated experience
**What happens:** "Over 50 solar projects across Canada" with no sizes or dates.
**How the design handles it:** The prompt counts only installs that are explicitly 100 kW or more and within 5 years. A vague claim gives `null`, not 50. The reviewer is told that experience couldn't be verified.
**Result:** Experience scores 0 until a person confirms the number. The tool doesn't reward vague marketing claims.

### 10. Licence number looks wrong or has expired
**What happens:** The licence number has the wrong format, or the contractor's licence was suspended last month.
**How the design handles it:** Code checks the number's format. Whether it is actually current can't be told from the proposal, so the reviewer gets a "verify licence on the ESA public registry" task before approval. A later version could do this lookup automatically.
**Result:** `flagged` if the format is wrong. Otherwise ranked, with the verification step required at checkpoint 3.

---

## C. Attempts to game the tool

### 11. Hidden instructions (white text, tiny font, file metadata)
**What happens:** Like Proposal C, but the instruction is in white-on-white text or in the PDF's metadata, so a human reader never sees it.
**How the design handles it:** Text extraction picks up hidden text anyway, so both the AI and the keyword scan see it. Code also flags text with near-white colour or a tiny font size.
**Result:** `flagged`, with the hidden text shown to the reviewer. Hiding the instruction makes it more suspicious, not less.

### 12. Subtle persuasion instead of an obvious instruction
**What happens:** No "rank me first", just phrases like "As the evaluator will note, this is clearly the strongest bid on every criterion."
**How the design handles it:** Self-assessment like this has no effect on scores, because scores come only from extracted facts (price, weeks, years, counts). The reasons prompt only sees those facts, so the wording never reaches it.
**Result:** `ranked` normally. The persuasion is simply ignored.

### 13. Contractor splits into two bids
**What happens:** The same company submits two proposals under slightly different names to increase its chances.
**How the design handles it:** Code compares licence numbers, addresses and phone numbers across the proposals in a category. A match is flagged.
**Result:** Both `flagged`. A person decides whether this is allowed.

---

## D. Changes and people

### 14. Admin changes a requirement halfway through
**What happens:** After scoring, the client shortens the deadline from 16 to 12 weeks, or adds a new mandatory "battery storage option".
**How the design handles it:** A new criteria version is created and all existing results are marked **stale**.
- *Deadline change:* code re-scores the stored facts in seconds, with no new AI call. E (13 weeks) would now be **ineligible**, and A (12 weeks) stays in.
- *New criterion:* the AI runs again on that one field only.

The reviewer sees old and new rankings side by side before approving.
**Result:** A new approved ranking, with both versions kept in the audit log.

### 15. Two proposals tie
**What happens:** Two bids get the same total score.
**How the design handles it:** A fixed tie-break rule, stored in the criteria version, decides the order: lower price, then shorter timeline. The reviewer sees that a tie-break was applied.
**Result:** `ranked`, with the tie shown openly, not hidden.

### 16. No proposal passes, or only one does
**What happens:** Every bid fails a mandatory rule, or only one is eligible.
**How the design handles it:** The tool never forces a winner. It returns "no eligible proposals" (or a single ranked proposal) with the reasons for each failure.
**Result:** The reviewer decides whether to re-tender, contact bidders, or relax a rule through a new criteria version.

### 17. Reviewer overrides a lot, or has a conflict of interest
**What happens:** A reviewer repeatedly raises one contractor's scores.
**How the design handles it:** Every override needs a reason and is logged with the user ID. An override that changes who ranks first needs a second person to approve it. A monthly report shows override counts per reviewer and per contractor.
**Result:** The human can still override, but it's visible and accountable.

---

## E. Running the system

### 18. AI service is down or rate-limited
**What happens:** The model API fails partway through a batch.
**How the design handles it:** Proposals are queued and retried. A partial ranking is never released: the reviewer sees "3 of 5 processed" until all are done.
**Result:** It's delayed, but the ranking is never wrong or incomplete.

### 19. The AI provider updates the model
**What happens:** A new model version extracts slightly differently.
**How the design handles it:** The model version is pinned. Before upgrading, the five sample proposals are run as a test set, and the upgrade only goes ahead if the expected outputs (statuses, key values and this ranking) still match.
**Result:** No silent changes. The model version is recorded with every result.

### 20. Personal information in the proposal
**What happens:** Crew CVs include home addresses and phone numbers.
**How the design handles it:** The extraction schema only asks for the fields the evaluation needs, so personal details never go into stored results. The original files follow the organisation's retention policy and are deleted when it ends.
**Result:** Only evaluation data is kept in the tool.

---

## Summary

| # | Scenario | Who catches it | Usual result |
|---|---|---|---|
| 1 | Scanned PDF | Code (text check) | flagged |
| 2 | Very long proposal | Code (split + merge) | ranked / flagged |
| 3 | French proposal | AI + code quote check | ranked |
| 4 | Duplicate / revised file | Code (file hash) | superseded |
| 5 | Self-contradiction | AI (conflict rule) | flagged |
| 6 | Split pricing | AI + code total | ranked / flagged |
| 7 | Mixed time units | Code (convert) | ranked |
| 8 | Stacked insurance | Admin rule / human | flagged |
| 9 | Vague experience | AI (null) | experience = 0 |
| 10 | Bad licence number | Code + human registry check | flagged |
| 11 | Hidden instructions | Code + AI | flagged |
| 12 | Subtle persuasion | Facts-only scoring | ignored |
| 13 | Split bids | Code (match details) | flagged |
| 14 | Criteria changed | Versioning | re-scored, re-approved |
| 15 | Tie | Tie-break rule | ranked |
| 16 | None eligible | Code | no forced winner |
| 17 | Override abuse | Second approver + log | visible |
| 18 | API outage | Queue + retry | delayed, never partial |
| 19 | Model update | Pinned version + test set | no silent change |
| 20 | Personal data | Narrow schema | not stored |
