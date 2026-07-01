"""Humanized input controller.

Wraps ``pydirectinput`` (scancode-based, required for DirectX games) for key
presses, clicks, and typing, adding gaussian timing jitter and a small random
target radius so actions don't look mechanical. On non-Windows / when
``pydirectinput`` is unavailable, or in dry-run mode, it logs intended actions
instead of sending them — so the whole pipeline runs on Linux for testing.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Optional, Tuple

from .events import EventBus


def _load_backend():
    try:
        import pydirectinput  # type: ignore

        pydirectinput.PAUSE = 0  # we manage our own delays
        return pydirectinput
    except Exception:
        return None


class InputController:
    def __init__(self, bus: Optional[EventBus] = None, dry_run: bool = True,
                 delay_jitter: float = 0.15, click_radius: int = 4):
        self.bus = bus
        self.dry_run = dry_run
        self.delay_jitter = delay_jitter
        self.click_radius = click_radius
        # Serializes actions so the fishing loop and the chat watcher (separate
        # threads sharing one controller) never interleave a click with typing.
        self.lock = threading.RLock()
        self._backend = None if dry_run else _load_backend()
        if not dry_run and self._backend is None:
            self.dry_run = True  # no backend -> degrade to logging
            self._log("pydirectinput unavailable; forcing dry-run input")

    # -- internals ----------------------------------------------------------
    def _log(self, message: str) -> None:
        if self.bus:
            self.bus.log(message, level="debug")

    def _jitter(self, base: float) -> float:
        if self.delay_jitter <= 0:
            return max(0.0, base)
        return max(0.0, random.gauss(base, self.delay_jitter * base))

    def _radius_offset(self, x: int, y: int) -> Tuple[int, int]:
        if self.click_radius <= 0:
            return x, y
        return (x + random.randint(-self.click_radius, self.click_radius),
                y + random.randint(-self.click_radius, self.click_radius))

    def sleep(self, seconds: float) -> None:
        time.sleep(self._jitter(seconds))

    # -- public actions -----------------------------------------------------
    def press_key(self, key: str) -> None:
        with self.lock:
            self._log(f"key: {key}")
            if not self.dry_run and self._backend:
                self._backend.press(key)

    def click(self, x: int, y: int, button: str = "left") -> None:
        with self.lock:
            jx, jy = self._radius_offset(x, y)
            self._log(f"click {button} @ ({jx},{jy})")
            if not self.dry_run and self._backend:
                self._backend.click(jx, jy, button=button)

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def move_to(self, x: int, y: int) -> None:
        with self.lock:
            jx, jy = self._radius_offset(x, y)
            self._log(f"move @ ({jx},{jy})")
            if not self.dry_run and self._backend:
                self._backend.moveTo(jx, jy)

    def drag(self, sx: int, sy: int, dx: int, dy: int) -> None:
        with self.lock:
            self._log(f"drag ({sx},{sy}) -> ({dx},{dy})")
            if not self.dry_run and self._backend:
                self._backend.moveTo(sx, sy)
                self._backend.dragTo(dx, dy, button="left")

    def type_text(self, text: str, per_char: float = 0.05) -> None:
        with self.lock:
            self._log(f"type: {text!r}")
            if self.dry_run or not self._backend:
                return
            for ch in text:
                self._backend.typewrite(ch)
                time.sleep(self._jitter(per_char))

    def press_enter(self) -> None:
        self.press_key("enter")
