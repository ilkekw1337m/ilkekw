from metin2fishbot.solver import pieces
from metin2fishbot.solver.puzzle_solver import (
    apply_placement,
    best_placement,
    empty_count,
    is_complete,
    new_board,
    solve_sequence,
)


def test_rotations_unique():
    # Square has 1 unique orientation, line (I) has 2, T has 4.
    assert len(pieces.get_piece(1).orientations()) == 1
    assert len(pieces.get_piece(2).orientations()) == 2
    assert len(pieces.get_piece(3).orientations()) == 4


def test_best_placement_on_empty_board():
    board = new_board(4, 6)
    placement = best_placement(board, 1)  # square
    assert placement is not None
    assert len(placement.cells) == 4
    # All chosen cells are within bounds and empty.
    for r, c in placement.cells:
        assert 0 <= r < 4 and 0 <= c < 6
        assert board[r][c] == 0


def test_apply_and_complete():
    board = new_board(1, 4)
    placement = best_placement(board, 2)  # line of 4 fits a 1x4 board exactly
    assert placement is not None
    board = apply_placement(board, placement.cells)
    assert is_complete(board)
    assert empty_count(board) == 0


def test_discard_when_no_fit():
    # Fully filled board: nothing fits, solver returns None (discard).
    board = [[1] * 6 for _ in range(4)]
    assert best_placement(board, 2) is None


def test_single_piece_fills_last_hole():
    board = new_board(2, 2)
    board[0][0] = board[0][1] = board[1][0] = 1  # one empty cell left
    placement = best_placement(board, 6)  # single
    assert placement is not None
    assert placement.cells == [(1, 1)]


def test_solve_sequence_fills_2x2_with_square():
    board, choices = solve_sequence(2, 2, [1])
    assert is_complete(board)
    assert choices[0] is not None


def test_solver_prefers_tight_packing():
    # On a 2x4 board, place a square then a square: result should be complete.
    board, choices = solve_sequence(2, 4, [1, 1])
    assert is_complete(board)
    assert all(c is not None for c in choices)


def test_fill_full_4x6_with_squares():
    # 4x6 = 24 cells; six 2x2 squares (id 1) fill it exactly.
    board, choices = solve_sequence(4, 6, [1] * 6)
    assert is_complete(board)
    assert all(c is not None for c in choices)


def test_discard_piece_too_big_for_remaining_space():
    # A 1x4 board with one empty cell can't take the 4-long line -> discard.
    board = [[1, 0, 1, 1]]
    from metin2fishbot.solver.puzzle_solver import best_placement
    assert best_placement(board, 2) is None
    # ...but a single-cell piece fits.
    assert best_placement(board, 6) is not None


def test_apply_placement_does_not_mutate_input():
    board = new_board(2, 2)
    out = apply_placement(board, [(0, 0)])
    assert board[0][0] == 0   # original untouched
    assert out[0][0] == 1
