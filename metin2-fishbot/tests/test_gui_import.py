"""GUI import smoke test.

Skipped where Tkinter/CustomTkinter aren't installed (headless CI). On a desktop
with Tkinter it verifies the GUI modules import without error.
"""
import pytest

pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


def test_gui_modules_import():
    from metin2fishbot.gui import app, calibration, chat_panel, fish_picker, widgets  # noqa: F401
    assert hasattr(app, "App")
