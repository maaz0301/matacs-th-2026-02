# matacs-th-2026-02

- **Name:** Maaz Khan
- **Reference:** MATACS-TH-2026-02
- **Time spent:** Approximately 60 minutes

## Start here
- **The idea:** AI reads the proposals and explains scores. Plain code decides eligibility, scores and rank. A person reviews every exception and makes the award.
- **The result:** A ranks first (98), E second (88), D third (74). B is ineligible because it doesn't hold the electrical licence itself. C is flagged because it contains an instruction telling automated reviewers to rank it first.
- **To check it yourself:** run `python prototype/score.py --breakdown` (no API key needed).

## Files
- [diagram/process-flow.png](diagram/process-flow.png) - process flow in four coloured lanes: Human (orange), AI (blue), Rules (green), Outcome. It follows a proposal from PDF upload → AI extraction → quote and injection checks → mandatory rules → scoring → AI-written reasons → human review and approval → ranked output, with every step writing to an audit log.
- [WRITEUP.md](WRITEUP.md) - answers to the five questions, rubric and sample results
- [PROMPTS.md](PROMPTS.md) - extraction and reason prompts, output schema
- [ranking.json](ranking.json) - expected ranking of A-E
- [SCENARIOS.md](SCENARIOS.md) - 20 real-life situations and how the design handles each
- [prototype/](prototype/README.md) - working prototype:
  - [criteria.v1.json](prototype/criteria.v1.json) - versioned criteria and weights
  - [extract.py](prototype/extract.py) - runs the extraction prompt, checks quotes, scans for injection
  - [score.py](prototype/score.py) - mandatory rules, scoring and ranking
  - [sample_facts.json](prototype/sample_facts.json) - sample facts so scoring runs without a key
  - [.env.example](prototype/.env.example), [requirements.txt](prototype/requirements.txt)

## AI usage disclosure
I used Claude to brainstorm procurement failure modes and draft initial JSON extraction schemas. I disagreed with the AI when it initially suggested using an LLM to evaluate pass/fail eligibility and compute numerical scores directly. That approach creates severe risks of hallucinations, scoring drift, and prompt injection (as attempted in Proposal C), so I corrected the architecture to restrict AI strictly to grounded fact extraction and human-readable explanations, keeping all eligibility, arithmetic scoring, and ranking in deterministic code.
