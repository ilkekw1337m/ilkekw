"""Configuration loading and persistence.

Loads ``config/default_config.yaml``, optionally overlays a named profile from
``config/profiles/<name>.yaml``, and exposes a small ``Config`` wrapper with
dotted-path access (``cfg.get("fishing.system")``).
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Repo root = three parents up from this file (src/metin2fishbot/core/config.py).
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default_config.yaml"
PROFILES_DIR = PROJECT_ROOT / "config" / "profiles"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """Thin wrapper over the merged config dict with dotted access."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data


def load_config(
    profile: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> Config:
    """Load default config, overlay a profile if requested, and return ``Config``.

    The active profile is taken from the ``profile`` argument, else from the
    ``runtime.profile`` key in the default config.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    profile_name = profile or data.get("runtime", {}).get("profile")
    if profile_name:
        profile_path = PROFILES_DIR / f"{profile_name}.yaml"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as fh:
                overlay = yaml.safe_load(fh) or {}
            data = _deep_merge(data, overlay)

    return Config(data)


def save_profile(config: Config, name: str) -> Path:
    """Persist the current config dict as a profile YAML and return its path."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILES_DIR / f"{name}.yaml"
    with open(profile_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config.data, fh, allow_unicode=True, sort_keys=False)
    return profile_path


def resolve_path(relative: str) -> Path:
    """Resolve a project-relative path (e.g. catalog_path) to an absolute Path."""
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p
