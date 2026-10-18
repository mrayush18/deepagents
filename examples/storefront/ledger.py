"""Append-only CSV ledger for sales and costs.

Usage:
    python ledger.py summary
    python ledger.py cost 12.50 "domain name"
"""

import csv
import os
import sys
from datetime import datetime, timezone

LEDGER_PATH = os.environ.get("LEDGER_PATH", os.path.join(os.path.dirname(__file__), "ledger.csv"))
FIELDS = ["timestamp", "kind", "ref", "description", "amount", "currency"]


def _rows():
    if not os.path.exists(LEDGER_PATH):
        return []
    with open(LEDGER_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _append(row):
    new_file = not os.path.exists(LEDGER_PATH)
    with open(LEDGER_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def record_sale(ref, description, amount_cents, currency):
    """Record a paid order. Returns False if `ref` was already recorded (webhook retries)."""
    if any(r["ref"] == ref for r in _rows()):
        return False
    _append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "sale",
        "ref": ref,
        "description": description,
        "amount": f"{amount_cents / 100:.2f}",
        "currency": currency.lower(),
    })
    return True


def record_cost(amount, description, currency="usd"):
    _append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "cost",
        "ref": "",
        "description": description,
        "amount": f"{float(amount):.2f}",
        "currency": currency.lower(),
    })


def summary():
    totals = {}
    for r in _rows():
        t = totals.setdefault(r["currency"], {"sales": 0.0, "costs": 0.0, "orders": 0})
        if r["kind"] == "sale":
            t["sales"] += float(r["amount"])
            t["orders"] += 1
        else:
            t["costs"] += float(r["amount"])
    for t in totals.values():
        t["profit"] = round(t["sales"] - t["costs"], 2)
    return totals


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "cost" and len(sys.argv) >= 4:
        record_cost(sys.argv[2], sys.argv[3])
        print("Recorded cost.")
    elif cmd == "summary":
        totals = summary()
        if not totals:
            print("No entries yet.")
        for cur, t in totals.items():
            print(f"{cur.upper()}: {t['orders']} orders, sales {t['sales']:.2f}, "
                  f"costs {t['costs']:.2f}, profit {t['profit']:.2f}")
    else:
        print(__doc__)
