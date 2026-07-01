"""Vision helpers: template matching, HSV masking, region cropping.

Pure functions over numpy/OpenCV BGR frames. Shared by the detectors, the fish
recognizer, and the calibration overlay. No screen/IO side effects here so this
module is fully unit-testable on Linux with fixture images.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

Region = Tuple[int, int, int, int]  # x, y, w, h


@dataclass
class Match:
    """A template match result. (x, y) is the top-left in the haystack."""

    x: int
    y: int
    w: int
    h: int
    confidence: float

    @property
    def center(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def crop(frame: np.ndarray, region: Optional[Region]) -> np.ndarray:
    """Return a view of ``frame`` cropped to ``region`` (or the whole frame)."""
    if region is None:
        return frame
    x, y, w, h = region
    h_img, w_img = frame.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w_img, x + w)
    y1 = min(h_img, y + h)
    return frame[y0:y1, x0:x1]


def match_template(haystack: np.ndarray, needle: np.ndarray,
                   threshold: float = 0.6) -> Optional[Match]:
    """Best single template match at or above ``threshold``, else ``None``."""
    if haystack is None or needle is None:
        return None
    if (haystack.shape[0] < needle.shape[0]
            or haystack.shape[1] < needle.shape[1]):
        return None
    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    # A zero-variance (flat-colour) template makes TM_CCOEFF_NORMED produce NaN;
    # treat non-finite scores as "no match" so we never act on garbage.
    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        return None
    h, w = needle.shape[:2]
    return Match(int(max_loc[0]), int(max_loc[1]), w, h, float(max_val))


def match_template_all(haystack: np.ndarray, needle: np.ndarray,
                       threshold: float = 0.6) -> List[Match]:
    """All non-overlapping matches at/above ``threshold`` (greedy NMS-ish)."""
    if haystack is None or needle is None:
        return []
    if (haystack.shape[0] < needle.shape[0]
            or haystack.shape[1] < needle.shape[1]):
        return []
    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
    h, w = needle.shape[:2]
    matches: List[Match] = []
    ys, xs = np.where(result >= threshold)
    candidates = sorted(
        ((float(result[y, x]), int(x), int(y)) for y, x in zip(ys, xs)),
        reverse=True,
    )
    for conf, x, y in candidates:
        if all(abs(x - m.x) >= w // 2 or abs(y - m.y) >= h // 2
               for m in matches):
            matches.append(Match(x, y, w, h, conf))
    return matches


def best_catalog_match(frame: np.ndarray, templates: dict,
                       threshold: float = 0.6) -> Tuple[Optional[str], float]:
    """Match ``frame`` against a name->template dict; return (best_name, conf)."""
    best_name: Optional[str] = None
    best_conf = 0.0
    for name, tpl in templates.items():
        m = match_template(frame, tpl, threshold=0.0)
        if m and m.confidence > best_conf:
            best_conf = m.confidence
            best_name = name
    if best_conf < threshold:
        return None, best_conf
    return best_name, best_conf


def hsv_mask(frame: np.ndarray, lower: Tuple[int, int, int],
             upper: Tuple[int, int, int]) -> np.ndarray:
    """Binary mask of pixels within an inclusive HSV range."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))


def fill_ratio(mask: np.ndarray) -> float:
    """Fraction of non-zero pixels in a binary mask (0.0..1.0)."""
    if mask.size == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.size)


def mean_brightness(frame: np.ndarray) -> float:
    """Mean grayscale brightness of a BGR frame (0..255)."""
    if frame.size == 0:
        return 0.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())


def dominant_bgr(frame: np.ndarray) -> Tuple[int, int, int]:
    """Mean BGR colour of a frame, used to classify puzzle piece colour."""
    if frame.size == 0:
        return (0, 0, 0)
    mean = frame.reshape(-1, frame.shape[-1]).mean(axis=0)
    return tuple(int(c) for c in mean[:3])
