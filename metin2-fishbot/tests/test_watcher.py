from metin2fishbot.chat.watcher import ChatWatcher
from metin2fishbot.core.config import Config
from metin2fishbot.core.input_controller import InputController


def _config(**overrides):
    data = {
        "chat_ai": {
            "enabled": True, "model": "claude-opus-4-8", "max_tokens": 80,
            "poll_interval": 0.01, "reply_cooldown": 5.0, "max_replies": 0,
            "triggers": ["gm"], "persona": "be a player",
        },
        "regions": {"chat": [0, 0, 10, 10]},
    }
    data["chat_ai"].update(overrides)
    return Config(data)


def _make_watcher(cfg):
    ic = InputController(dry_run=True)
    w = ChatWatcher(cfg, capture=None, input_controller=ic, api_key="test-key")
    # Stub the AI responder so no real API call is made.
    w.responder.reply = lambda msg: "hey, busy fishing"
    return w


def test_handle_message_replies_and_records():
    w = _make_watcher(_config())
    reply = w.handle_message("GM: are you botting?")
    assert reply == "hey, busy fishing"
    assert w.reply_count == 1


def test_cooldown_suppresses_second_reply():
    w = _make_watcher(_config(reply_cooldown=999))
    assert w.handle_message("GM: hi") == "hey, busy fishing"
    assert w.handle_message("GM: hi again") is None  # within cooldown
    assert w.reply_count == 1


def test_max_replies_cap():
    w = _make_watcher(_config(max_replies=1, reply_cooldown=0))
    assert w.handle_message("GM: 1") is not None
    assert w.handle_message("GM: 2") is None
    assert w.reply_count == 1


def test_pause_cb_called_around_send():
    w = _make_watcher(_config(reply_cooldown=0))
    events = []
    w.pause_cb = lambda p: events.append(p)
    w.handle_message("GM: hello")
    # paused (True) before typing, resumed (False) after
    assert events == [True, False]


def test_ready_false_without_key():
    cfg = _config()
    ic = InputController(dry_run=True)
    w = ChatWatcher(cfg, capture=None, input_controller=ic, api_key=None)
    # no key + no tesseract in CI -> not ready, and start() is a safe no-op
    assert w.ready is False
    w.start()
    assert w._running is False
