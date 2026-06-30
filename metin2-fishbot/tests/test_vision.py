import numpy as np

from metin2fishbot.core import vision
from metin2fishbot.detection.bite_detector import BiteDetector
from metin2fishbot.detection.puzzle_detector import PuzzleDetector


def _make_icon(color, size=12):
    icon = np.zeros((size, size, 3), np.uint8)
    icon[:] = color
    # add a little texture so template matching is well-conditioned
    icon[0, 0] = (0, 0, 0)
    icon[-1, -1] = (255, 255, 255)
    return icon


def test_crop_region():
    frame = np.zeros((100, 100, 3), np.uint8)
    frame[20:40, 30:50] = 255
    region = vision.crop(frame, (30, 20, 20, 20))
    assert region.shape == (20, 20, 3)
    assert region.mean() == 255


def test_match_template_finds_icon():
    icon = _make_icon((10, 120, 200))
    hay = np.zeros((60, 60, 3), np.uint8)
    hay[25:37, 40:52] = icon
    m = vision.match_template(hay, icon, threshold=0.7)
    assert m is not None
    assert abs(m.center[0] - 46) <= 2
    assert abs(m.center[1] - 31) <= 2


def test_bite_detector_returns_center():
    icon = _make_icon((0, 0, 255))
    region = np.zeros((50, 80, 3), np.uint8)
    region[20:32, 30:42] = icon
    det = BiteDetector(icon, threshold=0.7)
    pos = det.detect(region, now=0.0)
    assert pos is not None
    assert abs(pos[0] - 36) <= 2 and abs(pos[1] - 26) <= 2


def test_puzzle_detector_reads_board():
    det = PuzzleDetector(rows=2, cols=2, fill_threshold=40.0)
    # board frame: top-left + bottom-right cells filled (bright), others dark
    frame = np.zeros((40, 40, 3), np.uint8)
    frame[0:20, 0:20] = 200      # cell (0,0)
    frame[20:40, 20:40] = 200    # cell (1,1)
    board = det.read_board(frame)
    assert board == [[1, 0], [0, 1]]


def test_puzzle_detector_classifies_piece():
    det = PuzzleDetector()
    red = np.zeros((10, 10, 3), np.uint8)
    red[:] = (60, 60, 200)  # matches DEFAULT_PIECE_COLORS[1]
    assert det.classify_piece(red) == 1
    black = np.zeros((10, 10, 3), np.uint8)
    assert det.classify_piece(black) is None
