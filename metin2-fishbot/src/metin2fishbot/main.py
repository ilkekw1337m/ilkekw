"""Entry point: launch the GUI.

Run with (``src/`` must be on ``PYTHONPATH``, or install with ``pip install -e .``)::

    PYTHONPATH=src python -m metin2fishbot.main
    # or, after `pip install -e .`:
    python -m metin2fishbot.main

Use ``--profile NAME`` to overlay a calibration profile, or ``--no-gui`` to run
a headless dry-run loop (useful for debugging detection without a UI).
Running the file directly (``python main.py``) will not work — the package uses
relative imports and must be launched as a module.
"""
from __future__ import annotations

import argparse
import sys

from .core.config import load_config
from .core.events import configure_logging


def run_gui(config):
    try:
        from .gui.app import App
    except Exception as exc:  # tkinter/customtkinter missing
        print(f"GUI baslatilamadi ({exc}).\n"
              "Tkinter ve customtkinter kurulu mu? Linux'ta: 'apt install "
              "python3-tk' ve 'pip install customtkinter'.", file=sys.stderr)
        return 1
    App(config).mainloop()
    return 0


def run_headless(config):
    """Headless run via BotController (dry-run), logging only. Also starts the
    Telegram bridge if enabled, so you can drive the bot from your phone with no
    GUI on the machine."""
    import time

    from .core.events import EventBus
    from .remote.controller import BotController

    config.set("runtime.dry_run", True)
    bus = EventBus()
    bus.subscribe(lambda e: print(f"[{e.type}] {e.payload}")
                  if e.type in ("log", "state") else None)
    controller = BotController(config, bus=bus)
    telegram = None
    if not controller.start():
        print("Headless capture baslatilamadi.\n"
              "Bu mod ekranli bir makinede (oyun penceresi acikken) calisir.",
              file=sys.stderr)
        return 1
    try:
        if config.get("telegram.enabled", False):
            from .remote.telegram import TelegramBridge

            telegram = TelegramBridge(config, controller, bus=bus)
            telegram.start()
            print("Telegram köprüsü aktif; Ctrl+C ile çıkın.")
            while True:
                time.sleep(1)
        else:
            time.sleep(config.get("runtime.headless_seconds", 5))
    except KeyboardInterrupt:
        pass
    finally:
        if telegram:
            telegram.stop()
        controller.stop()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Metin2 fishing bot")
    parser.add_argument("--profile", default=None,
                        help="calibration profile name under config/profiles")
    parser.add_argument("--no-gui", action="store_true",
                        help="run a headless dry-run loop instead of the GUI")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    configure_logging(debug=args.debug)
    config = load_config(profile=args.profile)
    if args.debug:
        config.set("runtime.debug", True)

    if args.no_gui:
        return run_headless(config)
    return run_gui(config)


if __name__ == "__main__":
    raise SystemExit(main())
