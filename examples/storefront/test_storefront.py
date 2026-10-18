"""Offline tests: no Stripe account or network needed."""

import json
import os
import tempfile
import time

os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
os.environ["LEDGER_PATH"] = os.path.join(tempfile.mkdtemp(), "ledger.csv")

import stripe  # noqa: E402

import app as storefront  # noqa: E402
import ledger  # noqa: E402


def _signed(payload):
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload}", "whsec_test_secret")
    return {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def _completed_event(session_id):
    return json.dumps({
        "id": "evt_1", "object": "event", "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id, "object": "checkout.session", "payment_status": "paid",
            "amount_total": 4900, "currency": "usd", "metadata": {"product_id": "agent-setup"},
        }},
    })


def test_storefront_lists_products():
    resp = storefront.app.test_client().get("/")
    assert resp.status_code == 200
    assert b"Custom research agent setup" in resp.data


def test_webhook_rejects_bad_signature():
    client = storefront.app.test_client()
    resp = client.post("/webhook", data=_completed_event("cs_bad"), headers={"Stripe-Signature": "t=1,v1=nope"})
    assert resp.status_code == 400


def test_paid_webhook_records_sale_once():
    client = storefront.app.test_client()
    payload = _completed_event("cs_test_123")
    assert client.post("/webhook", data=payload, headers=_signed(payload)).status_code == 200
    # Stripe retries webhooks; the same session must not be counted twice.
    assert client.post("/webhook", data=payload, headers=_signed(payload)).status_code == 200
    ledger.record_cost("9.00", "hosting")
    totals = ledger.summary()["usd"]
    assert totals["orders"] == 1
    assert totals["sales"] == 49.0
    assert totals["profit"] == 40.0
