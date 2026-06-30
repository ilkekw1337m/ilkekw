"""Fishing state machine.

Defines the states of one fishing cycle and the transition order. The heavy
lifting (capture, detect, click) is performed by ``FishingBot`` which owns the
hardware-facing objects; this module keeps the *flow* explicit and inspectable.

Cycle::

    IDLE -> EQUIP_BAIT -> CAST -> WAIT -> (HOOK | PUZZLE) -> LOOT -> EQUIP_BAIT ...
"""
from __future__ import annotations

import enum


class State(enum.Enum):
    IDLE = "idle"
    EQUIP_BAIT = "equip_bait"
    CAST = "cast"
    WAIT = "wait"
    HOOK = "hook"        # old system: strike/click loop
    PUZZLE = "puzzle"    # new system: jigsaw solve loop
    LOOT = "loot"        # collect + optional fish disposal
    STOPPED = "stopped"


# Normal forward transitions used by the bot when a phase completes cleanly.
NEXT = {
    State.IDLE: State.EQUIP_BAIT,
    State.EQUIP_BAIT: State.CAST,
    State.CAST: State.WAIT,
    State.HOOK: State.LOOT,
    State.PUZZLE: State.LOOT,
    State.LOOT: State.EQUIP_BAIT,
}


def next_state(state: State) -> State:
    """Return the default next state for clean completion of ``state``."""
    return NEXT.get(state, State.EQUIP_BAIT)
