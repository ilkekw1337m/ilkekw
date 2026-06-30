"""Balıklar tab: show the fish catalog and let the user pick keep/burn.

Each fish row shows its icon (if downloaded) and a keep/burn segmented toggle.
Selections are written back to the catalog JSON.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.config import resolve_path
from ..fish.catalog import BURN, KEEP, FishCatalog


class FishPickerTab(ctk.CTkScrollableFrame):
    def __init__(self, master, config, log: Callable[[str], None]):
        super().__init__(master)
        self.config = config
        self.log = log
        self.catalog = FishCatalog.load(
            config.get("fish.catalog_path",
                       "assets/templates/fish/fish_catalog.json"))
        self._vars = {}
        self._icons = {}
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(header, text="Balık Seçimi (keep = tut, burn = yaktır)",
                     font=("", 15, "bold")).pack(side="left", padx=8)
        ctk.CTkButton(header, text="Tümünü Tut", width=90,
                      command=lambda: self._set_all(KEEP)).pack(side="right",
                                                                 padx=4)
        ctk.CTkButton(header, text="Tümünü Yaktır", width=110,
                      command=lambda: self._set_all(BURN)).pack(side="right",
                                                                 padx=4)
        ctk.CTkButton(header, text="Kaydet", width=80,
                      command=self.save).pack(side="right", padx=4)

        for entry in self.catalog.entries:
            self._add_row(entry)

    def _load_icon(self, entry):
        icon_path = resolve_path(entry.icon)
        if not icon_path.exists():
            return None
        try:
            from PIL import Image

            img = Image.open(icon_path)
            return ctk.CTkImage(light_image=img, size=(32, 32))
        except Exception:
            return None

    def _add_row(self, entry):
        row = ctk.CTkFrame(self)
        row.pack(fill="x", pady=2, padx=4)

        icon = self._load_icon(entry)
        if icon:
            self._icons[entry.name] = icon
            ctk.CTkLabel(row, image=icon, text="").pack(side="left", padx=6)
        else:
            ctk.CTkLabel(row, text="🐟", width=36).pack(side="left", padx=6)

        ctk.CTkLabel(row, text=entry.name, width=160, anchor="w").pack(
            side="left", padx=6)

        var = ctk.StringVar(value=entry.preference)
        self._vars[entry.name] = var
        ctk.CTkSegmentedButton(row, values=[KEEP, BURN], variable=var).pack(
            side="right", padx=8)

    def _set_all(self, preference: str):
        for var in self._vars.values():
            var.set(preference)

    def save(self):
        for name, var in self._vars.items():
            self.catalog.set_preference(name, var.get())
        path = self.catalog.save()
        burn = self.catalog.burn_names()
        self.log(f"balık tercihleri kaydedildi -> {path} (yaktırılacak: {burn})")
