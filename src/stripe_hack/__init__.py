import argparse

from . import agent, audit
from .policy import Request

DEMO = [
    Request("aws", 120, "cloud", "Monthly compute"),
    Request("github", 45, "software", "Team seats"),
    Request("wework", 350, "office", "Desk block (over approval threshold)"),
    Request("shadycorp", 90, "software", "Unknown vendor"),
    Request("notion", 900, "software", "Annual plan (over hard limit)"),
    Request("aws", 450, "cloud", "GPU burst (would breach daily limit)"),
]


def main() -> None:
    p = argparse.ArgumentParser(prog="stripe-hack")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spend", help="free-text spend request, e.g. 'pay AWS £120 for compute'")
    s.add_argument("text")
    s.add_argument("--dry-run", action="store_true")
    d = sub.add_parser("demo", help="run scripted scenarios")
    d.add_argument("--dry-run", action="store_true")
    sub.add_parser("setup", help="create test supplier accounts + fund balance")
    sub.add_parser("pending", help="list escalated requests awaiting a human")
    for name in ("approve", "reject"):
        x = sub.add_parser(name, help=f"{name} a pending decision")
        x.add_argument("decision_id")
        x.add_argument("--as", dest="by", required=True, help="who is deciding")
        x.add_argument("--note", default="")
    sub.add_parser("report", help="print the audit trail")
    a = p.parse_args()
    if a.cmd == "spend":
        print(audit.explain(agent.handle(agent.parse(a.text), a.dry_run)))
    elif a.cmd == "demo":
        for r in DEMO:
            print(audit.explain(agent.handle(r, dry_run=a.dry_run)), "\n")
    elif a.cmd == "pending":
        items = audit.pending()
        for e in items:
            r = e["request"]
            print(f"{e['decision_id']}  £{r['amount']:.2f} -> {r['vendor']}  ({r['reason']})")
        print("" if items else "No pending approvals.")
    elif a.cmd in ("approve", "reject"):
        print(audit.explain(agent.resolve(a.decision_id, a.by, a.cmd == "approve", a.note)))
    elif a.cmd == "setup":
        from . import payments
        from .policy import load_policy
        print(payments.setup(list(load_policy()["vendors"])))
    else:
        for e in audit.read():
            print(audit.explain(e), "\n")
