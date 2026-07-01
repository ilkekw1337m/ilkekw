import time

import numpy as np

from metin2fishbot.bot.fishing_bot import FishingBot
from metin2fishbot.bot.state_machine import State, next_state
from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus


class FakeCapture:
    """Returns a black frame; records that grab() was called."""

    origin = (0, 0)

    def __init__(self):
        self.grabs = 0

    def grab(self):
        self.grabs += 1
        return np.zeros((100, 160, 3), np.uint8)

    def screen_pos(self, x, y):
        return x, y


def _fast_config():
    return Config({
        "window": {"backend": "mss", "title": "Metin2"},
        "fishing": {"system": "old", "bait_hotkey": "2", "cast_hotkey": "1",
                    "bait_time": 0.0, "throw_time": 0.0, "match_threshold": 0.5},
        "safety": {"emergency_hotkey": "f6", "click_cooldown": 0.0,
                   "delay_jitter": 0.0, "click_radius": 0,
                   "max_runtime_minutes": 0, "max_actions": 5,
                   "break_every_minutes": 0, "break_duration_seconds": 1},
        "regions": {"board": None, "bite": None, "inventory": None, "chat": None},
        "puzzle": {"rows": 4, "cols": 6, "cell_size": 32},
        "fish": {"enabled": False},
        "runtime": {"dry_run": True, "debug": False},
    })


def test_state_machine_transitions():
    assert next_state(State.EQUIP_BAIT) == State.CAST
    assert next_state(State.CAST) == State.WAIT
    assert next_state(State.HOOK) == State.LOOT
    assert next_state(State.PUZZLE) == State.LOOT
    assert next_state(State.LOOT) == State.EQUIP_BAIT


def test_bot_runs_dry_and_stops_on_action_cap():
    cfg = _fast_config()
    bus = EventBus()
    states_seen = set()
    bus.subscribe(lambda e: states_seen.add(e.payload.get("state"))
                  if e.type == "state" else None)

    cap = FakeCapture()
    bot = FishingBot(cfg, bus=bus, capture=cap)
    bot.start()
    time.sleep(0.5)   # let it cycle a few times in dry-run
    bot.stop()

    assert cap.grabs > 0
    # Old system with no bite template -> EQUIP_BAIT/CAST/WAIT/HOOK/LOOT cycle
    assert "equip_bait" in states_seen
    assert "cast" in states_seen
    assert not bot._running


def test_bot_pause_halts_and_resume_continues():
    cfg = _fast_config()
    cfg.set("safety.max_actions", 0)  # unlimited so the loop keeps running
    cap = FakeCapture()
    bot = FishingBot(cfg, bus=EventBus(), capture=cap)
    bot.start()
    time.sleep(0.2)
    bot.pause()
    assert bot.paused
    time.sleep(0.1)
    paused_at = cap.grabs
    time.sleep(0.3)
    # While paused, the loop waits in _wait_if_paused and stops grabbing.
    assert cap.grabs - paused_at <= 1
    bot.resume()
    assert not bot.paused
    time.sleep(0.2)
    assert cap.grabs > paused_at   # progress resumes
    bot.stop()
