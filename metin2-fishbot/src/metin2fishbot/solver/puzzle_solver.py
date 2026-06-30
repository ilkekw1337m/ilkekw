"""Greedy solver for the fishing jigsaw minigame.

The board is a ``rows x cols`` grid of 0 (empty) / 1 (filled). Given the current
board and the active piece id, the solver enumerates every legal placement
(piece orientation x board offset that lands on empty in-bounds cells) and picks
the one that minimizes leftover "holes" (empty cells that become hard to fill),
preferring placements that pack against existing fill. If no placement is legal
it returns ``None`` meaning "discard this piece".

Pure data in / data out — no screen interaction — so it is fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .pieces import Cell, get_piece

Board = List[List[int]]


@dataclass
class Placement:
    piece_id: int
    cells: List[Cell]          # absolute board cells the piece would occupy
    score: float               # lower is better


def new_board(rows: int, cols: int) -> Board:
    return [[0] * cols for _ in range(rows)]


def _in_bounds(r: int, c: int, rows: int, cols: int) -> bool:
    return 0 <= r < rows and 0 <= c < cols


def is_complete(board: Board) -> bool:
    return all(all(cell for cell in row) for row in board)


def empty_count(board: Board) -> int:
    return sum(1 for row in board for cell in row if cell == 0)


def apply_placement(board: Board, cells: Sequence[Cell]) -> Board:
    out = [row[:] for row in board]
    for r, c in cells:
        out[r][c] = 1
    return out


def _legal_placements(board: Board, piece_id: int) -> List[List[Cell]]:
    rows, cols = len(board), len(board[0])
    piece = get_piece(piece_id)
    placements: List[List[Cell]] = []
    seen = set()
    for orient in piece.orientations():
        max_r = max(r for r, _ in orient)
        max_c = max(c for _, c in orient)
        for off_r in range(rows - max_r):
            for off_c in range(cols - max_c):
                cells = [(r + off_r, c + off_c) for r, c in orient]
                if any(board[r][c] for r, c in cells):
                    continue  # overlaps existing fill
                key = frozenset(cells)
                if key in seen:
                    continue
                seen.add(key)
                placements.append(cells)
    return placements


def _count_holes(board: Board) -> int:
    """Count empty cells whose 4-neighbours are all filled/out-of-bounds.

    Such cells can only be filled by a single-cell piece, so minimizing them
    keeps the board flexible.
    """
    rows, cols = len(board), len(board[0])
    holes = 0
    for r in range(rows):
        for c in range(cols):
            if board[r][c]:
                continue
            blocked = True
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if _in_bounds(nr, nc, rows, cols) and board[nr][nc] == 0:
                    blocked = False
                    break
            if blocked:
                holes += 1
    return holes


def _adjacency_bonus(board: Board, cells: Sequence[Cell]) -> int:
    """How many of the placed cells touch an existing filled cell / border."""
    rows, cols = len(board), len(board[0])
    bonus = 0
    cellset = set(cells)
    for r, c in cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if not _in_bounds(nr, nc, rows, cols):
                bonus += 1  # touching the wall packs tightly
            elif board[nr][nc] == 1 and (nr, nc) not in cellset:
                bonus += 1
    return bonus


def score_placement(board: Board, cells: Sequence[Cell]) -> float:
    """Lower is better: holes created dominate, ties broken by tighter packing."""
    after = apply_placement(board, cells)
    holes = _count_holes(after)
    bonus = _adjacency_bonus(board, cells)
    return holes * 10.0 - bonus * 0.5


def best_placement(board: Board, piece_id: int) -> Optional[Placement]:
    """Best legal placement, or ``None`` if the piece should be discarded."""
    placements = _legal_placements(board, piece_id)
    if not placements:
        return None
    best: Optional[Placement] = None
    for cells in placements:
        s = score_placement(board, cells)
        if best is None or s < best.score:
            best = Placement(piece_id=piece_id, cells=cells, score=s)
    return best


def solve_sequence(rows: int, cols: int,
                   piece_ids: Sequence[int]) -> Tuple[Board, List[Optional[Placement]]]:
    """Greedily place a sequence of pieces; useful for offline evaluation/tests.

    Returns the final board and the per-piece chosen placement (``None`` =
    discarded).
    """
    board = new_board(rows, cols)
    choices: List[Optional[Placement]] = []
    for pid in piece_ids:
        placement = best_placement(board, pid)
        choices.append(placement)
        if placement is not None:
            board = apply_placement(board, placement.cells)
    return board, choices
