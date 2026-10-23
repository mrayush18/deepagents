"""Offline tests of the phone sub-agent: fake Android (no adb), fake iPhone (no WebDriverAgent), and a
scripted fake Claude client. The same file runs in every repo that carries phone_agent.py."""

import base64
import io
from types import SimpleNamespace as NS

import pytest
from PIL import Image

try:
    from tools import phone_agent
except ImportError:
    import phone_agent


def png(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


class FakeAndroid(phone_agent.Android):
    """Records shell commands; screencap returns a 1080x2400 portrait screen."""

    def __init__(self):
        super().__init__()
        self.commands = []

    def adb(self, *args, binary=False):
        if args[:2] == ("exec-out", "screencap"):
            return png(1080, 2400)
        self.commands.append(args[1])
        return "package:com.whatsapp.w4b\npackage:com.tencent.mm\n" if "pm list" in args[1] else ""


class FakeIPhone(phone_agent.IPhone):
    """A 390x844-point iPhone with a 3x (1170x2532) screen. Records WebDriverAgent calls."""

    def __init__(self):
        super().__init__("http://wda")
        self.sid, self.calls = "S1", []

    def wda(self, method, path, body=None, session=True):
        self.calls.append((method, path, body))
        if path == "/screenshot":
            return base64.b64encode(png(1170, 2532)).decode()
        if path == "/window/size":
            return {"width": 390, "height": 844}
        return None


def call(id, name, input):
    return NS(type="tool_use", id=id, name=name, input=input, toolset_name="computer")


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(phone_agent, "SETTLE", 0)
    monkeypatch.setattr(phone_agent.time, "sleep", lambda s: None)


def sent_size(block):
    return Image.open(io.BytesIO(base64.b64decode(block["source"]["data"]))).size


def test_android_screenshot_fits_and_taps_scale_back():
    phone = FakeAndroid()
    assert sent_size(phone.screenshot()) == (576, 1280)
    phone.act("left_click", {"coordinate": [288, 640]})
    phone.act("right_click", {"coordinate": [10, 10]})
    assert phone.commands == ["input tap 540 1200", "input swipe 19 19 19 19 700"]


def test_iphone_uses_points_not_pixels():
    phone = FakeIPhone()
    assert sent_size(phone.screenshot()) == (591, 1280)
    phone.act("left_click", {"coordinate": [591, 1280]})        # bottom-right corner of the screenshot
    phone.act("type", {"text": "नमस्ते"})                       # unicode works over WebDriverAgent
    phone.act("key", {"text": "Return"})
    assert phone.calls[-3] == ("POST", "/wda/tap", {"x": 389, "y": 843})
    assert phone.calls[-2] == ("POST", "/wda/keys", {"value": list("नमस्ते")})
    assert phone.calls[-1] == ("POST", "/wda/keys", {"value": ["\n"]})
    with pytest.raises(ValueError, match="no 'back' key"):
        phone.act("key", {"text": "Escape"})


def test_android_keys_text_and_scroll():
    phone = FakeAndroid()
    phone.screenshot()
    phone.act("key", {"text": "Return", "repeat": 2})
    phone.act("key", {"text": "ctrl+a"})
    phone.act("type", {"text": "Hello, it's\nAlex"})
    phone.act("scroll", {"scroll_direction": "down", "scroll_amount": 3})
    assert phone.commands[:3] == ["input keyevent 66", "input keyevent 66", "input keycombination 113 29"]
    assert phone.commands[3:6] == ["input text 'Hello,%sit'\"'\"'s'", "input keyevent 66", "input text Alex"]
    _, _, x1, y1, x2, y2, _ = phone.commands[6].split()
    assert x1 == x2 and int(y1) > int(y2)                     # scrolling down swipes the finger up


def test_scroll_stays_on_screen_and_moves_the_right_way():
    """Every direction, amount and centre on two real screen sizes: both ends on screen, finger moving
    against the scroll direction."""
    for size in [(1080, 2400), (390, 844)]:
        w, h = size
        for direction in ("up", "down", "left", "right"):
            for amount in (0, 1, 3, 10, 100):
                for cx in (0, w // 2, w - 1):
                    for cy in (0, h // 2, h - 1):
                        (x1, y1), (x2, y2) = phone_agent.scroll_path(direction, amount, (cx, cy), size)
                        assert 1 <= min(x1, x2) and max(x1, x2) <= w - 2
                        assert 1 <= min(y1, y2) and max(y1, y2) <= h - 2
                        moved = {"down": y1 - y2, "up": y2 - y1, "right": x1 - x2, "left": x2 - x1}[direction]
                        assert moved > 0


def test_failed_action_skips_rest_of_batch_and_echoes_toolset(monkeypatch):
    monkeypatch.setattr(phone_agent, "ADB_KEYBOARD", False)
    phone = FakeAndroid()
    phone.screenshot()
    results = phone_agent.run_calls(phone, [call("a", "type", {"text": "नमस्ते"}),
                                            call("b", "left_click", {"coordinate": [1, 1]})])
    assert [r["toolset_name"] for r in results] == ["computer", "computer"]
    assert results[0]["is_error"] and "ADBKeyBoard" in results[0]["content"]
    assert results[1]["content"] == phone_agent.NOT_EXECUTED and phone.commands == []


def test_open_app_by_alias_search_and_bundle():
    assert FakeAndroid().open_app("WhatsApp Business") == "Opened com.whatsapp.w4b."
    assert FakeAndroid().open_app("tencent") == "Opened com.tencent.mm."
    iphone = FakeIPhone()
    assert iphone.open_app("WhatsApp") == "Opened net.whatsapp.WhatsApp."
    assert iphone.calls[-1] == ("POST", "/wda/apps/launchUnattached", {"bundleId": "net.whatsapp.WhatsApp"})


def test_read_only_switches_off_typing():
    configs = phone_agent.toolset(read_only=True)["configs"]
    assert all(not configs[m]["enabled"] for m in ("type", "key", "left_click_drag", "mouse_move"))
    assert "type" not in phone_agent.toolset(read_only=False)["configs"]


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.beta = NS(messages=NS(stream=self.stream))

    def stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.responses.pop(0))


def test_loop_runs_calls_then_returns_report():
    client = FakeClient([
        NS(stop_reason="tool_use", stop_details=None,
           content=[call("t1", "left_click", {"coordinate": [100, 200]}), call("t2", "screenshot", {})]),
        NS(stop_reason="end_turn", stop_details=None,
           content=[NS(type="text", text="Asked Jaipur Crafts for prices; waiting for reply.")]),
    ])
    phone = FakeAndroid()
    report = phone_agent.run_task("Message Jaipur Crafts", rules="Be brief.", app="WhatsApp Business",
                                  client=client, device=phone)

    assert report == "Asked Jaipur Crafts for prices; waiting for reply."
    first, second = client.requests
    assert first["tools"][0]["type"] == "computer_toolset_20260801" and "name" not in first["tools"][0]
    assert first["system"][0]["text"].endswith("Be brief.")
    assert first["messages"][0]["content"][1]["type"] == "image"            # starts from a screenshot
    results = second["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert results[0]["content"] == "OK" and results[1]["content"][0]["type"] == "image"
    assert phone.commands[0].startswith("monkey -p com.whatsapp.w4b")
