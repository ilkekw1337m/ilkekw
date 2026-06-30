"""Safety guards: emergency stop, run/action caps, periodic breaks.

Wraps the runtime concerns that keep the bot from running away: a global
emergency-stop hotkey (via the ``keyboard`` library when available), a max
runtime / max action budget, and randomized periodic breaks to look less
mechanical. Designed to degrade gracefully where ``keyboard`` can't be used
(e.g. headless Linux) so the rest of the system stays testable.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Optional

from ..core.events import EventBus


class SafetyGuard:
    def __init__(self, bus: Optional[EventBus] = None,
                 emergency_hotkey: str = "f6",
                 max_runtime_minutes: float = 0,
                 max_actions: int = 0,
                 break_every_minutes: float = 0,
                 break_duration_seconds: float = 30):
        self.bus = bus
        self.emergency_hotkey = emergency_hotkey
        self.max_runtime = max_runtime_minutes * 60.0
        self.max_actions = max_actions
        self.break_every = break_every_minutes * 60.0
        self.break_duration = break_duration_seconds

        self._stop = threading.Event()
        self._start_ts = 0.0
        self._last_break_ts = 0.0
        self.action_count = 0
        self._hotkey_handle = None

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self._start_ts = time.time()
        self._last_break_ts = self._start_ts
        self.action_count = 0
        self._install_hotkey()

    def stop(self) -> None:
        self._stop.set()
        self._remove_hotkey()

    def request_stop(self) -> None:
        self._stop.set()
        if self.bus:
            self.bus.log("emergency stop requested", level="warning")

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # -- hotkey -------------------------------------------------------------
    def _install_hotkey(self) -> None:
        try:
            import keyboard  # type: ignore

            self._hotkey_handle = keyboard.add_hotkey(
                self.emergency_hotkey, self.request_stop)
            if self.bus:
                self.bus.log(
                    f"emergency hotkey active: {self.emergency_hotkey}")
        except Exception:
            self._hotkey_handle = None  # keyboard unavailable / no permissions

    def _remove_hotkey(self) -> None:
        if self._hotkey_handle is None:
            return
        try:
            import keyboard  # type: ignore

            keyboard.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        self._hotkey_handle = None

    # -- per-loop checks ----------------------------------------------------
    def record_action(self, n: int = 1) -> None:
        self.action_count += n

    def should_continue(self) -> bool:
        if self._stop.is_set():
            return False
        if self.max_runtime and (time.time() - self._start_ts) >= self.max_runtime:
            if self.bus:
                self.bus.log("max runtime reached; stopping", level="warning")
            return False
        if self.max_actions and self.action_count >= self.max_actions:
            if self.bus:
                self.bus.log("max actions reached; stopping", level="warning")
            return False
        return True

    def maybe_break(self, sleeper=time.sleep) -> bool:
        """Take a randomized break if due. Returns True if a break was taken."""
        if not self.break_every:
            return False
        if (time.time() - self._last_break_ts) < self.break_every:
            return False
        duration = max(1.0, random.gauss(self.break_duration,
                                         self.break_duration * 0.2))
        if self.bus:
            self.bus.log(f"taking a {duration:.0f}s break")
        # Break in small slices so an emergency stop interrupts promptly.
        waited = 0.0
        while waited < duration and not self._stop.is_set():
            step = min(0.5, duration - waited)
            sleeper(step)
            waited += step
        self._last_break_ts = time.time()
        return True
