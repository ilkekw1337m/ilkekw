"""Enumerate top-level windows by title (for multi-client support).

On Windows this uses Win32 ``EnumWindows`` to find every visible window whose
title contains the given substring — so multiple game clients (all titled
"Metin2") can each be targeted by their own ``hwnd``. On non-Windows it returns
an empty list, and callers fall back to single-client / title-based capture.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    rect: tuple  # (left, top, right, bottom)

    @property
    def label(self) -> str:
        return f"{self.title} (#{self.hwnd})"


def is_windowing_available() -> bool:
    """True if per-window enumeration is available (Windows + pywin32)."""
    if platform.system() != "Windows":
        return False
    try:
        import win32gui  # noqa: F401
        return True
    except Exception:
        return False


def list_windows(title_substring: str) -> List[WindowInfo]:
    """Return every visible top-level window whose title contains the substring.

    Ordered left-to-right, top-to-bottom by window position so client indices
    are stable across runs (as long as the windows don't move).
    """
    if not is_windowing_available():
        return []

    import win32gui

    needle = (title_substring or "").lower()
    found: List[WindowInfo] = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or (needle and needle not in title.lower()):
            return
        try:
            rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        found.append(WindowInfo(hwnd=hwnd, title=title, rect=rect))

    win32gui.EnumWindows(_cb, None)
    found.sort(key=lambda w: (w.rect[1] // 50, w.rect[0]))  # rows then columns
    return found
