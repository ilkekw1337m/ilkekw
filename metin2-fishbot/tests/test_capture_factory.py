import pytest

from metin2fishbot.core import capture


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        capture.create_capture("bogus")


def test_is_win32_available_false_on_linux(monkeypatch):
    monkeypatch.setattr(capture.platform, "system", lambda: "Linux")
    assert capture.is_win32_available() is False


def test_auto_selects_win32_on_windows(monkeypatch):
    monkeypatch.setattr(capture.platform, "system", lambda: "Windows")
    created = {}

    class FakeWin32:
        def __init__(self, title):
            created["title"] = title

    monkeypatch.setattr(capture, "Win32Capture", FakeWin32)
    cap = capture.create_capture("auto", title="MyGame")
    assert isinstance(cap, FakeWin32)
    assert created["title"] == "MyGame"


def test_auto_selects_mss_off_windows(monkeypatch):
    monkeypatch.setattr(capture.platform, "system", lambda: "Linux")
    created = {}

    class FakeMss:
        def __init__(self, region=None):
            created["region"] = region

    monkeypatch.setattr(capture, "MssCapture", FakeMss)
    cap = capture.create_capture("auto")
    assert isinstance(cap, FakeMss)


def test_capture_screen_pos_offsets_by_origin():
    class C(capture.Capture):
        origin = (100, 50)

    c = C()
    assert c.screen_pos(5, 7) == (105, 57)
