"""Fish catalog: names, icon templates, and per-fish keep/burn preference.

The catalog is a JSON file (``assets/templates/fish/fish_catalog.json``) listing
each fish with its icon path and the user's preference. Icons are downloaded
from the Metin2 wiki by ``tools/fetch_fish_images.py``. Preferences are edited
from the GUI's "Balıklar" tab.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from ..core.config import resolve_path

KEEP = "keep"
BURN = "burn"


@dataclass
class FishEntry:
    name: str
    icon: str               # path relative to project root
    preference: str = KEEP  # "keep" or "burn"


class FishCatalog:
    def __init__(self, entries: List[FishEntry], path: Optional[Path] = None):
        self.entries = entries
        self.path = path
        self._by_name = {e.name: e for e in entries}

    # -- persistence --------------------------------------------------------
    @classmethod
    def load(cls, catalog_path: str) -> "FishCatalog":
        path = resolve_path(catalog_path)
        if not path.exists():
            return cls([], path=path)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = [FishEntry(**item) for item in data.get("fish", [])]
        return cls(entries, path=path)

    def save(self, catalog_path: Optional[str] = None) -> Path:
        path = resolve_path(catalog_path) if catalog_path else self.path
        if path is None:
            raise ValueError("no catalog path to save to")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"fish": [asdict(e) for e in self.entries]}, fh,
                      ensure_ascii=False, indent=2)
        return path

    # -- access -------------------------------------------------------------
    def names(self) -> List[str]:
        return [e.name for e in self.entries]

    def get(self, name: str) -> Optional[FishEntry]:
        return self._by_name.get(name)

    def set_preference(self, name: str, preference: str) -> None:
        if preference not in (KEEP, BURN):
            raise ValueError(f"invalid preference: {preference!r}")
        entry = self._by_name.get(name)
        if entry:
            entry.preference = preference

    def burn_names(self) -> List[str]:
        return [e.name for e in self.entries if e.preference == BURN]

    def load_templates(self) -> Dict[str, "object"]:
        """Read icon images for entries that have an existing file (cv2 BGR)."""
        import cv2  # local import keeps OpenCV optional for pure-catalog use

        templates: Dict[str, object] = {}
        for entry in self.entries:
            icon_path = resolve_path(entry.icon)
            if icon_path.exists():
                img = cv2.imread(str(icon_path), cv2.IMREAD_COLOR)
                if img is not None:
                    templates[entry.name] = img
        return templates
