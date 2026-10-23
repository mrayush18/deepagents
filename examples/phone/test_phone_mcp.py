"""Offline tests of the phone MCP server: a fake Android phone, tools called in-process.
The same file runs in every repo that carries phone_mcp.py."""

import asyncio
import importlib.util
import io
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("mcp")
HERE = Path(__file__).resolve().parent
SERVER = next(p for p in (HERE / "phone_mcp.py", HERE.parent / "phone_mcp.py", HERE.parent / "tools" / "phone_mcp.py")
              if p.exists())


def load(monkeypatch, read_only=False):
    monkeypatch.setenv("PHONE_READ_ONLY", "1" if read_only else "0")
    spec = importlib.util.spec_from_file_location(f"phone_mcp_{read_only}", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    agent = mod.phone_agent
    monkeypatch.setattr(agent, "SETTLE", 0)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)

    class FakeAndroid(agent.Android):
        def __init__(self):
            super().__init__()
            self.commands = []

        def adb(self, *args, binary=False):
            if args[:2] == ("exec-out", "screencap"):
                buf = io.BytesIO()
                Image.new("RGB", (1080, 2400), "white").save(buf, "PNG")
                return buf.getvalue()
            self.commands.append(args[1])
            return ""

    monkeypatch.setattr(agent, "connect", FakeAndroid)
    mod._device = None
    return mod


def call(mod, name, args):
    return asyncio.run(mod.server.call_tool(name, args))


def names(mod):
    return {t.name for t in asyncio.run(mod.server.list_tools())}


def test_screenshot_then_tap_in_screenshot_pixels(monkeypatch):
    mod = load(monkeypatch)
    shot = call(mod, "phone_screenshot", {})
    assert shot.content[0].type == "image" and shot.content[0].mime_type == "image/png"
    assert call(mod, "phone_tap", {"x": 288, "y": 640}).content[0].text == "OK"
    call(mod, "phone_type", {"text": "hi"})
    assert mod._device.commands == ["input tap 540 1200", "input text hi"]


def test_read_only_server_has_no_typing_tools(monkeypatch):
    full, read_only = names(load(monkeypatch)), names(load(monkeypatch, read_only=True))
    assert {"phone_type", "phone_key", "phone_swipe"} <= full
    assert not {"phone_type", "phone_key", "phone_swipe"} & read_only
    assert {"phone_screenshot", "phone_tap", "phone_scroll", "phone_task"} <= read_only
    with pytest.raises(Exception, match="read only"):
        call(load(monkeypatch, read_only=True), "phone_task", {"task": "send hi", "read_only": False})


def test_errors_reach_the_client_as_text(monkeypatch):
    """A ToolError's text goes back to the client; any other exception would be hidden by the SDK."""
    mod = load(monkeypatch)
    with pytest.raises(mod.ToolError, match="ValueError: direction must be"):
        call(mod, "phone_scroll", {"direction": "sideways"})
