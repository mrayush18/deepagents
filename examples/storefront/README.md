# Storefront example

A minimal Stripe Checkout storefront for selling deep-agent services, with an
append-only ledger that tracks orders, costs and profit.

It runs in **test mode** by default and refuses live keys unless
`ALLOW_LIVE_KEYS=1` is set.

## Setup

1. Create your own Stripe account at stripe.com (this must be done by the
   account owner) and stay in test mode.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your test keys as environment variables (never commit them):
   ```bash
   export STRIPE_SECRET_KEY=sk_test_...      # or a restricted rk_test_ key
   export STRIPE_WEBHOOK_SECRET=whsec_...    # printed by `stripe listen`
   ```
4. Run the app and forward webhooks with the Stripe CLI:
   ```bash
   python app.py
   stripe listen --forward-to localhost:4242/webhook
   ```
5. Open http://localhost:4242 and pay with test card `4242 4242 4242 4242`.

## Products

Edit `products.json` to change what you sell and the prices (in cents).

## Ledger

Paid orders are written to `ledger.csv` by the webhook. Each Checkout Session
is recorded once, even when Stripe retries the webhook.

```bash
python ledger.py cost 9.00 "hosting"   # record a cost
python ledger.py summary               # orders, sales, costs, profit
```

## Tests

```bash
pip install pytest
pytest test_storefront.py
```

The tests run offline and need no Stripe account.
