# Prototype

A small working version of the flow in the [diagram](../diagram/process-flow.png). No deployment.

| File | What it does | Step in the diagram |
|---|---|---|
| `criteria.v1.json` | The admin's criteria and weights, versioned. Nothing is hard-coded in the scripts. | 0 |
| `extract.py` | Sends the Prompt 1 text from `PROMPTS.md` to Claude, then checks every quote against the source, runs the keyword injection scan, caches by file hash and writes an audit log. | 2-3 |
| `score.py` | Mandatory rules, rubric scores, weighted total, tie-break, ranking. Plain code. | 4-5 |
| `sample_facts.json` | The five samples' facts entered by hand (no proposal text), so scoring runs without an API key. | - |

## Run the scoring (no key needed)

```
python prototype/score.py               # same result as ranking.json
python prototype/score.py --breakdown   # per-criterion table
```

**Change a requirement:** copy `criteria.v1.json` to `criteria.v2.json`, edit it (for example `"max_weeks": 12`), and run `python prototype/score.py --breakdown --criteria prototype/criteria.v2.json`. With a 12-week deadline, E becomes ineligible and A stays first.

## Run the AI extraction (needs a key)

1. `pip install -r prototype/requirements.txt`
2. Copy `.env.example` to `.env` and add your key. `.env` is git-ignored. Never commit a real key.
3. Save each proposal's text as `prototype/proposals/A.txt` ... `E.txt`. This folder is git-ignored because the brief must not be copied into the repo.
4. Run:
   ```
   python prototype/extract.py --dry-run    # shows the exact prompt, no API call
   python prototype/extract.py              # writes prototype/out/facts.json + audit_log.jsonl
   python prototype/score.py --breakdown --facts prototype/out/facts.json
   ```

`extract.py --responses <folder>` re-runs the code checks on saved model outputs without calling the API.

## What I tested

The API call itself was not run, because no key was available. Everything else was tested on the five samples using hand-written model outputs:
- The facts produced give the same ranking as `ranking.json`.
- When the simulated model **missed** C's injection, the code keyword scan still flagged it.
- When a quote was changed to a price not in the proposal, A was **flagged** for a person instead of scored.
- Setting `max_weeks` to 12 made E ineligible.
