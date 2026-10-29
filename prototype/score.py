"""Deterministic scoring step of the triage flow.

Input is the structured JSON the extraction prompt (PROMPTS.md) would return,
hand-entered below for the five samples. No API key is needed for this step.
Run: python prototype/score.py
"""
import json
import re
import sys

CRITERIA_VERSION = 1
WEIGHTS = {"experience": 30, "price": 25, "timeline": 15, "warranty": 15, "team": 15}
CEILING = 260_000
MAX_WEEKS = 16

# Extracted facts per proposal (None = not stated).
FACTS = {
    "A": dict(licence="direct", wsib_ins=True, installs=14, price=238_000, weeks=12, panel=25, work=10, team=4, injection=False),
    "B": dict(licence="subcontractor", wsib_ins=True, installs=6, price=189_500, weeks=10, panel=25, work=5, team=1, injection=False),
    "C": dict(licence="direct", wsib_ins=True, installs=9, price=244_000, weeks=14, panel=25, work=10, team=2, injection=True),
    "D": dict(licence="direct", wsib_ins=True, installs=11, price=231_000, weeks=None, panel=25, work=10, team=2, injection=False),
    "E": dict(licence="direct", wsib_ins=True, installs=8, price=242_500, weeks=13, panel=25, work=12, team=4, injection=False),
}
# team = count of: named lead, crew, safety plan, monitoring plan (max 4)

INJECTION_RE = re.compile(r"automated (review|system)|pre-?approved|rank (it|this) first", re.I)


def triage(pid, f):
    """Rules first: injection and mandatory checks decide status before any scoring."""
    if f["injection"]:
        return "flagged", "Contains text aimed at automated reviewers (rank-first instruction); held for human review, text ignored."
    if f["licence"] != "direct":
        return "ineligible", "Fails mandatory licence check: electrical work is subcontracted and the licence is not held by the bidder."
    if not f["wsib_ins"] or f["price"] > CEILING:
        return "ineligible", "Fails a mandatory or budget check."
    return "ranked", ""


def score(f, best_price, best_weeks):
    s = {
        "experience": min(f["installs"] / 12, 1) * 100,
        "price": best_price / f["price"] * 100,
        "timeline": 0 if f["weeks"] is None else best_weeks / f["weeks"] * 100,
        "warranty": 50 * f["panel"] / 25 + 50 * min(f["work"] / 12, 1),
        "team": f["team"] / 4 * 100,
    }
    total = sum(s[k] * WEIGHTS[k] / 100 for k in WEIGHTS)
    return s, round(total)


def breakdown(eligible, scored):
    """Per-criterion table so a reviewer can see why each proposal ranked where it did."""
    cols = list(WEIGHTS)
    print("proposal | " + " | ".join(f"{c} ({WEIGHTS[c]}%)" for c in cols) + " | total")
    for p in sorted(eligible, key=lambda p: -scored[p][1]):
        s, total = scored[p]
        print(f"{p} | " + " | ".join(f"{s[c]:.0f}" for c in cols) + f" | {total}")


def main():
    status = {p: triage(p, f) for p, f in FACTS.items()}
    eligible = [p for p, (st, _) in status.items() if st == "ranked"]
    best_price = min(FACTS[p]["price"] for p in eligible)
    best_weeks = min(FACTS[p]["weeks"] for p in eligible if FACTS[p]["weeks"])
    scored = {p: score(FACTS[p], best_price, best_weeks) for p in eligible}
    if "--breakdown" in sys.argv:
        breakdown(eligible, scored)
        return
    order = sorted(eligible, key=lambda p: -scored[p][1])
    out = []
    for i, p in enumerate(order, 1):
        _, total = scored[p]
        note = " No timeline stated, so timeline scores 0; flag for reviewer." if FACTS[p]["weeks"] is None else ""
        out.append(dict(proposal=p, rank=i, status="ranked", score=total, reason=f"Weighted score {total}/100.{note}"))
    for p, (st, why) in status.items():
        if st != "ranked":
            out.append(dict(proposal=p, rank=None, status=st, score=None, reason=why))
    out.sort(key=lambda r: r["proposal"])
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
