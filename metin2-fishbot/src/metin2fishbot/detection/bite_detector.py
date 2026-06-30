"""Old fishing system: detect the moving fish/strike indicator and click it.

Uses template matching to locate the fish marker inside the configured ``bite``
region. Tracks position over time to estimate velocity and (optionally) predict
where the marker will be, mirroring the approach used by image-based fishbots
such as vncsms/Metin2FishBot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ..core import vision

# Predict ahead when the marker moves faster than this (pixels/sec).
FISH_VELO_PREDICT = 150.0
# Acceptable click radius around the predicted point.
FISH_RANGE = 40


@dataclass
class BiteState:
    last_pos: Optional[Tuple[int, int]] = None
    last_ts: float = 0.0


class BiteDetector:
    def __init__(self, needle: np.ndarray, threshold: float = 0.55):
        self.needle = needle
        self.threshold = threshold
        self.state = BiteState()

    def detect(self, region_frame: np.ndarray,
               now: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """Return the (predicted) marker centre within the region, or ``None``.

        Coordinates are relative to ``region_frame``; the caller offsets them by
        the region origin before clicking.
        """
        now = time.time() if now is None else now
        match = vision.match_template(region_frame, self.needle, self.threshold)
        if match is None:
            self.state = BiteState()
            return None

        cx, cy = match.center
        predicted = (cx, cy)
        if self.state.last_pos is not None:
            dt = max(1e-3, now - self.state.last_ts)
            dx = cx - self.state.last_pos[0]
            dy = cy - self.state.last_pos[1]
            speed = (dx * dx + dy * dy) ** 0.5 / dt
            if speed >= FISH_VELO_PREDICT:
                predicted = (cx + int(dx), cy + int(dy))

        self.state.last_pos = (cx, cy)
        self.state.last_ts = now
        return predicted
