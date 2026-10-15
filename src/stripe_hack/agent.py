"""Agent: turns a free-text spend request into a structured Request (Claude), then the
policy engine decides. The LLM never decides whether money moves."""
import json
import os
import uuid

import anthropic

from . import audit, payments
from .policy import APPROVE, Request, evaluate, load_policy

MODEL = "claude-sonnet-5-5"
TOOL = {
    "name": "submit_spend_request",
    "description": "Extract a structured spend request from the user's message.",
    "input_schema": {"type": "object", "required": ["vendor", "amount", "category", "reason"],
                     "properties": {"vendor": {"type": "string"}, "amount": {"type": "number", "description": "GBP"},
                                    "category": {"type": "string"}, "reason": {"type": "string"}}},
}


def parse(text: str) -> Request:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set; use structured args instead.")
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=300, tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": text}])
    return Request(**next(b.input for b in msg.content if b.type == "tool_use"))


def handle(req: Request, dry_run: bool = False) -> dict:
    policy = load_policy()
    vendor = req.vendor.lower()
    d = evaluate(req, policy, audit.spent_today(), audit.spent_today(vendor))
    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    outcome, stripe_info, paid = d.outcome, None, False
    if outcome == APPROVE and not dry_run:
        try:
            stripe_info = payments.pay(vendor, req.amount, policy["currency"], decision_id, req.reason)
            paid = True
        except Exception as e:  # keep the failure in the audit trail
            outcome, stripe_info = "error", {"error": str(e)}
    return audit.record({"decision_id": decision_id, "request": req.__dict__, "outcome": outcome,
                         "rules": d.rules, "stripe": stripe_info, "paid": paid})


def resolve(decision_id: str, by: str, approve: bool = True, note: str = "") -> dict:
    """Approve or reject a pending escalation. The policy is re-checked at approval time,
    and the Stripe idempotency key is the original decision id, so it can only pay once."""
    original = next((e for e in audit.pending() if e["decision_id"] == decision_id), None)
    if original is None:
        raise SystemExit(f"{decision_id} is not pending (unknown, or already resolved).")
    req = Request(**original["request"])
    policy = load_policy()
    vendor = req.vendor.lower()
    d = evaluate(req, policy, audit.spent_today(), audit.spent_today(vendor))
    outcome, stripe_info, paid = "rejected", None, False
    if not approve:
        d.rules.append({"rule": "human_review", "passed": False, "evidence": f"rejected by {by}. {note}".strip()})
    elif d.outcome == "deny":
        outcome = "deny"
        d.rules.append({"rule": "human_review", "passed": False,
                        "evidence": f"{by} approved, but hard policy limits now fail; approval cannot override them"})
    else:
        d.rules.append({"rule": "human_approval", "passed": True, "evidence": f"approved by {by}. {note}".strip()})
        try:
            stripe_info = payments.pay(vendor, req.amount, policy["currency"], decision_id, req.reason)
            outcome, paid = "approve", True
        except Exception as e:
            outcome, stripe_info = "error", {"error": str(e)}
    return audit.record({"decision_id": f"dec_{uuid.uuid4().hex[:12]}", "resolves": decision_id,
                         "approved_by": by, "request": req.__dict__, "outcome": outcome,
                         "rules": d.rules, "stripe": stripe_info, "paid": paid})
