# stripe_hack — a spending agent that can explain every pound

Briefcase × Stripe hackathon, Track 01 (Agents that Spend). Stripe **test mode only**.

An agent receives spend requests, checks them against a **written policy**
([`policy.yaml`](src/stripe_hack/policy.yaml)), moves real test-mode money with Stripe
Transfers only when the policy allows it, and records an **audit trail** of the rule and
evidence behind every decision.

## Design

- **The LLM never decides whether money moves.** Claude only turns free text
  ("pay AWS £120 for compute") into a structured request. A deterministic policy engine
  (`policy.py`) approves, denies or escalates.
- **Rules, each with evidence:** vendor allowlist, allowed category, category matches the
  vendor, positive amount, per-transaction limit, daily limit, per-vendor daily limit,
  human-approval threshold.
- **Escalation queue:** requests above the approval threshold wait in `pending`. A named
  person runs `approve` or `reject`. The policy is re-checked at approval time and
  approval cannot override hard limits.
- **Safe by construction:** refuses non-`sk_test_` keys; Stripe idempotency key = decision id,
  so a decision can only pay once.
- **Audit trail:** append-only `audit.jsonl`; each paid decision links to its Stripe transfer id,
  and the transfer's metadata links back to the decision id.

## Run it

```
uv sync
cp .env.example .env          # add your sk_test_ key
uv run stripe-hack setup      # test supplier accounts (Connect) + fund test balance
uv run stripe-hack demo       # scripted approve / deny / escalate scenarios
uv run stripe-hack pending
uv run stripe-hack approve <decision_id> --as <name> --note "why"
uv run stripe-hack reject  <decision_id> --as <name>
uv run stripe-hack report     # full audit trail
uv run stripe-hack spend "pay AWS £120 for compute"   # needs ANTHROPIC_API_KEY
```

`setup` needs Connect enabled on the sandbox and the platform-profile loss-liability
terms accepted (https://dashboard.stripe.com/settings/connect/platform-profile).
Delete `audit.jsonl` to reset daily limits.
