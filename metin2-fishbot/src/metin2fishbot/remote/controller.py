"""BotController: centralize bot lifecycle so GUI, headless, and Telegram share
one code path for building and driving the bot.

Owns the input controller, capture, fish manager, chat watcher, and the
FishingBot, and exposes a small verb surface (start/stop/pause/resume/status/
screenshot). The GUI stays a thin shell over this; Telegram commands call the
same methods.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..bot.fishing_bot import FishingBot
from ..core.capture import Capture, create_capture
from ..core.config import Config
from ..core.events import EventBus
from ..core.input_controller import InputController
from ..fish.catalog import FishCatalog
from ..fish.disposer import FishDisposer
from ..fish.manager import FishManager
from ..fish.recognizer import FishRecognizer


class BotController:
    def __init__(self, config: Config, bus: Optional[EventBus] = None,
                 api_key: Optional[str] = None):
        self.cfg = config
        self.bus = bus or EventBus()
        self.api_key = api_key
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

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> bool:
        if self.is_running():
            return True
        dry_run = self.cfg.get("runtime.dry_run", True)
        self.input = InputController(
            bus=self.bus, dry_run=dry_run,
            delay_jitter=self.cfg.get("safety.delay_jitter", 0.15),
            click_radius=self.cfg.get("safety.click_radius", 4))
        try:
            self.capture = create_capture(
                self.cfg.get("window.backend", "auto"),
                title=self.cfg.get("window.title", "Metin2"))
        except Exception as exc:
            self.bus.log(f"pencere/capture hatası: {exc}", "error")
            return False

        fish_manager = (self._build_fish_manager(self.input)
                        if self.cfg.get("fish.enabled", False) else None)
        self.bot = FishingBot(self.cfg, bus=self.bus, capture=self.capture,
                              input_controller=self.input,
                              fish_manager=fish_manager)
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

    def pause(self) -> None:
        if self.bot:
            self.bot.pause()

    def resume(self) -> None:
        if self.bot:
            self.bot.resume()

    def is_running(self) -> bool:
        return self.bot is not None and self.bot._running

    # -- introspection ------------------------------------------------------
    def status(self) -> dict:
        if self.bot is None:
            return {"running": False, "state": "stopped"}
        return self.bot.status()

    def screenshot(self) -> Optional[np.ndarray]:
        """Return the most recent frame, or grab one on demand if idle."""
        if self.bot is not None and self.bot.last_frame is not None:
            return self.bot.last_frame
        try:
            cap = self.capture or create_capture(
                self.cfg.get("window.backend", "auto"),
                title=self.cfg.get("window.title", "Metin2"))
            return cap.grab()
        except Exception as exc:
            self.bus.log(f"screenshot hatası: {exc}", "error")
            return None
