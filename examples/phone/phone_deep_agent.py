"""A deep agent that can use the user's real phone, Android or iPhone.

The phone itself is driven by a Claude computer-use sub-agent (phone_agent.py, the same file as in
lingerie-agent and trading-agent). The deep agent plans, and hands each phone step to it as a tool.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...            # plus the phone setup in phone_agent.py's docstring
    python phone_deep_agent.py "What did Ravi last say on WhatsApp?"
    langgraph dev                           # or run it in LangGraph Studio
"""

import sys

import phone_agent
from deepagents import create_deep_agent

RULES = """You act for the phone's owner.
- Send a message, post or email only when the task gives its exact text and recipient.
- Report what you saw in full: names, numbers, dates and times as the screen shows them."""


def look_at_phone(task: str, app: str = ""):
    """Look something up on the user's phone and report it. Read only: it can tap and scroll through
    apps but cannot type or send. Give the whole task in plain words; `app` is the app to start in,
    e.g. "WhatsApp", or "" for the home screen."""
    return phone_agent.run_task(task, rules=RULES, app=app, read_only=True)


def use_phone(task: str, app: str = ""):
    """Do a task on the user's phone that needs typing or sending, and report what happened. It never
    pays, logs in or types passwords or OTPs. Give the exact text to send and who gets it."""
    return phone_agent.run_task(task, rules=RULES, app=app)


phone_instructions = """You get things done on the user's real phone (Android or iPhone).

## `look_at_phone`

Use this to read anything on the phone: messages, notifications, app screens. Prefer it whenever you
only need to look.

## `use_phone`

Use this when the phone must type or send something. Before you send anything on the user's behalf,
show the user the exact text and recipient and wait for them to agree.

Each phone call takes a minute or more, so give each one a complete task. Phone tasks run one at a
time: there is only one phone."""

agent = create_deep_agent([look_at_phone, use_phone], phone_instructions)

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Summarise my unread WhatsApp chats."
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    print(result["messages"][-1].content)
