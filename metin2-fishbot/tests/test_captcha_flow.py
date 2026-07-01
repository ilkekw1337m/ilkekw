import numpy as np

from metin2fishbot.bot.fishing_bot import FishingBot
from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus


def _icon(color, size=16):
    icon = np.zeros((size, size, 3), np.uint8)
    icon[:] = color
    icon[0, 0] = (0, 0, 0)
    icon[-1, -1] = (255, 255, 255)
    return icon


def _config():
    return Config({
        "window": {"backend": "mss"},
        "fishing": {"system": "old", "match_threshold": 0.6, "bait_time": 0.0,
                    "throw_time": 0.0, "cast_hotkey": "1", "bait_hotkey": "2"},
        "safety": {"delay_jitter": 0.0, "click_radius": 0, "click_cooldown": 0.0,
                   "max_runtime_minutes": 0, "max_actions": 0,
                   "break_every_minutes": 0, "break_duration_seconds": 1},
        "regions": {"bite": None, "board": None, "piece": None,
                    "inventory": None},
        "puzzle": {"rows": 4, "cols": 6},
        "fish": {"enabled": False},
        "runtime": {"dry_run": True, "debug": False},
    })


def test_captcha_detection_pauses_and_publishes():
    captcha_tpl = _icon((0, 200, 0))
    bot = FishingBot(_config(), bus=EventBus())
    # Inject a captcha template directly (no assets needed).
    bot.state_detector.templates["captcha"] = captcha_tpl

    events = []
    bot.bus.subscribe(lambda e: events.append(e.type))

    # A frame containing the captcha icon.
    frame = np.zeros((60, 80, 3), np.uint8)
    frame[10:26, 20:36] = captcha_tpl

    assert bot._check_captcha(frame) is True
    assert bot.paused
    assert bot.stats["captchas"] == 1
    assert "captcha" in events

    # A clean frame clears the flag and resumes.
    clean = np.zeros((60, 80, 3), np.uint8)
    assert bot._check_captcha(clean) is False
    assert not bot.paused


def test_no_captcha_template_is_noop():
    bot = FishingBot(_config(), bus=EventBus())
    frame = np.zeros((60, 80, 3), np.uint8)
    # No captcha template loaded -> never flags.
    assert bot._check_captcha(frame) is False
    assert not bot.paused
