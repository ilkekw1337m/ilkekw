import threading
import time

import numpy as np

from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus
from metin2fishbot.core.input_controller import InputBroker, InputController
from metin2fishbot.core.window import WindowInfo
from metin2fishbot.remote import controller as controller_mod
from metin2fishbot.remote.controller import MultiController


class FakeCapture:
    def __init__(self, hwnd=None, origin=(0, 0)):
        self.hwnd = hwnd
        self.origin = origin
        self.focus_calls = 0

    def grab(self):
        return np.zeros((40, 40, 3), np.uint8)

    def screen_pos(self, x, y):
        return self.origin[0] + x, self.origin[1] + y

    def focus(self):
        self.focus_calls += 1


# ---- InputBroker / focus serialization ------------------------------------

def test_broker_shared_lock_serializes_two_controllers():
    broker = InputBroker(focus_settle=0)
    active = {"n": 0}
    overlap = {"hit": False}

    def make(focus_marker):
        ic = InputController(dry_run=True, broker=broker,
                             focus_fn=focus_marker)
        return ic

    def worker(ic):
        for _ in range(15):
            with ic.lock:
                active["n"] += 1
                if active["n"] > 1:
                    overlap["hit"] = True
                time.sleep(0.001)
                active["n"] -= 1

    c1 = make(lambda: None)
    c2 = make(lambda: None)
    # Both controllers share the broker lock -> same object.
    assert c1.lock is c2.lock is broker.lock

    threads = [threading.Thread(target=worker, args=(c,)) for c in (c1, c2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not overlap["hit"]


def test_focus_called_before_action():
    focused = []
    ic = InputController(dry_run=True, broker=InputBroker(focus_settle=0),
                         focus_fn=lambda: focused.append(True))
    ic.click(5, 5)
    ic.press_key("1")
    assert len(focused) == 2  # focus before each action


def test_no_focus_without_focus_fn():
    ic = InputController(dry_run=True)  # single-client, no broker/focus
    ic.click(1, 1)  # must not raise


# ---- MultiController -------------------------------------------------------

def _config():
    return Config({
        "window": {"backend": "mss", "title": "Metin2"},
        "fishing": {"system": "old", "bait_time": 0.0, "throw_time": 0.0,
                    "match_threshold": 0.5, "cast_hotkey": "1", "bait_hotkey": "2"},
        "safety": {"delay_jitter": 0.0, "click_radius": 0, "click_cooldown": 0.0,
                   "max_runtime_minutes": 0, "max_actions": 0,
                   "break_every_minutes": 0, "break_duration_seconds": 1},
        "regions": {"bite": None, "board": None, "piece": None, "inventory": None},
        "puzzle": {"rows": 4, "cols": 6},
        "fish": {"enabled": False},
        "chat_ai": {"enabled": False},
        "runtime": {"dry_run": True},
        "multiclient": {"enabled": True, "max_clients": 4, "focus_settle": 0},
    })


def test_multi_discovers_and_starts_per_window(monkeypatch):
    wins = [WindowInfo(hwnd=10, title="Metin2", rect=(0, 0, 100, 100)),
            WindowInfo(hwnd=20, title="Metin2", rect=(100, 0, 200, 100))]
    monkeypatch.setattr(controller_mod, "list_windows", lambda title: wins)
    monkeypatch.setattr(
        controller_mod, "create_capture",
        lambda *a, **k: FakeCapture(hwnd=k.get("hwnd")))

    mc = MultiController(_config(), bus=EventBus())
    assert mc.discover() == wins
    assert mc.start() is True
    assert len(mc.clients) == 2
    # Each client bound to its own window + shares the broker.
    assert mc.clients[0].window.hwnd == 10
    assert mc.clients[1].window.hwnd == 20
    assert mc.clients[0].broker is mc.broker is mc.clients[1].broker

    st = mc.status()
    assert isinstance(st, list) and len(st) == 2
    assert st[0]["index"] == 1 and st[1]["index"] == 2

    mc.pause(index=2)
    assert not mc.clients[0].bot.paused
    assert mc.clients[1].bot.paused

    mc.pause()  # all
    assert mc.clients[0].bot.paused
    mc.stop()
    assert mc.clients == []


def test_multi_respects_max_clients(monkeypatch):
    wins = [WindowInfo(hwnd=i, title="Metin2", rect=(i, 0, i + 10, 10))
            for i in range(6)]
    monkeypatch.setattr(controller_mod, "list_windows", lambda title: wins)
    cfg = _config()
    cfg.set("multiclient.max_clients", 2)
    mc = MultiController(cfg, bus=EventBus())
    assert len(mc.discover()) == 2


def test_multi_falls_back_to_single_when_no_windows(monkeypatch):
    monkeypatch.setattr(controller_mod, "list_windows", lambda title: [])
    monkeypatch.setattr(controller_mod, "create_capture",
                        lambda *a, **k: FakeCapture())
    mc = MultiController(_config(), bus=EventBus())
    assert mc.start() is True
    assert len(mc.clients) == 1  # single fallback client
    assert mc.clients[0].window is None
    mc.stop()
