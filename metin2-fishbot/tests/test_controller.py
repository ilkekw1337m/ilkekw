import time

import numpy as np

from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus
from metin2fishbot.remote.controller import BotController


class FakeCapture:
    origin = (0, 0)

    def __init__(self):
        self.grabs = 0

    def grab(self):
        self.grabs += 1
        return np.zeros((60, 80, 3), np.uint8)

    def screen_pos(self, x, y):
        return x, y


def _config():
    return Config({
        "window": {"backend": "mss", "title": "Metin2"},
        "fishing": {"system": "old", "bait_hotkey": "2", "cast_hotkey": "1",
                    "bait_time": 0.0, "throw_time": 0.0, "match_threshold": 0.5},
        "safety": {"emergency_hotkey": "f6", "click_cooldown": 0.0,
                   "delay_jitter": 0.0, "click_radius": 0, "max_runtime_minutes": 0,
                   "max_actions": 0, "break_every_minutes": 0,
                   "break_duration_seconds": 1},
        "regions": {"board": None, "bite": None, "piece": None,
                    "inventory": None, "chat": None},
        "puzzle": {"rows": 4, "cols": 6, "cell_size": 32},
        "templates": {"state_dir": "assets/templates/state",
                      "bite_needle": "assets/templates/strike.png"},
        "fish": {"enabled": False},
        "chat_ai": {"enabled": False},
        "runtime": {"dry_run": True, "debug": False},
    })


def _controller_with_fake_capture(monkeypatch):
    cap = FakeCapture()
    import metin2fishbot.remote.controller as controller_mod
    monkeypatch.setattr(controller_mod, "create_capture",
                        lambda *a, **k: cap)
    ctrl = BotController(_config(), bus=EventBus())
    return ctrl, cap


def test_controller_start_stop(monkeypatch):
    ctrl, cap = _controller_with_fake_capture(monkeypatch)
    assert ctrl.start() is True
    assert ctrl.is_running()
    time.sleep(0.2)
    assert cap.grabs > 0
    ctrl.stop()
    assert not ctrl.is_running()


def test_controller_pause_resume(monkeypatch):
    ctrl, _ = _controller_with_fake_capture(monkeypatch)
    ctrl.start()
    ctrl.pause()
    assert ctrl.bot.paused
    ctrl.resume()
    assert not ctrl.bot.paused
    ctrl.stop()


def test_controller_status_and_screenshot(monkeypatch):
    ctrl, _ = _controller_with_fake_capture(monkeypatch)
    # status before start
    assert ctrl.status()["running"] is False
    ctrl.start()
    time.sleep(0.15)
    st = ctrl.status()
    assert st["running"] is True
    assert "casts" in st
    shot = ctrl.screenshot()
    assert shot is not None and shot.shape == (60, 80, 3)
    ctrl.stop()
