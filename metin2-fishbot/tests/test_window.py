from metin2fishbot.core import window
from metin2fishbot.core.window import WindowInfo


def test_window_info_label():
    w = WindowInfo(hwnd=42, title="Metin2", rect=(0, 0, 800, 600))
    assert w.label == "Metin2 (#42)"


def test_list_windows_empty_when_unavailable(monkeypatch):
    # On non-Windows / no pywin32, enumeration is unavailable -> empty list.
    monkeypatch.setattr(window, "is_windowing_available", lambda: False)
    assert window.list_windows("Metin2") == []


def test_is_windowing_available_false_on_linux(monkeypatch):
    monkeypatch.setattr(window.platform, "system", lambda: "Linux")
    assert window.is_windowing_available() is False
