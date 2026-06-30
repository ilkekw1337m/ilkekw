#!/usr/bin/env python3
"""Download Metin2 fish icons from the wiki and build ``fish_catalog.json``.

The fish list comes from the Metin2 wiki Fishing page. For each fish we try the
MediaWiki ``Special:FilePath`` redirect to fetch the icon PNG; whether or not the
download succeeds, the catalog JSON is (re)written so the GUI always has the full
fish list with keep/burn preferences.

Usage::

    python tools/fetch_fish_images.py            # download + build catalog
    python tools/fetch_fish_images.py --no-download   # build catalog only

Source: https://en-wiki.metin2.gameforge.com/index.php/Fishing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FISH_DIR = PROJECT_ROOT / "assets" / "templates" / "fish"
CATALOG_PATH = FISH_DIR / "fish_catalog.json"

WIKI_BASE = "https://en-wiki.metin2.gameforge.com"

# Fish types listed on the Metin2 wiki Fishing page.
FISH_NAMES = [
    "Brook Trout", "Carp", "Catfish", "Crucian Carp", "Eastern Perch", "Eel",
    "Goby", "Goldfish", "Grass Carp", "Large Zander", "Loach", "Lotus Fish",
    "Mandarin Fish", "Marsh Snail", "Mirror Carp", "Perch", "Rainbow Trout",
    "Red King Crab", "River Trout", "Rudd", "Salmon", "Shiri", "Skygazer",
]


def slugify(name: str) -> str:
    return name.lower().replace(" ", "_")


def wiki_filename(name: str) -> str:
    """Best-effort MediaWiki file name for a fish icon."""
    return name.replace(" ", "_") + ".png"


def download_icon(name: str, dest: Path, timeout: float = 15.0) -> bool:
    """Try to fetch the fish icon via Special:FilePath. Returns success."""
    import requests

    url = f"{WIKI_BASE}/index.php/Special:FilePath/{wiki_filename(name)}"
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "metin2-fishbot/0.1"})
        if resp.status_code == 200 and resp.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0"):
            dest.write_bytes(resp.content)
            return True
    except Exception as exc:  # network restricted / not found
        print(f"  ! {name}: {exc}", file=sys.stderr)
    return False


def build_catalog(download: bool = True) -> Path:
    FISH_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve existing keep/burn preferences if a catalog already exists.
    prefs = {}
    if CATALOG_PATH.exists():
        try:
            existing = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            prefs = {f["name"]: f.get("preference", "keep")
                     for f in existing.get("fish", [])}
        except Exception:
            pass

    entries = []
    for name in FISH_NAMES:
        icon_rel = f"assets/templates/fish/{slugify(name)}.png"
        icon_abs = PROJECT_ROOT / icon_rel
        if download and not icon_abs.exists():
            ok = download_icon(name, icon_abs)
            print(f"  {'✓' if ok else '·'} {name}")
        entries.append({
            "name": name,
            "icon": icon_rel,
            "preference": prefs.get(name, "keep"),
        })

    CATALOG_PATH.write_text(
        json.dumps({"fish": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote catalog with {len(entries)} fish -> {CATALOG_PATH}")
    return CATALOG_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-download", action="store_true",
                        help="build catalog without fetching icons")
    args = parser.parse_args()
    build_catalog(download=not args.no_download)


if __name__ == "__main__":
    main()
