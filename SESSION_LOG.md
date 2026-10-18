# Session log

Running record of work sessions, decisions and next steps. Newest first.

## 2026-10-18

**Goal:** start earning from deep-agent services, with payments through Stripe.

**Done**
- Added `examples/storefront/`: a Stripe Checkout storefront (test mode only by
  default), a webhook that records paid orders, and a CSV ledger with an
  orders, sales, costs and profit summary. Three offline tests pass.
- Two starter products in `products.json`: a custom research agent setup ($49)
  and a research report ($25). Prices are placeholders.

**Decisions**
- The Stripe account must be created by its owner; Claude does not sign up or
  hold credentials. Keys go in environment variables or environment secrets,
  never in the repo.
- No borrowed capital; selling services that need no upfront spend.

**Next steps**
- [ ] Owner creates a Stripe account and gets test keys.
- [ ] Run the storefront end to end with a test card.
- [ ] Settle the products and prices.
- [ ] Research where to find customers (freelance platforms, fees, payout rules).
- [ ] Choose hosting before switching to live keys.
