"""FishManager: glue recognizer + catalog preference + disposer.

Given an inventory frame, identify catalogued fish, and burn the ones the user
marked ``burn``. Wired into the bot's LOOT state.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np

from ..core import vision
from .catalog import BURN, FishCatalog
from .disposer import FishDisposer
from .recognizer import FishRecognizer


class FishManager:
    def __init__(self, catalog: FishCatalog, recognizer: FishRecognizer,
                 disposer: FishDisposer, bus=None, input_controller=None):
        self.catalog = catalog
        self.recognizer = recognizer
        self.disposer = disposer
        self.bus = bus
        self.input = input_controller

    def process_catch(self, frame: np.ndarray,
                      inventory_region: Tuple[int, int, int, int],
                      click_fn: Optional[Callable] = None) -> int:
        """Scan the inventory region; burn fish marked for disposal.

        Returns the number of fish disposed (or, in dry-run, would-dispose).
        """
        x, y, _, _ = inventory_region
        sub = vision.crop(frame, inventory_region)
        burned = 0
        for name, match in self.recognizer.find_all(sub):
            entry = self.catalog.get(name)
            if entry and entry.preference == BURN:
                cx = x + match.center[0]
                cy = y + match.center[1]
                self.disposer.dispose(name, (cx, cy),
                                      input_controller=self.input,
                                      click_fn=click_fn)
                burned += 1
            elif self.bus:
                self.bus.log(f"keep {name}", level="debug")
        return burned
