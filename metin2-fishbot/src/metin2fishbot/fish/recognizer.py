"""Recognize caught fish from the inventory/result region via template match."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core import vision


class FishRecognizer:
    def __init__(self, templates: Dict[str, np.ndarray], threshold: float = 0.7):
        self.templates = templates
        self.threshold = threshold

    def identify(self, frame: np.ndarray) -> Tuple[Optional[str], float]:
        """Best matching fish name for ``frame`` (a single icon crop)."""
        return vision.best_catalog_match(frame, self.templates, self.threshold)

    def find_all(self, frame: np.ndarray) -> List[Tuple[str, vision.Match]]:
        """Locate every catalogued fish icon present in ``frame``.

        Returns a list of (name, Match) where Match.center is relative to
        ``frame``. Useful for scanning an inventory grid.
        """
        found: List[Tuple[str, vision.Match]] = []
        for name, tpl in self.templates.items():
            for m in vision.match_template_all(frame, tpl, self.threshold):
                found.append((name, m))
        return found
