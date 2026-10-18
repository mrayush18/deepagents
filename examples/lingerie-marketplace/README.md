# Lingerie marketplace agents

Two [Deep Agents](https://github.com/langchain-ai/deepagents) that share one
store:

- **Buyer agent:** a shopping assistant. It asks what the shopper wants,
  estimates bra and brief sizes from measurements, recommends in-stock
  products, and places orders.
- **Seller agent:** a shop operations assistant. It reports and restocks
  inventory, adds products, adjusts prices, ships paid orders and reports
  sales.

Built against the current `deepagents` API (`create_deep_agent` with tools,
`system_prompt`, `interrupt_on` and a checkpointer).

## Human approval

Actions that move money or change what customers pay pause until a person
approves them:

| Agent  | Needs approval               |
|--------|------------------------------|
| Buyer  | `place_order`                |
| Seller | `set_price`, `cancel_order`  |

The store also enforces the order lifecycle:
`awaiting_payment → paid → shipped`, or `cancelled` before shipping, which
returns the stock. Orders can't be shipped before they're paid.

## Setup

```bash
pip install -e .
export ANTHROPIC_API_KEY=...      # never commit keys
# optional: export MODEL=anthropic:claude-opus-5-5
```

## Run

```bash
python agent.py buyer                                    # chat as a shopper
python agent.py seller "Which products are running low?"
```

On first run, `store.json` is created from `seed_store.json` (8 sample
products). Delete `store.json` to reset.

## Payments

New orders wait for payment. Connect this to a payment provider by calling
`Store.set_order_status(order_id, "paid")` from your payment webhook (for
example the Stripe storefront example), or mark one by hand:

```bash
python store.py mark-paid o-1234abcd
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Builds both agents and runs the chat loop with approvals |
| `tools.py` | Buyer and seller tools |
| `store.py` | JSON catalog, inventory and orders |
| `sizing.py` | Bra and brief size estimates |
| `prompts/` | System prompts for each agent |
| `seed_store.json` | Sample catalog |

## Tests

```bash
pip install pytest
pytest test_marketplace.py
```

The tests run offline with a scripted model, including the approve and
reject paths for placing an order.
