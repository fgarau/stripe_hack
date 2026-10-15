"""Deterministic spending-policy engine. Every decision names the rules and evidence."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

POLICY_PATH = Path(__file__).with_name("policy.yaml")

APPROVE, DENY, ESCALATE = "approve", "deny", "escalate"


@dataclass
class Request:
    vendor: str
    amount: float
    category: str
    reason: str = ""


@dataclass
class Decision:
    outcome: str
    rules: list[dict] = field(default_factory=list)  # [{rule, passed, evidence}]

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rules if not r["passed"]]


def load_policy(path: Path = POLICY_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def evaluate(req: Request, policy: dict, spent_today: float, vendor_spent_today: float) -> Decision:
    vendor = req.vendor.lower()
    info = policy["vendors"].get(vendor)
    rules = []

    def rule(name, passed, evidence):
        rules.append({"rule": name, "passed": passed, "evidence": evidence})

    rule("vendor_allowlist", info is not None,
         f"'{vendor}' is {'on' if info else 'not on'} the allowlist")
    rule("category_allowed", req.category in policy["allowed_categories"],
         f"category '{req.category}' vs allowed {policy['allowed_categories']}")
    if info:
        rule("category_matches_vendor", info["category"] == req.category,
             f"vendor registered as '{info['category']}', request says '{req.category}'")
    rule("positive_amount", req.amount > 0, f"amount £{req.amount:.2f}")
    rule("per_transaction_limit", req.amount <= policy["per_transaction_limit"],
         f"£{req.amount:.2f} vs limit £{policy['per_transaction_limit']:.2f}")
    rule("daily_limit", spent_today + req.amount <= policy["daily_limit"],
         f"£{spent_today:.2f} already spent + £{req.amount:.2f} vs daily limit £{policy['daily_limit']:.2f}")
    rule("vendor_daily_limit", vendor_spent_today + req.amount <= policy["vendor_daily_limit"],
         f"£{vendor_spent_today:.2f} to {vendor} today + £{req.amount:.2f} vs £{policy['vendor_daily_limit']:.2f}")

    d = Decision(APPROVE, rules)
    if d.failed:
        d.outcome = DENY
    elif req.amount > policy["approval_threshold"]:
        rule("approval_threshold", False,
             f"£{req.amount:.2f} exceeds £{policy['approval_threshold']:.2f}; human approval required")
        d.outcome = ESCALATE
    else:
        rule("approval_threshold", True,
             f"£{req.amount:.2f} within auto-approve limit £{policy['approval_threshold']:.2f}")
    return d
