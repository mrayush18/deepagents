"""Minimal Stripe Checkout storefront that records paid orders in ledger.csv.

Runs in test mode only unless ALLOW_LIVE_KEYS=1 is set.
"""

import json
import os

import stripe
from flask import Flask, abort, redirect, render_template_string, request

import ledger

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:4242")

# Refuse live keys by default so nothing charges real cards by accident.
if STRIPE_SECRET_KEY and not STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
    if os.environ.get("ALLOW_LIVE_KEYS") != "1":
        raise SystemExit("Live Stripe key detected. Set ALLOW_LIVE_KEYS=1 to use it on purpose.")

stripe.api_key = STRIPE_SECRET_KEY

with open(os.path.join(os.path.dirname(__file__), "products.json")) as f:
    PRODUCTS = {p["id"]: p for p in json.load(f)}

app = Flask(__name__)

PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storefront</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 16px; }
  .p { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
  button { padding: .5rem 1rem; cursor: pointer; }
</style>
<h1>Storefront</h1>
{% if message %}<p><strong>{{ message }}</strong></p>{% endif %}
{% for p in products %}
<div class="p">
  <h2>{{ p.name }}</h2>
  <p>{{ p.description }}</p>
  <form method="post" action="/checkout">
    <input type="hidden" name="product_id" value="{{ p.id }}">
    <button>Buy for {{ "%.2f"|format(p.price_cents / 100) }} {{ p.currency|upper }}</button>
  </form>
</div>
{% endfor %}
"""


@app.get("/")
def index():
    return render_template_string(PAGE, products=PRODUCTS.values(), message=None)


@app.post("/checkout")
def checkout():
    product = PRODUCTS.get(request.form.get("product_id", ""))
    if not product:
        abort(400)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": product["currency"],
                "unit_amount": product["price_cents"],
                "product_data": {"name": product["name"]},
            },
        }],
        metadata={"product_id": product["id"]},
        success_url=f"{BASE_URL}/success",
        cancel_url=f"{BASE_URL}/",
    )
    return redirect(session.url, code=303)


@app.get("/success")
def success():
    return render_template_string(
        PAGE, products=PRODUCTS.values(),
        message="Thanks! Your payment went through and your order is being prepared.",
    )


@app.post("/webhook")
def webhook():
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature", ""), STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError):
        abort(400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"].to_dict()
        if session.get("payment_status") == "paid":
            product = PRODUCTS.get((session.get("metadata") or {}).get("product_id"), {})
            ledger.record_sale(
                ref=session["id"],
                description=product.get("name", "unknown product"),
                amount_cents=session["amount_total"],
                currency=session["currency"],
            )
    return "", 200


if __name__ == "__main__":
    app.run(port=4242)
