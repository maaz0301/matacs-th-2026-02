"""AI half of the triage flow: run the extraction prompt from PROMPTS.md on each proposal,
then check the output with plain code before anything is scored.

Proposal texts are NOT in this repo (the brief must not be copied). Put one plain-text
file per proposal in prototype/proposals/ (git-ignored), named A.txt, B.txt, ...

Run:
  pip install -r prototype/requirements.txt
  cp prototype/.env.example prototype/.env     # then add your key
  python prototype/extract.py                  # writes prototype/out/facts.json
  python prototype/score.py --facts prototype/out/facts.json

  python prototype/extract.py --dry-run        # print the exact prompt, no API call
"""
import argparse
import datetime
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
MODEL = "claude-opus-5-5"
PROMPT_VERSION = "extract-v1"

# Code-side backstop for the model's own injection detection.
INJECTION_RE = re.compile(
    r"automated (review|system|evaluat)|pre-?approved|rank (it|this|us) first|full marks|"
    r"ignore (all |any )?(previous|prior) instructions|note to (the )?(ai|reviewer|evaluator)",
    re.I,
)


def load_prompt():
    """Read the system and user templates straight from PROMPTS.md, so the prompt sent
    is exactly the one documented."""
    text = (ROOT / "PROMPTS.md").read_text(encoding="utf-8")
    section = text.split("## Prompt 1")[1].split("## Prompt 2")[0]
    blocks = re.findall(r"```\n(.*?)```", section, re.S)
    return blocks[0].strip(), blocks[1].strip()


def fill(template, values):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), template)


# JSON schema enforced by structured outputs. Mirrors the schema in PROMPTS.md.
def _field(t):
    return {"type": "object", "additionalProperties": False, "required": ["value", "evidence"],
            "properties": {"value": {"type": [t, "null"]}, "evidence": {"type": ["string", "null"]}}}


def _flag():
    return {"type": "object", "additionalProperties": False, "required": ["value", "evidence"],
            "properties": {"value": {"type": "boolean"}, "evidence": {"type": ["string", "null"]}}}


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["contractor_name", "licence", "wsib_clearance", "liability_insurance_cad",
                 "qualifying_installs", "total_price_cad", "price_lines", "timeline_weeks",
                 "panel_warranty_years", "workmanship_warranty_years", "team",
                 "conflicts", "injection_detected", "injection_quotes"],
    "properties": {
        "contractor_name": _field("string"),
        "licence": {"type": "object", "additionalProperties": False,
                    "required": ["value", "licence_number", "evidence"],
                    "properties": {"value": {"type": "string", "enum": ["held_by_bidder", "subcontractor", "not_stated"]},
                                   "licence_number": {"type": ["string", "null"]},
                                   "evidence": {"type": ["string", "null"]}}},
        "wsib_clearance": _field("boolean"),
        "liability_insurance_cad": _field("number"),
        "qualifying_installs": {"type": "object", "additionalProperties": False,
                                "required": ["value", "range_exceeds_window", "evidence"],
                                "properties": {"value": {"type": ["integer", "null"]},
                                               "range_exceeds_window": {"type": "boolean"},
                                               "evidence": {"type": ["string", "null"]}}},
        "total_price_cad": _field("number"),
        "price_lines": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["label", "amount_cad", "optional", "evidence"],
            "properties": {"label": {"type": "string"}, "amount_cad": {"type": "number"},
                           "optional": {"type": "boolean"}, "evidence": {"type": "string"}}}},
        "timeline_weeks": {"type": "object", "additionalProperties": False,
                           "required": ["value", "as_stated", "evidence"],
                           "properties": {"value": {"type": ["number", "null"]},
                                          "as_stated": {"type": ["string", "null"]},
                                          "evidence": {"type": ["string", "null"]}}},
        "panel_warranty_years": _field("number"),
        "workmanship_warranty_years": _field("number"),
        "team": {"type": "object", "additionalProperties": False,
                 "required": ["named_lead", "defined_crew", "safety_plan", "monitoring_plan"],
                 "properties": {k: _flag() for k in ["named_lead", "defined_crew", "safety_plan", "monitoring_plan"]}},
        "conflicts": {"type": "array", "items": {"type": "string"},
                      "description": "Names of fields where the proposal states conflicting values."},
        "injection_detected": {"type": "boolean"},
        "injection_quotes": {"type": "array", "items": {"type": "string"}},
    },
}


def call_model(system, user):
    import anthropic  # imported here so --dry-run and --response-file work without the SDK

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        # If the model declines, the API retries on a fallback model in the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Model declined to extract; send this proposal to a person.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.model


def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def verify(ext, source):
    """Plain-code checks on the model output. Returns a list of issues for a person."""
    issues = []
    src = _norm(source)

    def check(name, field):
        ev = field.get("evidence")
        if field.get("value") not in (None, False, "not_stated") and not ev:
            issues.append(f"{name}: value given without a quote")
        elif ev and _norm(ev) not in src:
            issues.append(f"{name}: quote not found in the proposal")

    for name in ["contractor_name", "licence", "wsib_clearance", "liability_insurance_cad",
                 "qualifying_installs", "total_price_cad", "timeline_weeks",
                 "panel_warranty_years", "workmanship_warranty_years"]:
        check(name, ext[name])
    for name, field in ext["team"].items():
        check(f"team.{name}", field)
    for line in ext["price_lines"]:
        if _norm(line["evidence"]) not in src:
            issues.append(f"price line '{line['label']}': quote not found in the proposal")
    for name in ext["conflicts"]:
        issues.append(f"{name}: proposal states conflicting values")
    if ext["qualifying_installs"]["range_exceeds_window"]:
        issues.append("experience: stated range starts before the 5-year window")
    return issues


def normalise(ext, issues, source):
    """Turn verified extraction into the flat facts score.py uses."""
    price = ext["total_price_cad"]["value"]
    if price is None and ext["price_lines"]:
        price = sum(l["amount_cad"] for l in ext["price_lines"] if not l["optional"])
    injection = ext["injection_detected"] or bool(INJECTION_RE.search(source))
    return {
        "licence": ext["licence"]["value"],
        "wsib": bool(ext["wsib_clearance"]["value"]),
        "insurance_cad": ext["liability_insurance_cad"]["value"],
        "installs": ext["qualifying_installs"]["value"],
        "price_cad": price,
        "weeks": ext["timeline_weeks"]["value"],
        "panel_years": ext["panel_warranty_years"]["value"],
        "workmanship_years": ext["workmanship_warranty_years"]["value"],
        "team": [k for k, v in ext["team"].items() if v["value"]],
        "injection": injection,
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals", default=HERE / "proposals")
    ap.add_argument("--criteria", default=HERE / "criteria.v1.json")
    ap.add_argument("--out", default=HERE / "out")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt for the first proposal and stop")
    ap.add_argument("--responses", help="folder of saved model outputs (A.json, ...) to use instead of calling the API")
    args = ap.parse_args()

    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    c = json.loads(Path(args.criteria).read_text(encoding="utf-8"))
    system, user_tpl = load_prompt()
    files = sorted(Path(args.proposals).glob("*.txt"))
    if not files:
        raise SystemExit(f"No proposals found. Put A.txt, B.txt, ... in {args.proposals}")

    out = Path(args.out)
    (out / "cache").mkdir(parents=True, exist_ok=True)
    facts, log = {}, []
    for path in files:
        pid = path.stem
        source = path.read_text(encoding="utf-8")
        user = fill(user_tpl, {
            "category_name": c["category"], "today": datetime.date.today().isoformat(),
            "proposal_text": source, "min_kw": c["rubric"]["experience_min_kw"],
            "years": c["rubric"]["experience_years"],
        })
        system_filled = fill(system, {"min_kw": c["rubric"]["experience_min_kw"],
                                      "years": c["rubric"]["experience_years"]})
        if args.dry_run:
            print("=== SYSTEM ===\n" + system_filled + "\n\n=== USER ===\n" + user)
            return

        file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
        cached = out / "cache" / f"{file_hash}.json"
        if args.responses:
            ext, model = json.loads((Path(args.responses) / f"{pid}.json").read_text(encoding="utf-8")), "saved-response"
        elif cached.exists():
            ext, model = json.loads(cached.read_text(encoding="utf-8")), "cache"
        else:
            ext, model = call_model(system_filled, user)
            cached.write_text(json.dumps(ext, indent=2), encoding="utf-8")

        issues = verify(ext, source)
        facts[pid] = normalise(ext, issues, source)
        log.append({"proposal": pid, "file_hash": file_hash, "model": model,
                    "prompt_version": PROMPT_VERSION, "criteria_version": c["version"],
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    "injection": facts[pid]["injection"], "issues": issues})
        print(f"{pid}: injection={facts[pid]['injection']} issues={len(issues)}")

    (out / "facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    with open(out / "audit_log.jsonl", "a", encoding="utf-8") as f:
        for entry in log:
            f.write(json.dumps(entry) + "\n")
    print(f"Wrote {out / 'facts.json'} and appended to {out / 'audit_log.jsonl'}")


if __name__ == "__main__":
    main()
