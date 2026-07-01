"""Telegram remote control + notifications via the raw Bot HTTP API.

No heavy dependency: uses ``requests`` with long-polling ``getUpdates`` on a
background thread, and ``sendMessage`` / ``sendPhoto`` for replies and alerts.
Commands drive a ``BotController``; only authorized chat ids may issue them.
EventBus events (captcha / chat / errors) are forwarded as notifications.
"""
from __future__ import annotations

import os
import queue
import threading
import time
from typing import List, Optional

import requests

from ..core.config import Config
from ..core.events import Event, EventBus
from .controller import BotController

HELP_TEXT = (
    "Komutlar (çoklu istemcide sona istemci no ekleyin, örn: /pause 2):\n"
    "/start - botu başlat\n"
    "/stop - botu durdur\n"
    "/pause [n] - duraklat (tümü ya da #n)\n"
    "/resume [n] - devam et (tümü ya da #n)\n"
    "/status [n] - durum + istatistik\n"
    "/screenshot [n] - anlık ekran görüntüsü\n"
    "/dryrun on|off - kuru çalışma modu\n"
    "/help - bu yardım"
)


class TelegramBridge:
    def __init__(self, config: Config, controller: BotController,
                 bus: Optional[EventBus] = None, token: Optional[str] = None):
        self.cfg = config
        self.controller = controller
        self.bus = bus or EventBus()
        self.token = (token or config.get("telegram.token")
                      or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        self.authorized: List[int] = [
            int(c) for c in (config.get("telegram.authorized_chat_ids") or [])]
        self.notify = config.get("telegram.notify", {}) or {}
        self.poll_timeout = int(config.get("telegram.poll_timeout", 25))
        self.send_shot_on_captcha = config.get(
            "telegram.send_screenshot_on_captcha", True)

        self.session = requests.Session()
        self._offset = 0
        self._thread: Optional[threading.Thread] = None
        self._sender: Optional[threading.Thread] = None
        # Notifications are enqueued and sent from a dedicated thread so a slow
        # network call never blocks the bot/chat threads that publish events.
        self._outbox: "queue.Queue" = queue.Queue()
        self._running = False

    # -- config helpers -----------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def _is_authorized(self, chat_id: int) -> bool:
        return chat_id in self.authorized

    # -- outbound -----------------------------------------------------------
    def send_message(self, text: str, chat_id: Optional[int] = None) -> None:
        if not self.configured:
            return
        targets = [chat_id] if chat_id is not None else self.authorized
        for cid in targets:
            try:
                self.session.post(self._url("sendMessage"),
                                  data={"chat_id": cid, "text": text},
                                  timeout=10)
            except Exception as exc:
                self.bus.log(f"[telegram] send hata: {exc}", "debug")

    def send_photo(self, frame, caption: str = "",
                   chat_id: Optional[int] = None) -> None:
        if not self.configured or frame is None:
            return
        import cv2

        ok, buf = cv2.imencode(".png", frame)
        if not ok:
            return
        targets = [chat_id] if chat_id is not None else self.authorized
        for cid in targets:
            try:
                self.session.post(
                    self._url("sendPhoto"),
                    data={"chat_id": cid, "caption": caption},
                    files={"photo": ("shot.png", buf.tobytes(), "image/png")},
                    timeout=20)
            except Exception as exc:
                self.bus.log(f"[telegram] photo hata: {exc}", "debug")

    # -- commands -----------------------------------------------------------
    def handle_command(self, text: str, chat_id: int) -> str:
        """Execute a command from an authorized chat; returns the reply text."""
        if not self._is_authorized(chat_id):
            self.bus.log(f"[telegram] yetkisiz chat_id: {chat_id}", "warning")
            return (f"Yetkili değilsiniz. chat_id'niz: {chat_id}\n"
                    "Bunu config telegram.authorized_chat_ids listesine ekleyin.")

        parts = text.strip().split()
        cmd = parts[0].lower().lstrip("/").split("@")[0] if parts else ""
        arg = parts[1].lower() if len(parts) > 1 else ""
        # Optional 1-based client index for multi-client (e.g. "/pause 2").
        index = int(arg) if arg.isdigit() else None

        if cmd == "start":
            return "başlatıldı" if self.controller.start() else "başlatılamadı"
        if cmd == "stop":
            self.controller.stop()
            return "durduruldu"
        if cmd == "pause":
            self.controller.pause(index=index)
            return f"duraklatıldı{f' (#{index})' if index else ''}"
        if cmd == "resume":
            self.controller.resume(index=index)
            return f"devam ediliyor{f' (#{index})' if index else ''}"
        if cmd == "status":
            return self._format_status(self.controller.status(index=index))
        if cmd == "screenshot":
            frame = self.controller.screenshot(index=index)
            if frame is None:
                return "ekran görüntüsü alınamadı"
            self.send_photo(frame, caption=f"ekran görüntüsü{f' #{index}' if index else ''}",
                            chat_id=chat_id)
            return ""  # photo sent separately
        if cmd == "dryrun":
            if arg in ("on", "off"):
                self.cfg.set("runtime.dry_run", arg == "on")
                return f"dry_run = {arg == 'on'}"
            return "kullanım: /dryrun on|off"
        if cmd in ("help", "start_help"):
            return HELP_TEXT
        return f"bilinmeyen komut: {cmd}\n{HELP_TEXT}"

    @classmethod
    def _format_status(cls, s) -> str:
        # Multi-client: a list of per-client status dicts.
        if isinstance(s, list):
            if not s:
                return "durum: istemci yok"
            return "\n\n".join(
                f"#{item.get('index', i + 1)} [{item.get('label', '')}]\n"
                + cls._format_one(item)
                for i, item in enumerate(s))
        return cls._format_one(s)

    @staticmethod
    def _format_one(s: dict) -> str:
        if not s.get("running"):
            return "durum: durdu"
        return (
            f"durum: {s.get('state')}"
            + (" (duraklatıldı)" if s.get("paused") else "")
            + f"\nsistem: {s.get('system')} | dry_run: {s.get('dry_run')}"
            + f"\nsüre: {s.get('uptime_s', 0)}s | eylem: {s.get('actions', 0)}"
            + f"\ncast: {s.get('casts', 0)} | yaktırılan: {s.get('burns', 0)}"
            + f" | captcha: {s.get('captchas', 0)}")

    # -- polling ------------------------------------------------------------
    def _handle_update(self, update: dict) -> None:
        self._offset = max(self._offset, update.get("update_id", 0) + 1)
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        if chat_id is None or not text:
            return
        reply = self.handle_command(text, int(chat_id))
        if reply:
            self.send_message(reply, chat_id=int(chat_id))

    def _poll_once(self) -> None:
        resp = self.session.get(
            self._url("getUpdates"),
            params={"offset": self._offset, "timeout": self.poll_timeout},
            timeout=self.poll_timeout + 10)
        data = resp.json()
        for update in data.get("result", []):
            self._handle_update(update)

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._poll_once()
            except Exception as exc:
                self.bus.log(f"[telegram] poll hata: {exc}", "debug")
                time.sleep(3)

    def _sender_loop(self) -> None:
        while self._running:
            try:
                item = self._outbox.get(timeout=0.5)
            except queue.Empty:
                continue
            kind, payload = item
            if kind == "text":
                self.send_message(payload)
            elif kind == "photo":
                frame, caption = payload
                self.send_photo(frame, caption=caption)

    def _notify(self, text: Optional[str] = None, frame=None,
                caption: str = "") -> None:
        """Enqueue a notification (non-blocking) to all authorized chats."""
        if text is not None:
            self._outbox.put(("text", text))
        if frame is not None:
            self._outbox.put(("photo", (frame, caption)))

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        if not self.configured:
            self.bus.log("[telegram] token yok; devre dışı", "warning")
            return
        self.bus.subscribe(self._on_event)
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self._sender = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender.start()
        self.bus.log("[telegram] köprü başlatıldı")
        self._notify("🎣 Balık botu Telegram köprüsü aktif. /help")

    def stop(self) -> None:
        self._running = False
        self.bus.unsubscribe(self._on_event)
        if self._thread:
            self._thread.join(timeout=3)
        if self._sender:
            self._sender.join(timeout=2)

    # -- notifications ------------------------------------------------------
    def _on_event(self, event: Event) -> None:
        try:
            if event.type == "captcha" and self.notify.get("captcha", True):
                frame = (event.payload.get("frame")
                         if self.send_shot_on_captcha else None)
                client = event.payload.get("client", "")
                self._notify(
                    f"⚠️ CAPTCHA algılandı ({client}) — bot duraklatıldı. "
                    "Çözdükten sonra /resume gönderin.",
                    frame=frame, caption="captcha")
            elif event.type == "chat_incoming" and self.notify.get("chat", True):
                line = event.payload.get("line", "")
                reply = event.payload.get("reply", "")
                self._notify(f"💬 Gelen: {line}\n🤖 Yanıt: {reply}")
            elif event.type == "bot_stopped" and self.notify.get("errors", True):
                self._notify("⏹️ Bot durdu.")
            elif event.type == "log" and self.notify.get("errors", True):
                if event.payload.get("level") in ("error", "warning"):
                    self._notify(f"❗ {event.payload.get('message', '')}")
        except Exception:
            pass  # a notification failure must never break the bus
