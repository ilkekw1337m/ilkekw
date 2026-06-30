import numpy as np
import pytest

from metin2fishbot.fish.catalog import BURN, KEEP, FishCatalog, FishEntry
from metin2fishbot.fish.disposer import FishDisposer
from metin2fishbot.fish.manager import FishManager
from metin2fishbot.fish.recognizer import FishRecognizer


def _icon(color, size=12):
    icon = np.zeros((size, size, 3), np.uint8)
    icon[:] = color
    icon[0, 0] = (0, 0, 0)
    icon[-1, -1] = (255, 255, 255)
    return icon


def test_catalog_save_load(tmp_path):
    catalog_file = tmp_path / "cat.json"
    cat = FishCatalog([
        FishEntry("Carp", "x.png", KEEP),
        FishEntry("Salmon", "y.png", BURN),
    ], path=catalog_file)
    cat.save()
    loaded = FishCatalog.load(str(catalog_file))
    assert loaded.names() == ["Carp", "Salmon"]
    assert loaded.burn_names() == ["Salmon"]


def test_catalog_set_preference_validation():
    cat = FishCatalog([FishEntry("Carp", "x.png", KEEP)])
    cat.set_preference("Carp", BURN)
    assert cat.get("Carp").preference == BURN
    with pytest.raises(ValueError):
        cat.set_preference("Carp", "explode")


def test_recognizer_identifies_fish():
    carp = _icon((40, 200, 60))
    salmon = _icon((200, 120, 40))
    rec = FishRecognizer({"Carp": carp, "Salmon": salmon}, threshold=0.7)
    name, conf = rec.identify(carp)
    assert name == "Carp"
    assert conf > 0.9


def test_disposer_logs_in_dry_run():
    disp = FishDisposer(action="drop", dry_run=True)
    action = disp.dispose("Salmon", (100, 200))
    assert action == "log"  # dry-run never sends input


def test_disposer_right_click_calls_input():
    calls = []

    class FakeInput:
        def right_click(self, x, y):
            calls.append((x, y))

    disp = FishDisposer(action="right_click", dry_run=False)
    action = disp.dispose("Salmon", (10, 20), input_controller=FakeInput())
    assert action == "right_click"
    assert calls == [(10, 20)]


def test_manager_burns_only_marked_fish():
    carp = _icon((40, 200, 60))
    salmon = _icon((200, 120, 40))
    catalog = FishCatalog([
        FishEntry("Carp", "x.png", KEEP),
        FishEntry("Salmon", "y.png", BURN),
    ])
    rec = FishRecognizer({"Carp": carp, "Salmon": salmon}, threshold=0.7)

    disposed = []

    class RecordingDisposer(FishDisposer):
        def dispose(self, name, icon_xy, input_controller=None, click_fn=None):
            disposed.append(name)
            return "log"

    mgr = FishManager(catalog, rec, RecordingDisposer(dry_run=True))

    # inventory frame: salmon icon placed at (5,5); region offset (100, 50)
    frame = np.zeros((200, 300, 3), np.uint8)
    frame[55:67, 105:117] = salmon
    mgr.process_catch(frame, (100, 50, 80, 40))
    assert disposed == ["Salmon"]
