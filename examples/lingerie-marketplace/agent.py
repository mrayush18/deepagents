"""Lingerie marketplace: a buyer agent for shoppers and a seller agent for the shop owner.

Both agents share one store (store.json). Sensitive actions pause for a human
to approve: placing an order (buyer), and changing a price or cancelling an
order (seller).

Examples:
    python agent.py buyer
    python agent.py seller "Which products are running low?"
"""

from __future__ import annotations

import argparse
import os
import shutil
import uuid
from pathlib import Path

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel

from store import Store
from tools import buyer_tools, seller_tools

load_dotenv()

BASE_DIR = Path(__file__).parent
DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"
APPROVALS = {
    "buyer": {"place_order": {"allowed_decisions": ["approve", "reject"]}},
    "seller": {
        "set_price": {"allowed_decisions": ["approve", "reject"]},
        "cancel_order": {"allowed_decisions": ["approve", "reject"]},
    },
}

console = Console()


def open_store(path: Path = BASE_DIR / "store.json") -> Store:
    """Open the shared store, creating it from the seed catalog on first run."""
    if not path.exists():
        shutil.copy(BASE_DIR / "seed_store.json", path)
    return Store(path)


def create_marketplace_agent(role: str, store: Store, model: str | BaseChatModel | None = None) -> CompiledStateGraph:
    """Build the buyer or seller deep agent.

    Args:
        role: `buyer` for the shopping assistant or `seller` for the shop operations assistant.
        store: The store both agents read and write.
        model: Chat model or `provider:model` string; defaults to the `MODEL` env var.

    Raises:
        ValueError: If `role` is not `buyer` or `seller`.
    """
    if role not in APPROVALS:
        msg = f"Unknown role {role!r}; use 'buyer' or 'seller'."
        raise ValueError(msg)
    tools = buyer_tools(store) if role == "buyer" else seller_tools(store)
    return create_deep_agent(
        model=model or os.environ.get("MODEL", DEFAULT_MODEL),
        tools=tools,
        system_prompt=(BASE_DIR / "prompts" / f"{role}.md").read_text(),
        interrupt_on=APPROVALS[role],
        checkpointer=InMemorySaver(),
        name=f"lingerie-{role}",
    )


def _ask_approval(interrupt_value: dict) -> dict:
    """Show each pending action and collect approve/reject decisions from the human."""
    decisions = []
    for request in interrupt_value["action_requests"]:
        console.print(Panel(f"{request['name']}({request['args']})", title="Approval needed", border_style="yellow"))
        answer = console.input("Approve? [y/N] ").strip().lower()
        decisions.append({"type": "approve" if answer in {"y", "yes"} else "reject"})
    return {"decisions": decisions}


def run_turn(agent: CompiledStateGraph, thread_id: str, message: str) -> str:
    """Send one message, resolving any approval pauses, and return the agent's reply."""
    config = {"configurable": {"thread_id": thread_id}}
    payload: dict | Command = {"messages": [{"role": "user", "content": message}]}
    while True:
        result = agent.invoke(payload, config=config)
        interrupts = agent.get_state(config).interrupts
        if not interrupts:
            return result["messages"][-1].content
        payload = Command(resume=_ask_approval(interrupts[0].value))


def main() -> None:
    """Run a chat session with the chosen agent."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("role", choices=["buyer", "seller"])
    parser.add_argument("message", nargs="?", help="Send one message and exit instead of chatting.")
    args = parser.parse_args()

    agent = create_marketplace_agent(args.role, open_store())
    thread_id = str(uuid.uuid4())
    message = args.message or console.input(f"[bold cyan]{args.role}>[/bold cyan] ")
    while message.strip().lower() not in {"", "exit", "quit"}:
        console.print(Panel(run_turn(agent, thread_id, message), border_style="green"))
        if args.message:
            break
        message = console.input(f"[bold cyan]{args.role}>[/bold cyan] ")


if __name__ == "__main__":
    main()
