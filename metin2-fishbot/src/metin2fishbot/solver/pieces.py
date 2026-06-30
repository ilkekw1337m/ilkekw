"""Jigsaw puzzle piece definitions for the new fishing minigame.

The minigame asks you to place falling pieces onto a small grid (default 4x6).
The exact six shapes vary slightly by client/server, so they are kept *data
driven*: each piece is a set of (row, col) cell offsets, and rotations are
derived geometrically. Tune ``PIECES`` to match your server if needed.

Pieces are identified by an integer id (1..N) which the detector reports from the
piece colour; the solver only needs the shape associated with that id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple

Cell = Tuple[int, int]  # (row, col)


def _normalize(cells) -> FrozenSet[Cell]:
    """Shift a set of cells so the min row/col is 0."""
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return frozenset((r - min_r, c - min_c) for r, c in cells)


def _rotate(cells) -> FrozenSet[Cell]:
    """Rotate cells 90 degrees clockwise, then normalize."""
    return _normalize([(c, -r) for r, c in cells])


def rotations(cells) -> List[FrozenSet[Cell]]:
    """All unique rotations (0/90/180/270) of a shape."""
    seen: List[FrozenSet[Cell]] = []
    current = _normalize(cells)
    for _ in range(4):
        if current not in seen:
            seen.append(current)
        current = _rotate(current)
    return seen


@dataclass(frozen=True)
class Piece:
    id: int
    name: str
    base: FrozenSet[Cell]

    def orientations(self) -> List[FrozenSet[Cell]]:
        return rotations(self.base)


# A reasonable tetromino-style set covering the common fishing-jigsaw shapes.
# Ids 1..6 map to the six piece colours the detector distinguishes.
PIECES: Dict[int, Piece] = {
    1: Piece(1, "O", _normalize([(0, 0), (0, 1), (1, 0), (1, 1)])),       # square
    2: Piece(2, "I", _normalize([(0, 0), (0, 1), (0, 2), (0, 3)])),       # line
    3: Piece(3, "T", _normalize([(0, 0), (0, 1), (0, 2), (1, 1)])),       # T
    4: Piece(4, "L", _normalize([(0, 0), (1, 0), (2, 0), (2, 1)])),       # L
    5: Piece(5, "S", _normalize([(1, 0), (1, 1), (0, 1), (0, 2)])),       # S
    6: Piece(6, "single", _normalize([(0, 0)])),                          # single
}


def get_piece(piece_id: int) -> Piece:
    return PIECES[piece_id]
