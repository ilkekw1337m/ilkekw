"""Background chat watcher: detect -> AI reply -> write, with cooldown + caps.

Runs on its own thread alongside the fishing loop. When a triggering whisper is
detected it generates a reply via the Claude API and types it back, applying a
reply cooldown and an optional reply cap. Opt-in (``chat_ai.enabled``) and safe
under dry-run.
"""
from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

from ..core import vision
from ..core.config import Config
from ..core.events import EventBus
from .ai_responder import AIResponder
from .chat_detector import ChatDetector
from .chat_writer import ChatWriter


class ChatWatcher:
    def __init__(self, config: Config, capture, input_controller,
                 bus: Optional[EventBus] = None, api_key: Optional[str] = None):
        self.cfg = config
        self.capture = capture
        self.bus = bus or EventBus()

        self.detector = ChatDetector(triggers=config.get("chat_ai.triggers", []))
        self.responder = AIResponder(
            system_prompt=config.get("chat_ai.persona", ""),
            model=config.get("chat_ai.model", "claude-opus-4-8"),
            max_tokens=config.get("chat_ai.max_tokens", 120),
            api_key=api_key,
        )
        self.writer = ChatWriter(input_controller, bus=self.bus)

        self.poll_interval = config.get("chat_ai.poll_interval", 3.0)
        self.reply_cooldown = config.get("chat_ai.reply_cooldown", 8.0)
        self.max_replies = config.get("chat_ai.max_replies", 0)
        self.chat_region = config.get("regions.chat")

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_reply_ts = 0.0
        self.reply_count = 0
        # Optional callback to pause the fishing loop while we type a reply.
        self.pause_cb = None

    @property
    def ready(self) -> bool:
        """True if OCR + API + chat region are all available."""
        return (self.detector.available and self.responder.configured
                and self.chat_region is not None)

    def start(self) -> None:
        if self._running:
            return
        if not self.responder.configured:
            self.bus.log("[chat-ai] no API key; chat AI disabled", "warning")
            return
        if not self.detector.available:
            self.bus.log("[chat-ai] tesseract not available; chat AI disabled",
                         "warning")
            return
        if self.chat_region is None:
            self.bus.log("[chat-ai] no chat region calibrated; disabled",
                         "warning")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.bus.log("[chat-ai] watcher started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def handle_message(self, line: str) -> Optional[str]:
        """Generate and send a reply for one detected line; returns the reply."""
        now = time.time()
        if now - self._last_reply_ts < self.reply_cooldown:
            return None
        if self.max_replies and self.reply_count >= self.max_replies:
            return None
        self.bus.log(f"[chat-ai] incoming: {line!r}")
        reply = self.responder.reply(line)
        if not reply:
            return None
        if self.pause_cb:
            self.pause_cb(True)
        try:
            self.writer.send(reply)
        finally:
            if self.pause_cb:
                self.pause_cb(False)
        self._last_reply_ts = time.time()
        self.reply_count += 1
        # Surface the exchange so the Telegram bridge can forward it.
        self.bus.publish("chat_incoming", line=line, reply=reply)
        return reply

    def _run(self) -> None:
        while self._running:
            try:
                frame = self.capture.grab()
                sub = vision.crop(frame, tuple(self.chat_region))
                line = self.detector.poll(sub)
                if line:
                    self.handle_message(line)
            except Exception as exc:
                self.bus.log(f"[chat-ai] error: {exc}", "error")
            time.sleep(self.poll_interval)
