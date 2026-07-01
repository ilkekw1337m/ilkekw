"""Generate human-like chat replies with the Claude API.

Uses the official ``anthropic`` SDK. A strict ``system`` prompt makes the model
answer as a busy human player in one short, natural sentence. The API key comes
from the ``ANTHROPIC_API_KEY`` environment variable or is passed explicitly
(from the GUI's secure field).

Default model is ``claude-opus-4-8``; set ``chat_ai.model`` to
``claude-haiku-4-5`` in config for lower latency / cost.
"""
from __future__ import annotations

import os
from typing import Optional

DEFAULT_MODEL = "claude-opus-4-8"


class AIResponder:
    def __init__(self, system_prompt: str, model: str = DEFAULT_MODEL,
                 max_tokens: int = 120, api_key: Optional[str] = None,
                 client=None):
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self._client = client  # injectable for tests
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    @property
    def configured(self) -> bool:
        return self._client is not None or bool(self._api_key)

    def _get_client(self):
        if self._client is not None:
            return self._client
        import anthropic  # lazy import so the package loads without the SDK

        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def reply(self, incoming_message: str) -> Optional[str]:
        """Return a short reply to ``incoming_message`` or ``None`` on failure."""
        if not self.configured:
            return None
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[{"role": "user", "content": incoming_message}],
            )
        except Exception:
            return None
        text = self._extract_text(response)
        return self.clean_reply(text) if text else None

    @staticmethod
    def clean_reply(text: str, max_chars: int = 200) -> str:
        """Make a model reply chat-safe: single line, unquoted, length-capped.

        The in-game chat box is single-line, so collapse newlines, strip
        surrounding quotes the model sometimes adds, and trim length.
        """
        one_line = " ".join(text.split())
        if len(one_line) >= 2 and one_line[0] in "\"'" and one_line[-1] == one_line[0]:
            one_line = one_line[1:-1].strip()
        if len(one_line) > max_chars:
            one_line = one_line[:max_chars].rstrip()
        return one_line

    @staticmethod
    def _extract_text(response) -> Optional[str]:
        content = getattr(response, "content", None)
        if not content:
            return None
        parts = []
        for block in content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        text = " ".join(parts).strip()
        return text or None
