"""Window capture abstraction.

``Capture`` returns BGR ``numpy`` frames of the game window. Two backends:

* ``Win32Capture`` (Windows runtime) — ``GetWindowDC`` + ``BitBlt``; captures the
  window even when it is in the background. Imported lazily so this module loads
  on Linux for tests.
* ``MssCapture`` (cross-platform) — full-screen / region grab via ``mss``; used
  for CI, fixture generation, and Linux GUI smoke tests.

Both expose ``grab() -> np.ndarray (BGR)`` and ``screen_pos(x, y)`` which maps a
frame-relative pixel to an absolute screen coordinate (for input).
"""
from __future__ import annotations

import platform
import sys
from typing import Optional, Tuple

import numpy as np


class Capture:
    """Abstract capture backend."""

    #: top-left of the captured region in absolute screen coordinates
    origin: Tuple[int, int] = (0, 0)

    def grab(self) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def screen_pos(self, x: int, y: int) -> Tuple[int, int]:
        """Map a frame-relative (x, y) to absolute screen coordinates."""
        ox, oy = self.origin
        return ox + x, oy + y

    def close(self) -> None:  # pragma: no cover - default no-op
        pass


class MssCapture(Capture):
    """Cross-platform capture via mss. Grabs a monitor or fixed region."""

    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None,
                 monitor: int = 1):
        import mss  # lazy: optional at import time

        self._sct = mss.mss()
        self._mss = mss
        if region is not None:
            x, y, w, h = region
            self._bbox = {"left": x, "top": y, "width": w, "height": h}
            self.origin = (x, y)
        else:
            mon = self._sct.monitors[monitor]
            self._bbox = mon
            self.origin = (mon["left"], mon["top"])

    def grab(self) -> np.ndarray:
        shot = self._sct.grab(self._bbox)
        # mss returns BGRA; drop alpha -> BGR
        frame = np.asarray(shot)[:, :, :3]
        return np.ascontiguousarray(frame)

    def close(self) -> None:
        self._sct.close()


class Win32Capture(Capture):
    """Windows capture of a named window via GetWindowDC + BitBlt.

    Mirrors the well-known pattern (e.g. vncsms/Metin2FishBot windowcapture.py):
    find the window, account for border/titlebar offsets, BitBlt into a bitmap,
    convert the raw bytes to a contiguous BGR numpy array.
    """

    # Typical non-client offsets for a standard windowed game.
    BORDER_PIXELS = 8
    TITLEBAR_PIXELS = 30

    def __init__(self, title: str):
        import win32con  # noqa: F401  (validates availability)
        import win32gui
        import win32ui

        self._win32gui = win32gui
        self._win32ui = win32ui

        self.hwnd = win32gui.FindWindow(None, title)
        if not self.hwnd:
            # Fall back to a substring search over visible top-level windows.
            self.hwnd = self._find_by_substring(title)
        if not self.hwnd:
            raise RuntimeError(f"window not found: {title!r}")

        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.width = (right - left) - self.BORDER_PIXELS * 2
        self.height = (bottom - top) - self.TITLEBAR_PIXELS - self.BORDER_PIXELS
        self.cropped_x = self.BORDER_PIXELS
        self.cropped_y = self.TITLEBAR_PIXELS
        self.origin = (left + self.cropped_x, top + self.cropped_y)

    def _find_by_substring(self, needle: str) -> int:
        needle_low = needle.lower()
        matches = []

        def _cb(hwnd, _):
            if self._win32gui.IsWindowVisible(hwnd):
                title = self._win32gui.GetWindowText(hwnd)
                if title and needle_low in title.lower():
                    matches.append(hwnd)

        self._win32gui.EnumWindows(_cb, None)
        return matches[0] if matches else 0

    def grab(self) -> np.ndarray:
        import win32gui

        wdc = win32gui.GetWindowDC(self.hwnd)
        dc_obj = self._win32ui.CreateDCFromHandle(wdc)
        mem_dc = dc_obj.CreateCompatibleDC()
        bitmap = self._win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(dc_obj, self.width, self.height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (self.width, self.height), dc_obj,
                      (self.cropped_x, self.cropped_y), 0x00CC0020)  # SRCCOPY

        signed = bitmap.GetBitmapBits(True)
        frame = np.frombuffer(signed, dtype=np.uint8)
        frame = frame.reshape((self.height, self.width, 4))

        dc_obj.DeleteDC()
        mem_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, wdc)
        self._win32ui.DeleteObject(bitmap.GetHandle())

        return np.ascontiguousarray(frame[:, :, :3])


def create_capture(backend: str, title: str = "Metin2",
                   region: Optional[Tuple[int, int, int, int]] = None) -> Capture:
    """Factory: pick a backend. ``auto`` -> win32 on Windows, mss elsewhere."""
    chosen = backend
    if backend == "auto":
        chosen = "win32" if platform.system() == "Windows" else "mss"

    if chosen == "win32":
        return Win32Capture(title)
    if chosen == "mss":
        return MssCapture(region=region)
    raise ValueError(f"unknown capture backend: {backend!r}")


def is_win32_available() -> bool:
    """True if the Win32 capture stack is importable (Windows + pywin32)."""
    if platform.system() != "Windows":
        return False
    try:
        import win32gui  # noqa: F401
        import win32ui  # noqa: F401
        return True
    except Exception:
        return False
