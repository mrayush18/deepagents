"""Offline tests: no API key or network needed."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.types import Command

import sizing
from agent import create_marketplace_agent
from store import Store, StoreError

SEED = Path(__file__).parent / "seed_store.json"


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model that replays scripted messages and accepts tool binding."""

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003, ANN201, ARG002  # Test double ignores tools.
        return self


@pytest.fixture
def store(tmp_path: Path) -> Store:
    path = tmp_path / "store.json"
    shutil.copy(SEED, path)
    return Store(path)


def test_sizing() -> None:
    assert sizing.bra_size(33, 37) == "34C"
    assert sizing.bra_size(30, 30) == "30AA"
    assert sizing.brief_size(39.5) == "M"
    with pytest.raises(ValueError):
        sizing.bra_size(10, 30)


def test_search_filters_by_size_and_price(store: Store) -> None:
    results = store.search(query="lace", size="34C", max_price=60)
    assert [p["id"] for p in results] == ["p-bra03"]


def test_order_lifecycle(store: Store) -> None:
    order = store.place_order("p-bra01", "34C", "black", 2, "shopper@example.com")
    assert order["total"] == 84.0
    assert store.get("p-bra01")["variants"][7]["stock"] == 4
    with pytest.raises(StoreError, match="Cannot change order"):
        store.set_order_status(order["id"], "shipped")
    store.set_order_status(order["id"], "paid")
    store.set_order_status(order["id"], "shipped", "1Z999")
    assert store.sales_report()["revenue"] == 84.0


def test_cancel_returns_stock_and_overselling_fails(store: Store) -> None:
    order = store.place_order("p-shp01", "M", "nude", 2, "shopper@example.com")
    with pytest.raises(StoreError, match="Only 0 left"):
        store.place_order("p-shp01", "M", "nude", 1, "other@example.com")
    store.set_order_status(order["id"], "cancelled")
    stock = {(v["size"], v["color"]): v["stock"] for v in store.get("p-shp01")["variants"]}
    assert stock[("M", "nude")] == 2


def _order_call() -> AIMessage:
    args = {"product_id": "p-bri01", "size": "M", "color": "black", "quantity": 1, "customer_email": "a@example.com"}
    return AIMessage(content="", tool_calls=[{"name": "place_order", "args": args, "id": "call_1"}])


@pytest.mark.parametrize(("decision", "orders"), [("approve", 1), ("reject", 0)])
def test_buyer_order_waits_for_approval(store: Store, decision: str, orders: int) -> None:
    model = ScriptedModel(messages=iter([_order_call(), AIMessage(content="Done.")]))
    agent = create_marketplace_agent("buyer", store, model=model)
    config = {"configurable": {"thread_id": "t1"}}

    agent.invoke({"messages": [{"role": "user", "content": "Order the black hipster in M"}]}, config=config)
    assert store.orders() == []  # Paused before the tool ran.
    interrupt = agent.get_state(config).interrupts[0].value
    assert interrupt["action_requests"][0]["name"] == "place_order"

    agent.invoke(Command(resume={"decisions": [{"type": decision}]}), config=config)
    assert len(store.orders()) == orders


def test_seed_is_valid_json() -> None:
    data = json.loads(SEED.read_text())
    assert data["orders"] == []
    assert len(data["products"]) == 8
