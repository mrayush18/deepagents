"""JSON-backed catalog, inventory and orders shared by the buyer and seller agents.

Usage:
    python store.py mark-paid ORDER_ID   # e.g. from a payment webhook
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ORDER_STATUSES = ("awaiting_payment", "paid", "shipped", "cancelled")


class StoreError(ValueError):
    """Raised when a store operation is not allowed."""


class Store:
    """A small marketplace store persisted to a single JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def _load(self) -> dict:
        return json.loads(self.path.read_text())

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def _product(self, data: dict, product_id: str) -> dict:
        for product in data["products"]:
            if product["id"] == product_id:
                return product
        msg = f"Unknown product {product_id!r}."
        raise StoreError(msg)

    def _order(self, data: dict, order_id: str) -> dict:
        for order in data["orders"]:
            if order["id"] == order_id:
                return order
        msg = f"Unknown order {order_id!r}."
        raise StoreError(msg)

    # Catalog

    def search(
        self,
        query: str = "",
        category: str = "",
        size: str = "",
        max_price: float | None = None,
    ) -> list[dict]:
        """Return active products matching every given filter, with in-stock sizes."""
        words = query.lower().split()
        results = []
        for product in self._load()["products"]:
            text = f"{product['name']} {product['description']} {' '.join(product['tags'])}".lower()
            if not product.get("active", True) or not all(w in text for w in words):
                continue
            if category and product["category"] != category.lower():
                continue
            if max_price is not None and product["price"] > max_price:
                continue
            if size and not _in_stock(product, size=size):
                continue
            results.append(_summary(product))
        return results

    def get(self, product_id: str) -> dict:
        """Return one product with its full variant stock."""
        return self._product(self._load(), product_id)

    def add_product(self, product: dict) -> dict:
        """Add a new product. `product` needs name, category, price, description, tags and variants."""
        with self._lock:
            data = self._load()
            product = {"id": f"p-{uuid.uuid4().hex[:6]}", "active": True, **product}
            data["products"].append(product)
            self._save(data)
        return product

    def restock(self, product_id: str, size: str, color: str, quantity: int) -> dict:
        """Add stock to a variant, creating the variant if it does not exist."""
        if quantity <= 0:
            msg = "Restock quantity must be positive."
            raise StoreError(msg)
        with self._lock:
            data = self._load()
            product = self._product(data, product_id)
            variant = _variant(product, size, color, create=True)
            variant["stock"] += quantity
            self._save(data)
        return variant

    def set_price(self, product_id: str, price: float) -> dict:
        """Change a product's price."""
        if price <= 0:
            msg = "Price must be positive."
            raise StoreError(msg)
        with self._lock:
            data = self._load()
            product = self._product(data, product_id)
            product["price"] = round(price, 2)
            self._save(data)
        return _summary(product)

    def inventory(self, low_stock_below: int | None = None) -> list[dict]:
        """List every variant's stock, optionally only those below a threshold."""
        rows = []
        for product in self._load()["products"]:
            for v in product["variants"]:
                if low_stock_below is None or v["stock"] < low_stock_below:
                    rows.append({"product_id": product["id"], "name": product["name"], **v})
        return rows

    # Orders

    def place_order(self, product_id: str, size: str, color: str, quantity: int, customer_email: str) -> dict:
        """Reserve stock and create an order awaiting payment."""
        if quantity <= 0:
            msg = "Quantity must be positive."
            raise StoreError(msg)
        with self._lock:
            data = self._load()
            product = self._product(data, product_id)
            variant = _variant(product, size, color)
            if variant["stock"] < quantity:
                msg = f"Only {variant['stock']} left in size {size}, {color}."
                raise StoreError(msg)
            variant["stock"] -= quantity
            order = _new_order(product, size, color, quantity, customer_email)
            data["orders"].append(order)
            self._save(data)
        return order

    def order(self, order_id: str) -> dict:
        """Return one order."""
        return self._order(self._load(), order_id)

    def orders(self, status: str = "") -> list[dict]:
        """List orders, optionally filtered by status."""
        return [o for o in self._load()["orders"] if not status or o["status"] == status]

    def set_order_status(self, order_id: str, status: str, tracking: str = "") -> dict:
        """Move an order forward, enforcing the allowed transitions."""
        allowed = {
            "paid": {"awaiting_payment"},
            "shipped": {"paid"},
            "cancelled": {"awaiting_payment", "paid"},
        }
        with self._lock:
            data = self._load()
            order = self._order(data, order_id)
            if order["status"] not in allowed.get(status, set()):
                msg = f"Cannot change order from {order['status']} to {status}."
                raise StoreError(msg)
            if status == "cancelled":
                _release_stock(data, order)
            order["status"] = status
            order["tracking"] = tracking or order.get("tracking", "")
            order["updated_at"] = _now()
            self._save(data)
        return order

    def sales_report(self) -> dict:
        """Summarize revenue from paid and shipped orders."""
        report = {"orders": 0, "units": 0, "revenue": 0.0, "by_product": {}}
        for order in self._load()["orders"]:
            if order["status"] not in {"paid", "shipped"}:
                continue
            report["orders"] += 1
            report["units"] += order["quantity"]
            report["revenue"] = round(report["revenue"] + order["total"], 2)
            name = order["product_name"]
            report["by_product"][name] = round(report["by_product"].get(name, 0.0) + order["total"], 2)
        return report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary(product: dict) -> dict:
    sizes = sorted({v["size"] for v in product["variants"] if v["stock"] > 0})
    colors = sorted({v["color"] for v in product["variants"] if v["stock"] > 0})
    keys = ("id", "name", "category", "price", "description")
    return {**{k: product[k] for k in keys}, "sizes_in_stock": sizes, "colors_in_stock": colors}


def _in_stock(product: dict, size: str) -> bool:
    return any(v["size"].lower() == size.lower() and v["stock"] > 0 for v in product["variants"])


def _variant(product: dict, size: str, color: str, *, create: bool = False) -> dict:
    for v in product["variants"]:
        if v["size"].lower() == size.lower() and v["color"].lower() == color.lower():
            return v
    if create:
        variant = {"size": size, "color": color, "stock": 0}
        product["variants"].append(variant)
        return variant
    msg = f"{product['name']} is not available in size {size}, {color}."
    raise StoreError(msg)


def _new_order(product: dict, size: str, color: str, quantity: int, email: str) -> dict:
    return {
        "id": f"o-{uuid.uuid4().hex[:8]}",
        "product_id": product["id"],
        "product_name": product["name"],
        "size": size,
        "color": color,
        "quantity": quantity,
        "total": round(product["price"] * quantity, 2),
        "customer_email": email,
        "status": "awaiting_payment",
        "tracking": "",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _release_stock(data: dict, order: dict) -> None:
    for product in data["products"]:
        if product["id"] == order["product_id"]:
            _variant(product, order["size"], order["color"], create=True)["stock"] += order["quantity"]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "mark-paid":
        store = Store(Path(__file__).parent / "store.json")
        print(json.dumps(store.set_order_status(sys.argv[2], "paid"), indent=2))
    else:
        print(__doc__)
