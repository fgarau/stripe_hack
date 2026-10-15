"""Append-only JSONL audit trail: request, rules + evidence, outcome, Stripe object IDs."""
import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_PATH = Path("audit.jsonl")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(entry: dict, path: Path = AUDIT_PATH) -> dict:
    entry = {"ts": now(), **entry}
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read(path: Path = AUDIT_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def spent_today(vendor: str | None = None, path: Path = AUDIT_PATH) -> float:
    today = now()[:10]
    return sum(e["request"]["amount"] for e in read(path)
               if e["ts"][:10] == today and e.get("paid")
               and (vendor is None or e["request"]["vendor"] == vendor))


def pending(path: Path = AUDIT_PATH) -> list[dict]:
    """Escalated decisions that nobody has approved or rejected yet."""
    entries = read(path)
    resolved = {e["resolves"] for e in entries if e.get("resolves")}
    return [e for e in entries if e["outcome"] == "escalate" and e["decision_id"] not in resolved]


def explain(e: dict) -> str:
    r = e["request"]
    ref = f" (resolves {e['resolves']})" if e.get("resolves") else ""
    lines = [f"[{e['ts']}] {e['outcome'].upper()}{ref} {e['decision_id']}: £{r['amount']:.2f} to {r['vendor']} ({r['category']}) — {r['reason']}"]
    for rule in e["rules"]:
        lines.append(f"   {'✓' if rule['passed'] else '✗'} {rule['rule']}: {rule['evidence']}")
    if e.get("stripe"):
        lines.append(f"   Stripe: {e['stripe']}")
    return "\n".join(lines)
