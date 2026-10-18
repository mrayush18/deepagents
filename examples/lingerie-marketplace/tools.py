"""Tools for the buyer and seller agents, bound to a shared `Store`."""

from __future__ import annotations

import json
from collections.abc import Callable

from langchain_core.tools import BaseTool, tool

import sizing
from store import Store, StoreError


def _run(action: Callable[[], object]) -> str:
    """Return the action's result as JSON, or the store's error message for the agent to relay."""
    try:
        return json.dumps(action(), indent=2)
    except (StoreError, ValueError) as err:
        return f"Error: {err}"


def buyer_tools(store: Store) -> list[BaseTool]:
    """Tools a shopper's agent may use: browse, get sizing help, order, and track."""

    @tool
    def search_products(query: str = "", category: str = "", size: str = "", max_price: float | None = None) -> str:
        """Search the catalog. Category is one of: bra, brief, set, sleepwear, shapewear. Size filters to in-stock sizes."""
        return _run(lambda: store.search(query, category, size, max_price))

    @tool
    def get_product(product_id: str) -> str:
        """Get one product's details, including stock for every size and color."""
        return _run(lambda: store.get(product_id))

    @tool
    def recommend_bra_size(underbust_inches: float, bust_inches: float) -> str:
        """Estimate a starting US bra size from underbust and bust measurements in inches."""
        return _run(lambda: {"estimated_size": sizing.bra_size(underbust_inches, bust_inches)})

    @tool
    def recommend_brief_size(hip_inches: float) -> str:
        """Estimate a letter size for briefs, sets and sleepwear from the hip measurement in inches."""
        return _run(lambda: {"estimated_size": sizing.brief_size(hip_inches)})

    @tool
    def place_order(product_id: str, size: str, color: str, quantity: int, customer_email: str) -> str:
        """Place an order. Stock is reserved and the order waits for payment. Requires the shopper's approval."""
        return _run(lambda: store.place_order(product_id, size, color, quantity, customer_email))

    @tool
    def order_status(order_id: str) -> str:
        """Look up an order's status and tracking number."""
        return _run(lambda: store.order(order_id))

    return [search_products, get_product, recommend_bra_size, recommend_brief_size, place_order, order_status]


def seller_tools(store: Store) -> list[BaseTool]:
    """Tools a shop owner's agent may use: manage catalog, stock, prices and orders."""

    @tool
    def list_inventory(low_stock_below: int | None = None) -> str:
        """List stock for every size and color, optionally only variants below a threshold."""
        return _run(lambda: store.inventory(low_stock_below))

    @tool
    def add_product(name: str, category: str, price: float, description: str, tags: list[str], variants: list[dict]) -> str:
        """Add a product. Each variant is {"size": str, "color": str, "stock": int}."""
        product = {"name": name, "category": category.lower(), "price": price,
                   "description": description, "tags": tags, "variants": variants}
        return _run(lambda: store.add_product(product))

    @tool
    def restock(product_id: str, size: str, color: str, quantity: int) -> str:
        """Add stock to a size and color of a product."""
        return _run(lambda: store.restock(product_id, size, color, quantity))

    @tool
    def set_price(product_id: str, price: float) -> str:
        """Change a product's price. Requires the owner's approval."""
        return _run(lambda: store.set_price(product_id, price))

    @tool
    def list_orders(status: str = "") -> str:
        """List orders. Status is one of: awaiting_payment, paid, shipped, cancelled, or empty for all."""
        return _run(lambda: store.orders(status))

    @tool
    def ship_order(order_id: str, tracking_number: str) -> str:
        """Mark a paid order as shipped with its tracking number."""
        return _run(lambda: store.set_order_status(order_id, "shipped", tracking_number))

    @tool
    def cancel_order(order_id: str) -> str:
        """Cancel an unshipped order and return its stock. Requires the owner's approval."""
        return _run(lambda: store.set_order_status(order_id, "cancelled"))

    @tool
    def sales_report() -> str:
        """Summarize revenue from paid and shipped orders."""
        return _run(store.sales_report)

    return [list_inventory, add_product, restock, set_price, list_orders, ship_order, cancel_order, sales_report]
