"""New fishing system: read the jigsaw board state and the active piece.

The board region is sliced into a ``rows x cols`` grid of cells. A cell is
"filled" when its mean brightness exceeds an empty-baseline threshold. The
active piece is classified into one of the six ids by nearest reference colour.
Everything works on a BGR frame of the board region, so it is testable with
fixtures.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core import vision
from ..solver.puzzle_solver import Board

# Reference BGR colours for the six piece ids. Tune to match your client; the
# detector picks the nearest by Euclidean distance.
DEFAULT_PIECE_COLORS: Dict[int, Tuple[int, int, int]] = {
    1: (60, 60, 200),    # red
    2: (60, 180, 60),    # green
    3: (200, 160, 40),   # blue
    4: (40, 200, 220),   # yellow
    5: (200, 80, 200),   # magenta
    6: (200, 200, 200),  # white / single
}


class PuzzleDetector:
    def __init__(self, rows: int = 4, cols: int = 6,
                 fill_threshold: float = 40.0,
                 piece_colors: Optional[Dict[int, Tuple[int, int, int]]] = None):
        self.rows = rows
        self.cols = cols
        self.fill_threshold = fill_threshold
        self.piece_colors = piece_colors or DEFAULT_PIECE_COLORS

    def cell_rects(self, region: Tuple[int, int, int, int]) -> List[List[Tuple[int, int, int, int]]]:
        """Window-relative rects for each board cell, given the board region."""
        x, y, w, h = region
        cw = w / self.cols
        ch = h / self.rows
        grid = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                row.append((int(x + c * cw), int(y + r * ch), int(cw), int(ch)))
            grid.append(row)
        return grid

    def read_board(self, board_frame: np.ndarray) -> Board:
        """Slice the board-region frame into cells; 1 = filled, 0 = empty."""
        h, w = board_frame.shape[:2]
        cw = w / self.cols
        ch = h / self.rows
        board: Board = []
        for r in range(self.rows):
            row: List[int] = []
            for c in range(self.cols):
                y0 = int(r * ch)
                y1 = int((r + 1) * ch)
                x0 = int(c * cw)
                x1 = int((c + 1) * cw)
                cell = board_frame[y0:y1, x0:x1]
                filled = vision.mean_brightness(cell) > self.fill_threshold
                row.append(1 if filled else 0)
            board.append(row)
        return board

    def classify_piece(self, piece_frame: np.ndarray) -> Optional[int]:
        """Classify the active piece by nearest reference colour."""
        if piece_frame.size == 0:
            return None
        bgr = np.array(vision.dominant_bgr(piece_frame), dtype=float)
        # Ignore near-black (no piece present).
        if bgr.max() < 25:
            return None
        best_id: Optional[int] = None
        best_dist = float("inf")
        for pid, ref in self.piece_colors.items():
            dist = float(np.linalg.norm(bgr - np.array(ref, dtype=float)))
            if dist < best_dist:
                best_dist = dist
                best_id = pid
        return best_id
