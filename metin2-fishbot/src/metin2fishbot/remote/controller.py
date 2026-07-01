"""Controllers that centralize bot lifecycle so the GUI, headless main, and
Telegram all drive the bot the same way.

* ``BotController`` — one game client. Optionally bound to a specific window
  (``WindowInfo``) and a shared ``InputBroker`` so it plays nicely with siblings.
* ``MultiController`` — discovers every matching game window and runs one
  ``BotController`` per window, sharing a single input broker (only one client
  sends mouse/keyboard at a time, focusing its window first). Fans commands out
  to all clients, or targets one by 1-based index.

Both expose the same verb surface (``start/stop/pause/resume/status/screenshot``)
with an optional ``index`` on the per-client verbs, so Telegram/GUI don't care
which one they hold.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..bot.fishing_bot import FishingBot
from ..core.capture import Capture, create_capture
from ..core.config import Config
from ..core.events import EventBus
from ..core.input_controller import InputBroker, InputController
from ..core.window import WindowInfo, list_windows
from ..fish.catalog import FishCatalog
from ..fish.disposer import FishDisposer
from ..fish.manager import FishManager
from ..fish.recognizer import FishRecognizer


class BotController:
    def __init__(self, config: Config, bus: Optional[EventBus] = None,
                 api_key: Optional[str] = None,
                 window: Optional[WindowInfo] = None,
                 broker: Optional[InputBroker] = None):
        self.cfg = config
        self.bus = bus or EventBus()
        self.api_key = api_key
        self.window = window
        self.broker = broker
        self.label = window.label if window else "client"
        self.bot: Optional[FishingBot] = None
        self.chat_watcher = None
        self.capture: Optional[Capture] = None
        self.input: Optional[InputController] = None

    # -- building -----------------------------------------------------------
    def _build_fish_manager(self, input_controller):
        catalog = FishCatalog.load(
            self.cfg.get("fish.catalog_path",
                         "assets/templates/fish/fish_catalog.json"))
        recognizer = FishRecognizer(
            catalog.load_templates(),
            threshold=self.cfg.get("fish.match_threshold", 0.7))
        disposer = FishDisposer(
            action=self.cfg.get("fish.dispose_action", "log"),
            npc_position=self.cfg.get("fish.npc_position"),
            bus=self.bus, dry_run=self.cfg.get("runtime.dry_run", True))
        return FishManager(catalog, recognizer, disposer, bus=self.bus,
                           input_controller=input_controller)

    def _make_capture(self) -> Capture:
        return create_capture(
            self.cfg.get("window.backend", "auto"),
            title=self.cfg.get("window.title", "Metin2"),
            hwnd=self.window.hwnd if self.window else None)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> bool:
        if self.is_running():
            return True
        try:
            self.capture = self._make_capture()
        except Exception as exc:
            self.bus.log(f"[{self.label}] pencere/capture hatası: {exc}", "error")
            return False

        dry_run = self.cfg.get("runtime.dry_run", True)
        # When bound to a window with a broker, focus that window before input.
        focus_fn = self.capture.focus if (self.window and self.broker) else None
        self.input = InputController(
            bus=self.bus, dry_run=dry_run,
            delay_jitter=self.cfg.get("safety.delay_jitter", 0.15),
            click_radius=self.cfg.get("safety.click_radius", 4),
            broker=self.broker, focus_fn=focus_fn)

        fish_manager = (self._build_fish_manager(self.input)
                        if self.cfg.get("fish.enabled", False) else None)
        self.bot = FishingBot(self.cfg, bus=self.bus, capture=self.capture,
                              input_controller=self.input,
                              fish_manager=fish_manager,
                              client_label=self.label)
        self.bot.start()

        if self.cfg.get("chat_ai.enabled", False):
            from ..chat.watcher import ChatWatcher

            self.chat_watcher = ChatWatcher(
                self.cfg, self.capture, self.input, bus=self.bus,
                api_key=self.api_key)
            self.chat_watcher.pause_cb = (
                lambda p: self.bot.pause() if p else self.bot.resume())
            self.chat_watcher.start()
        return True

    def stop(self) -> None:
        if self.chat_watcher:
            self.chat_watcher.stop()
            self.chat_watcher = None
        if self.bot:
            self.bot.stop()
            self.bot = None

    def pause(self, index: Optional[int] = None) -> None:
        if self.bot:
            self.bot.pause()

    def resume(self, index: Optional[int] = None) -> None:
        if self.bot:
            self.bot.resume()

    def is_running(self) -> bool:
        return self.bot is not None and self.bot._running

    # -- introspection ------------------------------------------------------
    def status(self, index: Optional[int] = None) -> dict:
        if self.bot is None:
            return {"running": False, "state": "stopped", "label": self.label}
        s = self.bot.status()
        s["label"] = self.label
        return s

    def screenshot(self, index: Optional[int] = None) -> Optional[np.ndarray]:
        """Return the most recent frame, or grab one on demand if idle."""
        if self.bot is not None and self.bot.last_frame is not None:
            return self.bot.last_frame
        try:
            cap = self.capture or self._make_capture()
            return cap.grab()
        except Exception as exc:
            self.bus.log(f"[{self.label}] screenshot hatası: {exc}", "error")
            return None


class MultiController:
    """Run one BotController per detected game window, sharing an input broker."""

    def __init__(self, config: Config, bus: Optional[EventBus] = None,
                 api_key: Optional[str] = None):
        self.cfg = config
        self.bus = bus or EventBus()
        self.api_key = api_key
        self.broker = InputBroker(
            focus_settle=config.get("multiclient.focus_settle", 0.08))
        self.clients: List[BotController] = []

    def discover(self) -> List[WindowInfo]:
        title = self.cfg.get("window.title", "Metin2")
        windows = list_windows(title)
        max_clients = int(self.cfg.get("multiclient.max_clients", 4))
        return windows[:max_clients]

    def start(self) -> bool:
        if self.clients:
            return True
        windows = self.discover()
        if not windows:
            # No per-window enumeration (e.g. non-Windows, or none found):
            # fall back to a single title-based client so behavior degrades
            # gracefully instead of failing.
            self.bus.log("çoklu istemci: pencere bulunamadı, tek istemciye "
                         "geçiliyor", "warning")
            single = BotController(self.cfg, bus=self.bus, api_key=self.api_key)
            ok = single.start()
            if ok:
                self.clients = [single]
            return ok

        self.bus.log(f"çoklu istemci: {len(windows)} pencere bulundu")
        started = 0
        for win in windows:
            client = BotController(self.cfg, bus=self.bus, api_key=self.api_key,
                                   window=win, broker=self.broker)
            if client.start():
                self.clients.append(client)
                started += 1
            else:
                self.bus.log(f"[{win.label}] başlatılamadı", "warning")
        return started > 0

    def stop(self) -> None:
        for client in self.clients:
            client.stop()
        self.clients = []

    def _targets(self, index: Optional[int]) -> List[BotController]:
        if index is None:
            return list(self.clients)
        if 1 <= index <= len(self.clients):
            return [self.clients[index - 1]]
        return []

    def pause(self, index: Optional[int] = None) -> None:
        for client in self._targets(index):
            client.pause()

    def resume(self, index: Optional[int] = None) -> None:
        for client in self._targets(index):
            client.resume()

    def is_running(self) -> bool:
        return any(c.is_running() for c in self.clients)

    def status(self, index: Optional[int] = None) -> list:
        targets = self._targets(index) if index else self.clients
        out = []
        for i, client in enumerate(targets, start=(index or 1)):
            s = client.status()
            s["index"] = i
            out.append(s)
        return out

    def screenshot(self, index: Optional[int] = None) -> Optional[np.ndarray]:
        # Default to the first client when no index is given.
        targets = self._targets(index or 1)
        return targets[0].screenshot() if targets else None
