"""Calibration tab: pick window-relative regions by dragging on a screenshot.

The user captures a full screenshot (mss), then drags a rectangle to define each
region (board / bite / inventory / chat). Coordinates are stored relative to the
capture origin so they line up with what the bot grabs at runtime. A manual
entry fallback is provided for fine tuning.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

import customtkinter as ctk

REGION_NAMES = ["board", "bite", "inventory", "chat"]


class RegionPicker(ctk.CTkToplevel):
    """Fullscreen overlay over a screenshot; drag to select a rectangle."""

    def __init__(self, master, screenshot_bgr, origin: Tuple[int, int],
                 on_done: Callable[[Tuple[int, int, int, int]], None]):
        super().__init__(master)
        import cv2
        from PIL import Image

        self.origin = origin
        self.on_done = on_done
        self._start = None
        self._rect = None

        rgb = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2RGB)
        self._pil = Image.fromarray(rgb)
        h, w = screenshot_bgr.shape[:2]
        self.geometry(f"{w}x{h}+0+0")
        self.attributes("-topmost", True)

        self._image = ctk.CTkImage(light_image=self._pil, size=(w, h))
        self.canvas = ctk.CTkCanvas(self, width=w, height=h,
                                    highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._tkimg = self._pil
        # Use a plain Tk PhotoImage via Pillow for the canvas background.
        from PIL import ImageTk

        self._photo = ImageTk.PhotoImage(self._pil)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_press(self, event):
        self._start = (event.x, event.y)
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2)

    def _on_drag(self, event):
        if self._start and self._rect:
            self.canvas.coords(self._rect, self._start[0], self._start[1],
                               event.x, event.y)

    def _on_release(self, event):
        if not self._start:
            return
        x0, y0 = self._start
        x1, y1 = event.x, event.y
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        self.on_done((x, y, w, h))
        self.destroy()


class CalibrationTab(ctk.CTkFrame):
    def __init__(self, master, config, capture_factory: Callable,
                 log: Callable[[str], None]):
        super().__init__(master)
        self.config = config
        self.capture_factory = capture_factory
        self.log = log
        self.region_vars = {}

        ctk.CTkLabel(self, text="Bölge Kalibrasyonu",
                     font=("", 16, "bold")).pack(anchor="w", padx=12, pady=8)
        ctk.CTkLabel(
            self,
            text=("Her bölge için 'Seç' tuşuna basın, ekranda dikdörtgen çizin. "
                  "Koordinatlar pencereye göre [x, y, w, h] olarak saklanır."),
            wraplength=520, justify="left").pack(anchor="w", padx=12)

        for name in REGION_NAMES:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=name, width=90, anchor="w").pack(side="left")
            var = ctk.StringVar(value=str(config.get(f"regions.{name}") or ""))
            self.region_vars[name] = var
            ctk.CTkEntry(row, textvariable=var, width=220).pack(side="left",
                                                                padx=6)
            ctk.CTkButton(row, text="Seç", width=60,
                          command=lambda n=name: self._pick(n)).pack(side="left")

    def _pick(self, name: str):
        try:
            cap = self.capture_factory()
            frame = cap.grab()
        except Exception as exc:
            self.log(f"kalibrasyon yakalama hatası: {exc}")
            return

        def _done(region):
            self.region_vars[name].set(str(list(region)))
            self.config.set(f"regions.{name}", list(region))
            self.log(f"{name} bölgesi: {list(region)}")

        RegionPicker(self, frame, getattr(cap, "origin", (0, 0)), _done)

    def apply(self) -> None:
        """Persist edited region strings back into the config."""
        import ast

        for name, var in self.region_vars.items():
            text = var.get().strip()
            if not text:
                self.config.set(f"regions.{name}", None)
                continue
            try:
                value = ast.literal_eval(text)
                self.config.set(f"regions.{name}", list(value))
            except Exception:
                self.log(f"geçersiz bölge: {name}={text!r}")
