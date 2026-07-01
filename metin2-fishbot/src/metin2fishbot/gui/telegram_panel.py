"""Telegram tab: enable + configure remote control / notifications.

Token stays in memory (env or this field), chat ids and notify flags are
written to the live config. A "Test mesajı" button verifies connectivity.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class TelegramPanelTab(ctk.CTkFrame):
    def __init__(self, master, config, log: Callable[[str], None]):
        super().__init__(master)
        self.config = config
        self.log = log
        self.token = ""  # kept in memory only

        ctk.CTkLabel(self, text="Telegram Uzaktan Kontrol",
                     font=("", 16, "bold")).pack(anchor="w", padx=12, pady=8)

        self.enabled = ctk.BooleanVar(value=config.get("telegram.enabled", False))
        ctk.CTkSwitch(self, text="Etkin", variable=self.enabled).pack(
            anchor="w", padx=12, pady=4)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Bot Token", width=120, anchor="w").pack(
            side="left")
        self.token_var = ctk.StringVar(value=config.get("telegram.token", ""))
        ctk.CTkEntry(row, textvariable=self.token_var, show="*", width=320).pack(
            side="left")

        crow = ctk.CTkFrame(self, fg_color="transparent")
        crow.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(crow, text="Yetkili chat_id'ler", width=120,
                     anchor="w").pack(side="left")
        self.chat_ids_var = ctk.StringVar(
            value=", ".join(str(c) for c in
                            (config.get("telegram.authorized_chat_ids") or [])))
        ctk.CTkEntry(crow, textvariable=self.chat_ids_var, width=320).pack(
            side="left")

        notify = config.get("telegram.notify", {}) or {}
        self.n_captcha = ctk.BooleanVar(value=notify.get("captcha", True))
        self.n_chat = ctk.BooleanVar(value=notify.get("chat", True))
        self.n_errors = ctk.BooleanVar(value=notify.get("errors", True))
        ctk.CTkLabel(self, text="Bildirimler:").pack(anchor="w", padx=12,
                                                     pady=(8, 0))
        ctk.CTkCheckBox(self, text="Captcha", variable=self.n_captcha).pack(
            anchor="w", padx=24, pady=2)
        ctk.CTkCheckBox(self, text="GM/whisper mesajı", variable=self.n_chat).pack(
            anchor="w", padx=24, pady=2)
        ctk.CTkCheckBox(self, text="Bot durdu / hata", variable=self.n_errors).pack(
            anchor="w", padx=24, pady=2)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=8)
        ctk.CTkButton(btns, text="Uygula", command=self.apply).pack(
            side="left", padx=4)
        ctk.CTkButton(btns, text="Test mesajı gönder",
                      command=self.send_test).pack(side="left", padx=4)

        ctk.CTkLabel(
            self,
            text=("Token'ı @BotFather'dan alın. chat_id öğrenmek için bota /start "
                  "yazıp yetkisiz yanıttaki id'yi buraya ekleyin."),
            wraplength=520, justify="left", text_color="gray").pack(
            anchor="w", padx=12, pady=(4, 0))

    def _parse_chat_ids(self):
        ids = []
        for part in self.chat_ids_var.get().split(","):
            part = part.strip()
            if part:
                try:
                    ids.append(int(part))
                except ValueError:
                    self.log(f"geçersiz chat_id: {part!r}")
        return ids

    def apply(self) -> None:
        self.config.set("telegram.enabled", bool(self.enabled.get()))
        self.token = self.token_var.get().strip()
        self.config.set("telegram.token", self.token)
        self.config.set("telegram.authorized_chat_ids", self._parse_chat_ids())
        self.config.set("telegram.notify", {
            "captcha": bool(self.n_captcha.get()),
            "chat": bool(self.n_chat.get()),
            "errors": bool(self.n_errors.get()),
        })
        self.log("telegram ayarları uygulandı")

    def get_token(self) -> str:
        return self.token or self.token_var.get().strip()

    def send_test(self) -> None:
        """Fire a one-off test message using the current settings."""
        self.apply()
        from ..remote.telegram import TelegramBridge
        from ..remote.controller import BotController

        bridge = TelegramBridge(self.config, BotController(self.config),
                                token=self.get_token())
        if not bridge.configured:
            self.log("telegram test: token yok")
            return
        if not bridge.authorized:
            self.log("telegram test: yetkili chat_id yok")
            return
        bridge.send_message("✅ Test mesajı — balık botu bağlantısı çalışıyor.")
        self.log("telegram test mesajı gönderildi")
