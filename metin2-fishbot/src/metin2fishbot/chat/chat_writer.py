"""Type an AI-generated reply into the in-game chat box.

Opens chat (Enter), types the reply with humanized per-character delays, and
sends it. Honors dry-run (logs only). Designed to be called by the chat
watcher which first pauses the fishing loop briefly (detect-before-action).
"""
from __future__ import annotations

from typing import Optional

from ..core.input_controller import InputController


class ChatWriter:
    def __init__(self, input_controller: InputController, bus=None,
                 open_key: str = "enter", send_key: str = "enter"):
        self.input = input_controller
        self.bus = bus
        self.open_key = open_key
        self.send_key = send_key

    def send(self, message: str) -> None:
        if self.bus:
            self.bus.log(f"[chat-ai] reply: {message!r}")
        # Open chat, type, send. In dry-run these are logged, not sent.
        self.input.press_key(self.open_key)
        self.input.sleep(0.2)
        self.input.type_text(message)
        self.input.sleep(0.15)
        self.input.press_key(self.send_key)
