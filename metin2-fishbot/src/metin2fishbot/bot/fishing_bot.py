"""Fishing bot orchestrator.

Wires capture, detectors, solver, input, safety, and (optionally) the fish
recognizer/disposer into the state-machine loop and runs it on a background
thread, publishing events for the GUI. Honours ``runtime.dry_run`` end to end:
in dry-run it detects and decides, logging every action without sending input.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from ..core import vision
from ..core.capture import Capture, create_capture
from ..core.config import Config
from ..core.events import EventBus
from ..core.input_controller import InputController
from ..detection.bite_detector import BiteDetector
from ..detection.puzzle_detector import PuzzleDetector
from ..detection.state_detector import StateDetector
from ..safety.guards import SafetyGuard
from ..solver import puzzle_solver
from .state_machine import State, next_state


class FishingBot:
    def __init__(self, config: Config, bus: Optional[EventBus] = None,
                 capture: Optional[Capture] = None,
                 input_controller: Optional[InputController] = None,
                 fish_manager=None):
        self.cfg = config
        self.bus = bus or EventBus()
        self.dry_run = bool(config.get("runtime.dry_run", True))

        self.capture = capture
        self.input = input_controller or InputController(
            bus=self.bus,
            dry_run=self.dry_run,
            delay_jitter=config.get("safety.delay_jitter", 0.15),
            click_radius=config.get("safety.click_radius", 4),
        )
        self.fish_manager = fish_manager  # optional FishManager (recognize+dispose)

        self.guard = SafetyGuard(
            bus=self.bus,
            emergency_hotkey=config.get("safety.emergency_hotkey", "f6"),
            max_runtime_minutes=config.get("safety.max_runtime_minutes", 0),
            max_actions=config.get("safety.max_actions", 0),
            break_every_minutes=config.get("safety.break_every_minutes", 0),
            break_duration_seconds=config.get("safety.break_duration_seconds", 30),
        )

        self.puzzle_detector = PuzzleDetector(
            rows=config.get("puzzle.rows", 4),
            cols=config.get("puzzle.cols", 6),
        )
        # State templates (minigame clock, captcha, inventory) loaded lazily from
        # assets/templates/state/ at start(); empty until then.
        self.state_detector = StateDetector(
            threshold=config.get("fishing.match_threshold", 0.6))
        self.bite_detector: Optional[BiteDetector] = None  # set when a needle exists

        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Not set => running. Set => paused (e.g. while the chat AI types a reply).
        self._paused = threading.Event()
        self.state = State.IDLE

        # Minimal telemetry surfaced via status() and Telegram /status.
        self.stats = {"casts": 0, "cycles": 0, "burns": 0,
                      "captchas": 0, "started_at": None}
        self._captcha_flagged = False  # avoid repeat captcha alerts
        self.last_frame = None  # most recent grab, for remote screenshots

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        if self.capture is None:
            self.capture = create_capture(
                self.cfg.get("window.backend", "auto"),
                title=self.cfg.get("window.title", "Metin2"),
            )
        self._load_state_templates()
        self._load_bite_needle()
        self._preflight_check()
        self._running = True
        self._paused.clear()
        self._captcha_flagged = False
        self.stats["started_at"] = time.time()
        self.guard.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.bus.publish("bot_started")

    def stop(self) -> None:
        self._running = False
        self._paused.clear()
        self.guard.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self.bus.publish("bot_stopped")

    def pause(self) -> None:
        """Pause the fishing loop (used while the chat AI types a reply)."""
        self._paused.set()
        self.bus.publish("paused")

    def resume(self) -> None:
        self._paused.clear()
        self.bus.publish("resumed")

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def _wait_if_paused(self) -> None:
        while self._paused.is_set() and self._running:
            time.sleep(0.05)

    def _load_state_templates(self) -> None:
        """Load optional state templates from assets/templates/state/."""
        try:
            from ..core.config import resolve_path

            state_dir = resolve_path(
                self.cfg.get("templates.state_dir", "assets/templates/state"))
            loaded = StateDetector.from_dir(
                state_dir, threshold=self.cfg.get("fishing.match_threshold", 0.6))
            if loaded.templates:
                self.state_detector.templates.update(loaded.templates)
                self.bus.log(
                    f"state templates loaded: {list(loaded.templates)}")
        except Exception as exc:
            self.bus.log(f"state template load skipped: {exc}", "debug")

    def set_bite_needle(self, needle: np.ndarray) -> None:
        self.bite_detector = BiteDetector(
            needle, threshold=self.cfg.get("fishing.match_threshold", 0.55))

    def _load_bite_needle(self) -> None:
        """Auto-load the strike marker template for the old fishing system."""
        if self.bite_detector is not None:
            return
        try:
            from ..core.config import resolve_path
            import cv2

            path = resolve_path(
                self.cfg.get("templates.bite_needle", "assets/templates/strike.png"))
            if path.exists():
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is not None:
                    self.set_bite_needle(img)
                    self.bus.log(f"bite template loaded: {path.name}")
        except Exception as exc:
            self.bus.log(f"bite template load skipped: {exc}", "debug")

    def _preflight_check(self) -> list:
        """Warn about missing regions/templates before running. Returns issues."""
        system = self.cfg.get("fishing.system", "auto")
        issues = []
        if system in ("old", "auto") and self.bite_detector is None:
            issues.append("eski sistem için strike şablonu yok (assets/templates/strike.png)")
        if system in ("old", "auto") and not self._region("bite"):
            issues.append("'bite' bölgesi kalibre edilmemiş")
        if system in ("new", "auto"):
            if not self._region("board"):
                issues.append("'board' bölgesi kalibre edilmemiş")
            if not (self._region("piece") or self._region("inventory")):
                issues.append("'piece' bölgesi kalibre edilmemiş")
        for issue in issues:
            self.bus.log(f"preflight uyarısı: {issue}", "warning")
        if issues:
            self.bus.publish("preflight", issues=issues)
        return issues

    def status(self) -> dict:
        """Snapshot of bot state + telemetry (for GUI and Telegram /status)."""
        started = self.stats.get("started_at")
        uptime = int(time.time() - started) if started else 0
        return {
            "running": self._running,
            "paused": self.paused,
            "state": self.state.value,
            "system": self.cfg.get("fishing.system", "auto"),
            "dry_run": self.dry_run,
            "uptime_s": uptime,
            "actions": self.guard.action_count,
            "casts": self.stats["casts"],
            "cycles": self.stats["cycles"],
            "burns": self.stats["burns"],
            "captchas": self.stats["captchas"],
        }

    # -- helpers ------------------------------------------------------------
    def _region(self, name: str):
        return self.cfg.get(f"regions.{name}")

    def _click_window(self, rx: int, ry: int) -> None:
        """Click a window-relative coordinate via the capture's screen mapping."""
        sx, sy = self.capture.screen_pos(rx, ry)
        self.input.click(sx, sy)
        self.guard.record_action()

    # -- state handlers -----------------------------------------------------
    def _do_equip_bait(self) -> State:
        self.input.sleep(self.cfg.get("fishing.bait_time", 1.0))
        self.input.press_key(self.cfg.get("fishing.bait_hotkey", "2"))
        self.guard.record_action()
        return State.CAST

    def _do_cast(self) -> State:
        self.input.press_key(self.cfg.get("fishing.cast_hotkey", "1"))
        self.guard.record_action()
        self.stats["casts"] += 1
        self.input.sleep(self.cfg.get("fishing.throw_time", 1.5))
        return State.WAIT

    def _do_wait(self, frame: np.ndarray) -> State:
        system = self.cfg.get("fishing.system", "auto")
        if system == "old":
            return State.HOOK
        if system == "new":
            return State.PUZZLE
        # auto: prefer a calibrated minigame template (robust); otherwise fall
        # back to the board-fill heuristic.
        if self.state_detector.templates.get("minigame") is not None:
            return State.PUZZLE if self.state_detector.minigame_active(frame) \
                else State.HOOK
        board_region = self._region("board")
        if board_region:
            board_frame = vision.crop(frame, tuple(board_region))
            board = self.puzzle_detector.read_board(board_frame)
            if puzzle_solver.empty_count(board) < (
                    self.puzzle_detector.rows * self.puzzle_detector.cols):
                return State.PUZZLE
        return State.HOOK

    def _do_hook(self, frame: np.ndarray) -> State:
        """Old system: click the strike marker until it disappears."""
        if self.bite_detector is None:
            self.bus.log("no bite template configured; skipping hook", "warning")
            return State.LOOT
        region = self._region("bite")
        deadline = time.time() + 15.0
        last_click = 0.0
        while self._running and self.guard.should_continue() and time.time() < deadline:
            self._wait_if_paused()
            frame = self.capture.grab()
            sub = vision.crop(frame, tuple(region)) if region else frame
            pos = self.bite_detector.detect(sub)
            if pos is None:
                break  # marker gone -> fish caught / minigame ended
            now = time.time()
            if now - last_click >= self.cfg.get("safety.click_cooldown", 0.30):
                ox, oy = (region[0], region[1]) if region else (0, 0)
                self._click_window(ox + pos[0], oy + pos[1])
                last_click = now
            self.input.sleep(0.05)
        return State.LOOT

    def _do_puzzle(self, frame: np.ndarray) -> State:
        """New system: read board + active piece, place via solver, repeat."""
        region = self._region("board")
        if not region:
            self.bus.log("no board region configured; skipping puzzle", "warning")
            return State.LOOT
        rects = self.puzzle_detector.cell_rects(tuple(region))
        deadline = time.time() + 30.0
        stale = 0
        while self._running and self.guard.should_continue() and time.time() < deadline:
            self._wait_if_paused()
            frame = self.capture.grab()
            board_frame = vision.crop(frame, tuple(region))
            board = self.puzzle_detector.read_board(board_frame)
            if puzzle_solver.is_complete(board):
                break
            # Active-piece preview region; falls back to inventory for older
            # profiles that predate the dedicated 'piece' region.
            piece_region = self._region("piece") or self._region("inventory")
            piece_id = None
            if piece_region:
                piece_id = self.puzzle_detector.classify_piece(
                    vision.crop(frame, tuple(piece_region)))
            if piece_id is None:
                stale += 1
                if stale > 10:
                    break
                self.input.sleep(0.2)
                continue
            stale = 0
            placement = puzzle_solver.best_placement(board, piece_id)
            if placement is None:
                self.bus.log(f"piece {piece_id}: no placement, discarding")
                self.input.sleep(0.2)
                continue
            for (r, c) in placement.cells:
                x, y, w, h = rects[r][c]
                self._click_window(x + w // 2, y + h // 2)
                self.input.sleep(0.08)
            self.input.sleep(0.15)
        return State.LOOT

    def _do_loot(self, frame: np.ndarray) -> State:
        """Collect the catch and optionally recognise + dispose unwanted fish."""
        if self.fish_manager is not None and self.cfg.get("fish.enabled", False):
            region = self._region("inventory")
            if region:
                burned = self.fish_manager.process_catch(
                    self.capture.grab(), tuple(region))
                self.stats["burns"] += int(burned or 0)
        return State.EQUIP_BAIT

    def _check_captcha(self, frame: np.ndarray) -> bool:
        """Detect a captcha; on first detection pause + alert. Requires a
        calibrated captcha template (otherwise a no-op)."""
        if self.state_detector.templates.get("captcha") is None:
            return False
        if self.state_detector.captcha_present(frame):
            if not self._captcha_flagged:
                self._captcha_flagged = True
                self.stats["captchas"] += 1
                self.pause()
                self.bus.log("CAPTCHA algılandı — bot duraklatıldı", "warning")
                self.bus.publish("captcha", frame=frame)
                self._save_debug_frame(frame, "captcha")
            return True
        # Captcha cleared; allow future alerts and resume if we paused for it.
        if self._captcha_flagged:
            self._captcha_flagged = False
            self.resume()
            self.bus.log("captcha temizlendi — devam ediliyor")
        return False

    def _save_debug_frame(self, frame: np.ndarray, tag: str) -> None:
        if not self.cfg.get("runtime.debug", False):
            return
        try:
            from ..core.config import resolve_path
            import cv2

            debug_dir = resolve_path(self.cfg.get("runtime.debug_dir", "debug"))
            debug_dir.mkdir(parents=True, exist_ok=True)
            path = debug_dir / f"{tag}_{int(time.time())}.png"
            cv2.imwrite(str(path), frame)
        except Exception:
            pass

    # -- main loop ----------------------------------------------------------
    def _run(self) -> None:
        self.state = State.EQUIP_BAIT
        while self._running and self.guard.should_continue():
            self._wait_if_paused()
            self.guard.maybe_break()
            if not self._running or not self.guard.should_continue():
                break
            try:
                frame = self.capture.grab()
            except Exception as exc:  # capture failure shouldn't crash the loop
                self.bus.log(f"capture error: {exc}", "error")
                self.input.sleep(1.0)
                continue

            self.last_frame = frame
            self.stats["cycles"] += 1
            if self._check_captcha(frame):
                self.input.sleep(0.5)
                continue

            self.bus.publish("state", state=self.state.value)
            if self.state == State.EQUIP_BAIT:
                self.state = self._do_equip_bait()
            elif self.state == State.CAST:
                self.state = self._do_cast()
            elif self.state == State.WAIT:
                self.state = self._do_wait(frame)
            elif self.state == State.HOOK:
                self.state = self._do_hook(frame)
            elif self.state == State.PUZZLE:
                self.state = self._do_puzzle(frame)
            elif self.state == State.LOOT:
                self.state = self._do_loot(frame)
            else:
                self.state = next_state(self.state)

        self.state = State.STOPPED
        self.bus.publish("state", state=self.state.value)
        self._running = False
