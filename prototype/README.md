# Prototype

`score.py` is the deterministic half of the flow: injection and mandatory checks, rubric scoring, weighted total and ranking. Its inputs are the structured facts the extraction prompt in `PROMPTS.md` would produce, entered by hand for the five samples (letters only, no proposal text).

```
python prototype/score.py
```

Output matches `ranking.json`. The AI extraction call is not wired up; `.env.example` shows where a key would go. Never commit a real key.
