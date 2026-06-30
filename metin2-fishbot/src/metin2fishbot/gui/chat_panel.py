"""Sohbet AI tab: enable/configure the chat auto-responder.

Lets the user toggle the AI responder, enter the Claude API key (masked), pick
the model, edit the persona/system prompt, and tune triggers. Values are written
back into the live config; the API key stays in memory only (never persisted to
the YAML).
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

MODELS = ["claude-opus-4-8", "claude-haiku-4-5"]


class ChatPanelTab(ctk.CTkFrame):
    def __init__(self, master, config, log: Callable[[str], None]):
        super().__init__(master)
        self.config = config
        self.log = log
        self.api_key = ""  # kept in memory only

        ctk.CTkLabel(self, text="Sohbet AI (admin/şüphe yanıtlayıcı)",
                     font=("", 16, "bold")).pack(anchor="w", padx=12, pady=8)

        self.enabled = ctk.BooleanVar(value=config.get("chat_ai.enabled", False))
        ctk.CTkSwitch(self, text="Etkin", variable=self.enabled).pack(
            anchor="w", padx=12, pady=4)

        # API key (masked, not saved to disk)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="API anahtarı", width=120, anchor="w").pack(
            side="left")
        self.key_var = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self.key_var, show="*", width=320).pack(
            side="left")

        # Model
        mrow = ctk.CTkFrame(self, fg_color="transparent")
        mrow.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(mrow, text="Model", width=120, anchor="w").pack(side="left")
        self.model_var = ctk.StringVar(
            value=config.get("chat_ai.model", MODELS[0]))
        ctk.CTkOptionMenu(mrow, values=MODELS, variable=self.model_var).pack(
            side="left")

        # Triggers
        trow = ctk.CTkFrame(self, fg_color="transparent")
        trow.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(trow, text="Tetikleyiciler", width=120, anchor="w").pack(
            side="left")
        self.triggers_var = ctk.StringVar(
            value=", ".join(config.get("chat_ai.triggers", []) or []))
        ctk.CTkEntry(trow, textvariable=self.triggers_var, width=320).pack(
            side="left")

        # Persona / system prompt
        ctk.CTkLabel(self, text="Persona (system prompt)").pack(
            anchor="w", padx=12, pady=(8, 0))
        self.persona = ctk.CTkTextbox(self, height=120)
        self.persona.pack(fill="x", padx=12, pady=4)
        self.persona.insert("1.0", config.get("chat_ai.persona", ""))

        ctk.CTkButton(self, text="Uygula", command=self.apply).pack(
            anchor="e", padx=12, pady=8)

    def apply(self) -> None:
        self.config.set("chat_ai.enabled", bool(self.enabled.get()))
        self.config.set("chat_ai.model", self.model_var.get())
        triggers = [t.strip() for t in self.triggers_var.get().split(",")
                    if t.strip()]
        self.config.set("chat_ai.triggers", triggers)
        self.config.set("chat_ai.persona", self.persona.get("1.0", "end").strip())
        self.api_key = self.key_var.get().strip()
        self.log("sohbet AI ayarları uygulandı"
                 + (" (API anahtarı ayarlandı)" if self.api_key else ""))

    def get_api_key(self) -> str:
        return self.api_key
