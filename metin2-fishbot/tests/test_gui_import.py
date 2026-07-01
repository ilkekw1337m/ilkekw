"""GUI import smoke test.

Skipped where Tkinter/CustomTkinter aren't installed (headless CI). On a desktop
with Tkinter it verifies the GUI modules import without error.
"""
import pytest

pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


def test_gui_modules_import():
    from metin2fishbot.gui import (  # noqa: F401
        app, calibration, chat_panel, fish_picker, telegram_panel, widgets,
    )
    assert hasattr(app, "App")
    assert hasattr(telegram_panel, "TelegramPanelTab")
