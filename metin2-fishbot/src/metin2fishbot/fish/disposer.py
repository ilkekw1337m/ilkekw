"""Dispose (burn/destroy/drop) unwanted fish.

The exact "burn" mechanic differs by server, so the action is configurable:

* ``log``         — default, safe: only log the decision (dry diagnostic).
* ``drop``        — drag the icon out of inventory / press the drop key.
* ``right_click`` — right-click the icon (servers where that destroys/uses it).
* ``npc_drag``    — drag the icon onto a configured NPC position.

The disposer never decides *which* fish to burn — it acts on a decision already
made from the catalog's keep/burn preference.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple


class FishDisposer:
    def __init__(self, action: str = "log",
                 npc_position: Optional[Tuple[int, int]] = None,
                 bus=None, dry_run: bool = True):
        self.action = action
        self.npc_position = npc_position
        self.bus = bus
        self.dry_run = dry_run

    def _log(self, msg: str) -> None:
        if self.bus:
            self.bus.log(msg)

    def dispose(self, name: str, icon_xy: Tuple[int, int],
                input_controller=None, click_fn: Optional[Callable] = None) -> str:
        """Perform the configured disposal for one fish icon.

        ``icon_xy`` is a window-relative coordinate of the fish icon. ``click_fn``
        (window-relative click) is preferred; ``input_controller`` is used for
        drags. Returns the action actually taken (``log`` in dry-run).
        """
        x, y = icon_xy
        if self.action == "log" or self.dry_run or input_controller is None:
            self._log(f"[dispose:{self.action}] would burn {name} @ ({x},{y})")
            return "log"

        if self.action == "right_click":
            input_controller.right_click(x, y)
        elif self.action == "drop":
            # drag the icon a bit away from the slot to drop it on the ground
            input_controller.drag(x, y, x, y + 120)
        elif self.action == "npc_drag" and self.npc_position:
            nx, ny = self.npc_position
            input_controller.drag(x, y, nx, ny)
        else:
            self._log(f"[dispose] unsupported action {self.action!r}; logging only")
            return "log"
        self._log(f"[dispose:{self.action}] burned {name} @ ({x},{y})")
        return self.action
