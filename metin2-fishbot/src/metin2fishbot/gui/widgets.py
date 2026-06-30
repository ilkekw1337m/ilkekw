"""Small reusable CustomTkinter widgets."""
from __future__ import annotations

import customtkinter as ctk


class LabeledEntry(ctk.CTkFrame):
    """A label + entry row bound to a StringVar."""

    def __init__(self, master, label: str, value: str = "", width: int = 120,
                 show: str | None = None):
        super().__init__(master, fg_color="transparent")
        self.var = ctk.StringVar(value=str(value))
        ctk.CTkLabel(self, text=label, width=160, anchor="w").pack(
            side="left", padx=(0, 8))
        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=width,
                                  show=show)
        self.entry.pack(side="left")

    def get(self) -> str:
        return self.var.get()

    def set(self, value) -> None:
        self.var.set(str(value))


class LogView(ctk.CTkTextbox):
    """Read-only scrolling log textbox."""

    def __init__(self, master, **kwargs):
        super().__init__(master, state="disabled", **kwargs)

    def append(self, line: str) -> None:
        self.configure(state="normal")
        self.insert("end", line + "\n")
        self.see("end")
        self.configure(state="disabled")
