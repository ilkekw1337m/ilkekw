from metin2fishbot.chat.ai_responder import AIResponder
from metin2fishbot.chat.chat_detector import ChatDetector
from metin2fishbot.chat.chat_writer import ChatWriter
from metin2fishbot.core.input_controller import InputController


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class MockMessages:
    def __init__(self, recorder):
        self.recorder = recorder

    def create(self, **kwargs):
        self.recorder["call"] = kwargs
        return _Resp("hey sorry, fishing rn :)")


class MockClient:
    def __init__(self, recorder):
        self.messages = MockMessages(recorder)


def test_ai_responder_builds_correct_request():
    recorder = {}
    responder = AIResponder(
        system_prompt="be a player",
        model="claude-opus-4-8",
        max_tokens=80,
        client=MockClient(recorder),
    )
    assert responder.configured
    reply = responder.reply("are you a bot?")
    assert reply == "hey sorry, fishing rn :)"

    call = recorder["call"]
    assert call["model"] == "claude-opus-4-8"
    assert call["max_tokens"] == 80
    assert call["system"] == "be a player"
    assert call["messages"] == [{"role": "user", "content": "are you a bot?"}]


def test_ai_responder_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    responder = AIResponder(system_prompt="x")
    assert not responder.configured
    assert responder.reply("hi") is None


def test_chat_detector_no_ocr_returns_none():
    det = ChatDetector(triggers=["gm"])
    # Tesseract is not installed in CI; detector degrades gracefully.
    if not det.available:
        import numpy as np
        assert det.poll(np.zeros((20, 80, 3), np.uint8)) is None


def test_chat_detector_trigger_filter_logic():
    det = ChatDetector(triggers=["gm", "admin"])
    assert det._matches_trigger("Hello from GM Bob")
    assert det._matches_trigger("the admin is watching")
    assert not det._matches_trigger("regular player chatter")
    # empty triggers -> matches anything
    det2 = ChatDetector(triggers=[])
    assert det2._matches_trigger("anything at all")


def test_chat_writer_dry_run_logs(capsys):
    ic = InputController(dry_run=True)
    writer = ChatWriter(ic)
    # Should not raise and should send no real input in dry-run.
    writer.send("hello there")
