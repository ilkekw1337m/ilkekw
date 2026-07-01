import numpy as np

from metin2fishbot.bot.fishing_bot import FishingBot
from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus


def _config(system, **regions):
    r = {"bite": None, "board": None, "piece": None, "inventory": None}
    r.update(regions)
    return Config({
        "window": {"backend": "mss"},
        "fishing": {"system": system, "match_threshold": 0.6},
        "safety": {},
        "regions": r,
        "puzzle": {"rows": 4, "cols": 6},
        "fish": {"enabled": False},
        "runtime": {"dry_run": True},
    })


def test_preflight_flags_missing_old_system():
    bot = FishingBot(_config("old"), bus=EventBus())
    published = []
    bot.bus.subscribe(lambda e: published.append(e)
                      if e.type == "preflight" else None)
    issues = bot._preflight_check()
    # no bite template + no bite region -> at least 2 issues
    assert any("strike" in i for i in issues)
    assert any("bite" in i for i in issues)
    assert published and published[0].payload["issues"]


def test_preflight_new_system_needs_board_and_piece():
    bot = FishingBot(_config("new"), bus=EventBus())
    issues = bot._preflight_check()
    assert any("board" in i for i in issues)
    assert any("piece" in i for i in issues)


def test_preflight_clean_when_calibrated():
    bot = FishingBot(_config("new", board=[0, 0, 10, 10],
                             piece=[0, 0, 5, 5]), bus=EventBus())
    assert bot._preflight_check() == []


def test_bite_needle_autoload(tmp_path, monkeypatch):
    import cv2
    import metin2fishbot.bot.fishing_bot as fb

    needle = np.zeros((10, 10, 3), np.uint8)
    needle[:] = (0, 0, 255)
    strike_path = tmp_path / "strike.png"
    cv2.imwrite(str(strike_path), needle)

    cfg = _config("old")
    cfg.set("templates.bite_needle", str(strike_path))
    # resolve_path returns absolute path unchanged for absolute inputs.
    bot = FishingBot(cfg, bus=EventBus())
    assert bot.bite_detector is None
    bot._load_bite_needle()
    assert bot.bite_detector is not None
