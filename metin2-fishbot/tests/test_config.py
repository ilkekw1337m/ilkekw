import yaml

from metin2fishbot.core.config import (
    Config,
    _deep_merge,
    load_config,
    resolve_path,
    PROJECT_ROOT,
)


def test_deep_merge_overrides_and_preserves():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 20, "z": 30}, "c": 4}
    merged = _deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}
    # base is not mutated
    assert base == {"a": {"x": 1, "y": 2}, "b": 3}


def test_config_dotted_get_set():
    cfg = Config({"fishing": {"system": "auto"}})
    assert cfg.get("fishing.system") == "auto"
    assert cfg.get("fishing.missing", "def") == "def"
    assert cfg.get("nope.deeper") is None
    cfg.set("regions.board", [1, 2, 3, 4])
    assert cfg.get("regions.board") == [1, 2, 3, 4]


def test_load_config_with_profile_overlay(tmp_path, monkeypatch):
    # Build a fake default + profile and verify overlay merges.
    default = {"window": {"title": "Metin2"}, "fishing": {"system": "auto"},
               "runtime": {"profile": None}}
    default_path = tmp_path / "default.yaml"
    default_path.write_text(yaml.safe_dump(default), encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "srv.yaml").write_text(
        yaml.safe_dump({"fishing": {"system": "new"}}), encoding="utf-8")

    import metin2fishbot.core.config as config_mod
    monkeypatch.setattr(config_mod, "PROFILES_DIR", profiles_dir)

    cfg = load_config(profile="srv", config_path=default_path)
    assert cfg.get("fishing.system") == "new"   # overlaid
    assert cfg.get("window.title") == "Metin2"  # preserved


def test_resolve_path_relative_and_absolute():
    rel = resolve_path("assets/x.png")
    assert rel == PROJECT_ROOT / "assets" / "x.png"
    absolute = resolve_path("/tmp/y.png")
    assert str(absolute) == "/tmp/y.png"


def test_default_config_has_piece_region():
    cfg = load_config()
    # v2 added a dedicated piece region key.
    assert "piece" in cfg.get("regions", {})
    assert cfg.get("templates.state_dir")
