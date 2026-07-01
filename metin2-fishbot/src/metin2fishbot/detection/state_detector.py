"""Detect high-level UI states: minigame open, captcha, daily reward, inventory.

Template-based, with graceful fallbacks when a template is not provided. The
'detect-before-action' principle relies on these checks so the bot never blind
clicks. Each detector is optional — missing templates simply report ``False``.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from ..core import vision


class StateDetector:
    def __init__(self, templates: Optional[Dict[str, np.ndarray]] = None,
                 threshold: float = 0.6):
        self.templates = templates or {}
        self.threshold = threshold

    @classmethod
    def from_dir(cls, directory, threshold: float = 0.6,
                 names=("minigame", "captcha", "inventory", "daily_reward")):
        """Load named state templates (<name>.png/.jpg) from a directory."""
        import cv2
        from pathlib import Path

        directory = Path(directory)
        templates: Dict[str, np.ndarray] = {}
        if directory.exists():
            for name in names:
                for ext in (".png", ".jpg"):
                    path = directory / f"{name}{ext}"
                    if path.exists():
                        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                        if img is not None:
                            templates[name] = img
                        break
        return cls(templates, threshold=threshold)

    def _present(self, name: str, frame: np.ndarray) -> bool:
        tpl = self.templates.get(name)
        if tpl is None:
            return False
        return vision.match_template(frame, tpl, self.threshold) is not None

    def minigame_active(self, frame: np.ndarray) -> bool:
        """True if the puzzle/strike minigame clock/frame is visible."""
        return self._present("minigame", frame)

    def captcha_present(self, frame: np.ndarray) -> bool:
        return self._present("captcha", frame)

    def daily_reward(self, frame: np.ndarray) -> bool:
        return self._present("daily_reward", frame)

    def inventory_open(self, frame: np.ndarray) -> bool:
        return self._present("inventory", frame)
