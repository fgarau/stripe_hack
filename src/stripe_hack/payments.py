"""Stripe test-mode money movement. Only called after the policy engine approves."""
import json
import os
import warnings
from pathlib import Path

import stripe
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning, module="stripe")
SUPPLIERS_PATH = Path("suppliers.json")  # vendor -> connected account id (made by setup)


def client() -> stripe.StripeClient:
    load_dotenv()
    key = os.environ["STRIPE_SECRET_KEY"]
    if not key.startswith("sk_test_"):
        raise SystemExit("Refusing to run: STRIPE_SECRET_KEY is not a test-mode key.")
    return stripe.StripeClient(key)


def suppliers() -> dict[str, str]:
    return json.loads(SUPPLIERS_PATH.read_text()) if SUPPLIERS_PATH.exists() else {}


def pay(vendor: str, amount: float, currency: str, decision_id: str, reason: str) -> dict:
    """Transfer funds from the platform balance to the vendor's connected account."""
    dest = suppliers().get(vendor)
    if not dest:
        raise RuntimeError(f"No connected account for '{vendor}'. Run `stripe-hack setup`.")
    t = client().v1.transfers.create(
        {"amount": round(amount * 100), "currency": currency, "destination": dest,
         "description": f"{vendor}: {reason}"[:200],
         "metadata": {"decision_id": decision_id, "vendor": vendor, "reason": reason[:400]}},
        {"idempotency_key": decision_id},
    )
    return {"transfer": t.id, "destination": dest, "amount": t.amount, "currency": t.currency}


def setup(vendors: list[str], fund_gbp: int = 5000) -> dict[str, str]:
    """Create one test recipient account per vendor and fund the platform test balance."""
    c = client()
    accounts = suppliers()
    for v in vendors:
        if v in accounts:
            continue
        a = c.v1.accounts.create({
            "country": "GB", "email": f"{v}@example.com", "business_type": "individual",
            "controller": {"fees": {"payer": "application"}, "losses": {"payments": "application"},
                           "requirement_collection": "application", "stripe_dashboard": {"type": "none"}},
            "capabilities": {"transfers": {"requested": True}},
            "tos_acceptance": {"date": 1760000000, "ip": "8.8.8.8"},
            "business_profile": {"name": v.title(), "mcc": "5734", "product_description": "Test supplier"},
            "individual": {"first_name": "Test", "last_name": v.title(), "email": f"{v}@example.com",
                           "phone": "+442071838750", "dob": {"day": 1, "month": 1, "year": 1901},
                           "address": {"line1": "1 Test St", "city": "London", "postal_code": "EC1A 1BB", "country": "GB"}},
            "external_account": {"object": "bank_account", "country": "GB", "currency": "gbp",
                                 "routing_number": "108800", "account_number": "00012345"},
        })
        accounts[v] = a.id
    SUPPLIERS_PATH.write_text(json.dumps(accounts, indent=2))
    # Test card that lands funds straight in the available balance
    c.v1.payment_intents.create({
        "amount": fund_gbp * 100, "currency": "gbp", "payment_method": "pm_card_bypassPending",
        "confirm": True, "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"}, "description": "Fund agent test balance"})
    return accounts
