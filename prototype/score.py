"""Deterministic half of the triage flow: status rules, rubric scoring, weighted total, ranking.

Criteria come from a versioned config file, never from this code. Facts come from
sample_facts.json (hand-entered) or from extract.py's output.

Run:
  python prototype/score.py                      # ranking.json-style output
  python prototype/score.py --breakdown          # per-criterion table
  python prototype/score.py --criteria my.json   # try changed criteria
  python prototype/score.py --facts prototype/out/facts.json
"""
import argparse
import datetime
import json
from pathlib import Path

HERE = Path(__file__).parent


def triage(f, c):
    """Status rules run before any scoring. Returns (status, reason)."""
    m = c["mandatory"]
    if f["injection"]:
        return "flagged", "Contains text aimed at automated reviewers; ignored and held for human review."
    if f["issues"]:
        return "flagged", "Needs a person to confirm: " + "; ".join(f["issues"])
    if m["licence_held_by_bidder"] and f["licence"] != "held_by_bidder":
        who = "a subcontractor holds it" if f["licence"] == "subcontractor" else "not stated"
        return "ineligible", f"Fails mandatory licence check: licence not held by the bidder ({who})."
    if m["wsib_clearance"] and not f["wsib"]:
        return "ineligible", "Fails mandatory check: WSIB clearance not confirmed."
    if (f["insurance_cad"] or 0) < m["min_liability_insurance_cad"]:
        return "ineligible", "Fails mandatory check: liability insurance below the required amount."
    if f["price_cad"] is None:
        return "flagged", "No total price stated; a person must confirm it."
    if f["price_cad"] > c["budget_ceiling_cad"]:
        return "ineligible", f"Price ${f['price_cad']:,} is over the ${c['budget_ceiling_cad']:,} ceiling."
    if f["weeks"] is not None and f["weeks"] > c["max_weeks"]:
        return "ineligible", f"Timeline of {f['weeks']} weeks is over the {c['max_weeks']}-week limit."
    return "ranked", ""


def score(f, c, best_price, best_weeks):
    r = c["rubric"]
    s = {
        "experience": min((f["installs"] or 0) / r["experience_full_marks_at"], 1) * 100,
        "price": best_price / f["price_cad"] * 100,
        "timeline": 0 if f["weeks"] is None else best_weeks / f["weeks"] * 100,
        "warranty": 50 * min((f["panel_years"] or 0) / r["panel_warranty_full_marks_years"], 1)
        + 50 * min((f["workmanship_years"] or 0) / r["workmanship_warranty_full_marks_years"], 1),
        "team": sum(item in f["team"] for item in r["team_items"]) / len(r["team_items"]) * 100,
    }
    total = sum(s[k] * w / 100 for k, w in c["weights"].items())
    return s, round(total)


def reason(f, s, total):
    strong = [k for k, v in s.items() if v >= 95]
    weak = [k for k, v in s.items() if v < 60]
    parts = [f"Score {total}/100."]
    if strong:
        parts.append("Strongest on " + ", ".join(strong) + ".")
    if weak:
        parts.append("Weaker on " + ", ".join(weak) + ".")
    if f["weeks"] is None:
        parts.append("No timeline stated (scored 0); reviewer should request a schedule.")
    return " ".join(parts)


def rank(facts, c):
    if sum(c["weights"].values()) != 100:
        raise SystemExit(f"Weights in criteria v{c['version']} add up to {sum(c['weights'].values())}, not 100.")
    status = {p: triage(f, c) for p, f in facts.items()}
    eligible = [p for p, (st, _) in status.items() if st == "ranked"]
    scored = {}
    if eligible:
        best_price = min(facts[p]["price_cad"] for p in eligible)
        weeks = [facts[p]["weeks"] for p in eligible if facts[p]["weeks"]]
        best_weeks = min(weeks) if weeks else 1
        scored = {p: score(facts[p], c, best_price, best_weeks) for p in eligible}

    def tie_key(p):
        f = facts[p]
        keys = {"price": f["price_cad"], "timeline": f["weeks"] if f["weeks"] is not None else 10**6}
        return (-scored[p][1], *[keys[k] for k in c["tie_break"]])

    order = sorted(eligible, key=tie_key)
    rows = []
    for i, p in enumerate(order, 1):
        s, total = scored[p]
        rows.append(dict(proposal=p, rank=i, status="ranked", score=total, reason=reason(facts[p], s, total)))
    for p, (st, why) in status.items():
        if st != "ranked":
            rows.append(dict(proposal=p, rank=None, status=st, score=None, reason=why))
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"], r["proposal"]))
    return rows, scored, order


def write_audit(path, rows, scored, c, args):
    """Append-only record of how each result was produced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            entry = {"step": "score", "proposal": r["proposal"], "status": r["status"], "rank": r["rank"],
                     "score": r["score"], "criterion_scores": {k: round(v) for k, v in scored[r["proposal"]][0].items()}
                     if r["proposal"] in scored else None, "reason": r["reason"],
                     "criteria_version": c["version"], "facts_file": str(args.facts),
                     "user_id": args.user, "timestamp": now}
            f.write(json.dumps(entry) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--criteria", default=HERE / "criteria.v1.json")
    ap.add_argument("--facts", default=HERE / "sample_facts.json")
    ap.add_argument("--breakdown", action="store_true")
    ap.add_argument("--audit-log", default=HERE / "out" / "audit_log.jsonl",
                    help="append one scoring entry per proposal here (same log extract.py writes to)")
    ap.add_argument("--user", default=None, help="reviewer ID recorded in the audit log (no login in the prototype)")
    args = ap.parse_args()
    c = json.loads(Path(args.criteria).read_text(encoding="utf-8"))
    facts = {k: v for k, v in json.loads(Path(args.facts).read_text(encoding="utf-8")).items() if not k.startswith("_")}
    rows, scored, order = rank(facts, c)
    write_audit(Path(args.audit_log), rows, scored, c, args)

    if args.breakdown:
        cols = list(c["weights"])
        print(f"Criteria version {c['version']}")
        print("proposal | " + " | ".join(f"{k} ({c['weights'][k]}%)" for k in cols) + " | total")
        for p in order:
            s, total = scored[p]
            print(f"{p} | " + " | ".join(f"{s[k]:.0f}" for k in cols) + f" | {total}")
        for r in rows:
            if r["status"] != "ranked":
                print(f"{r['proposal']} | {r['status']}: {r['reason']}")
        if not order:
            print("No eligible proposals. The tool does not force a winner.")
        return
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
