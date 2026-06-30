#!/usr/bin/env python3
"""Capture template images (bait/strike marker, puzzle clock, buttons) from a
running game window, for use by the detectors.

Grabs a frame of the configured window (or a screen region) and saves either the
whole frame or a cropped region to ``assets/templates/``. Use this on your own
machine where the game is running.

Examples::

    # save the whole window frame
    python tools/template_capture.py --out assets/templates/full.png

    # save a crop [x y w h] (window-relative)
    python tools/template_capture.py --region 120 340 48 48 \
        --out assets/templates/strike.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from metin2fishbot.core import vision  # noqa: E402
from metin2fishbot.core.capture import create_capture  # noqa: E402
from metin2fishbot.core.config import load_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output PNG path")
    parser.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                        help="window-relative crop to save")
    parser.add_argument("--backend", default=None,
                        help="capture backend override (auto/win32/mss)")
    args = parser.parse_args()

    import cv2

    config = load_config()
    backend = args.backend or config.get("window.backend", "auto")
    cap = create_capture(backend, title=config.get("window.title", "Metin2"))
    frame = cap.grab()
    if args.region:
        frame = vision.crop(frame, tuple(args.region))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame)
    print(f"saved {frame.shape[1]}x{frame.shape[0]} -> {out}")


if __name__ == "__main__":
    main()
