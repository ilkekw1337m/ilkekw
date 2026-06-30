"""Detect new incoming chat / whisper lines via OCR.

Captures the configured chat region, runs Tesseract OCR (pytesseract), and
reports the newest line that matches the configured triggers (e.g. a GM/admin
whisper) and hasn't been seen before. Vision-only — no memory reads.

Tesseract must be installed separately; if it isn't available, ``available`` is
False and ``poll`` returns ``None`` so the rest of the bot keeps working.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np


class ChatDetector:
    def __init__(self, triggers: Optional[List[str]] = None):
        self.triggers = [t.lower() for t in (triggers or [])]
        self._seen: set = set()
        self._ocr = self._load_ocr()

    @staticmethod
    def _load_ocr():
        try:
            import pytesseract  # type: ignore

            # Touch the binary so we fail fast if it's missing.
            pytesseract.get_tesseract_version()
            return pytesseract
        except Exception:
            return None

    @property
    def available(self) -> bool:
        return self._ocr is not None

    def _ocr_lines(self, frame: np.ndarray) -> List[str]:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        text = self._ocr.image_to_string(gray)
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    def _matches_trigger(self, line: str) -> bool:
        if not self.triggers:
            return True  # react to any new line when no filter is set
        low = line.lower()
        return any(t in low for t in self.triggers)

    def poll(self, chat_frame: np.ndarray) -> Optional[str]:
        """Return a new triggering chat line, or ``None``.

        Lines already seen are suppressed so we answer each message once.
        """
        if self._ocr is None:
            return None
        for line in self._ocr_lines(chat_frame):
            if line in self._seen:
                continue
            self._seen.add(line)
            if self._matches_trigger(line):
                return line
        return None

    def reset(self) -> None:
        self._seen.clear()
