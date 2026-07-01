import numpy as np

from metin2fishbot.core.config import Config
from metin2fishbot.core.events import EventBus
from metin2fishbot.remote.telegram import TelegramBridge


class FakeController:
    def __init__(self):
        self.calls = []

    def start(self):
        self.calls.append("start")
        return True

    def stop(self):
        self.calls.append("stop")

    def pause(self):
        self.calls.append("pause")

    def resume(self):
        self.calls.append("resume")

    def status(self):
        return {"running": True, "state": "cast", "system": "auto",
                "dry_run": True, "uptime_s": 10, "actions": 3, "casts": 2,
                "burns": 1, "captchas": 0}

    def screenshot(self):
        return np.zeros((10, 10, 3), np.uint8)


def _bridge(**cfg_over):
    data = {"telegram": {"enabled": True, "authorized_chat_ids": [111],
                         "notify": {"captcha": True, "chat": True, "errors": True},
                         "poll_timeout": 1, "send_screenshot_on_captcha": True}}
    data["telegram"].update(cfg_over)
    ctrl = FakeController()
    bridge = TelegramBridge(Config(data), ctrl, bus=EventBus(), token="TESTTOKEN")
    return bridge, ctrl


def test_unauthorized_chat_rejected():
    bridge, ctrl = _bridge()
    reply = bridge.handle_command("/stop", 999)
    assert "999" in reply and "yetkili" in reply.lower()
    assert ctrl.calls == []  # controller never touched


def test_authorized_commands_dispatch():
    bridge, ctrl = _bridge()
    assert bridge.handle_command("/start", 111) == "başlatıldı"
    assert bridge.handle_command("/pause", 111) == "duraklatıldı"
    assert bridge.handle_command("/resume", 111) == "devam ediliyor"
    assert bridge.handle_command("/stop", 111) == "durduruldu"
    assert ctrl.calls == ["start", "pause", "resume", "stop"]


def test_status_command_formats():
    bridge, _ = _bridge()
    reply = bridge.handle_command("/status", 111)
    assert "cast" in reply and "captcha" in reply


def test_dryrun_command_updates_config():
    bridge, _ = _bridge()
    assert "False" in bridge.handle_command("/dryrun off", 111)
    assert bridge.cfg.get("runtime.dry_run") is False
    assert "True" in bridge.handle_command("/dryrun on", 111)
    assert bridge.cfg.get("runtime.dry_run") is True


def test_screenshot_command_sends_photo(monkeypatch):
    bridge, _ = _bridge()
    sent = {}
    monkeypatch.setattr(bridge, "send_photo",
                        lambda frame, caption="", chat_id=None: sent.update(
                            {"frame": frame, "chat": chat_id}))
    reply = bridge.handle_command("/screenshot", 111)
    assert reply == ""              # photo sent separately, no text
    assert sent["chat"] == 111
    assert sent["frame"].shape == (10, 10, 3)


def test_command_with_bot_username_suffix():
    bridge, ctrl = _bridge()
    # Telegram sends "/status@MyBot" in groups
    reply = bridge.handle_command("/status@MyFishBot", 111)
    assert "cast" in reply


def test_handle_update_advances_offset_and_dispatches(monkeypatch):
    bridge, ctrl = _bridge()
    sent = []
    monkeypatch.setattr(bridge, "send_message",
                        lambda text, chat_id=None: sent.append((text, chat_id)))
    update = {"update_id": 42,
              "message": {"chat": {"id": 111}, "text": "/pause"}}
    bridge._handle_update(update)
    assert bridge._offset == 43
    assert ctrl.calls == ["pause"]
    assert sent and sent[0][1] == 111


def test_send_message_posts_to_authorized(monkeypatch):
    bridge, _ = _bridge()
    posts = []
    monkeypatch.setattr(bridge.session, "post",
                        lambda url, **kw: posts.append((url, kw)) or _Resp())
    bridge.send_message("hi")
    assert len(posts) == 1
    assert posts[0][0].endswith("/sendMessage")
    assert posts[0][1]["data"]["chat_id"] == 111
    assert posts[0][1]["data"]["text"] == "hi"


def test_notify_event_enqueues_without_network():
    bridge, _ = _bridge()
    from metin2fishbot.core.events import Event
    bridge._on_event(Event(type="captcha", payload={"frame": None}))
    # captcha text enqueued (frame None -> no photo item)
    kind, payload = bridge._outbox.get_nowait()
    assert kind == "text" and "CAPTCHA" in payload


class _Resp:
    status_code = 200

    def json(self):
        return {"result": []}
