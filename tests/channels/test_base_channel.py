import sys
from types import ModuleType, SimpleNamespace

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel


class _DummyChannel(BaseChannel):
    name = "dummy"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, msg: OutboundMessage) -> None:
        return None


def test_is_allowed_requires_exact_match() -> None:
    channel = _DummyChannel(SimpleNamespace(allow_from=["allow@email.com"]), MessageBus())

    assert channel.is_allowed("allow@email.com") is True
    assert channel.is_allowed("attacker|allow@email.com") is False


@pytest.mark.asyncio
async def test_transcribe_audio_prefers_local_whisper(monkeypatch) -> None:
    channel = _DummyChannel(SimpleNamespace(allow_from=["*"]), MessageBus())
    channel.transcription_api_key = "groq-key"

    class FakeLocalWhisper:
        def __init__(self) -> None:
            pass

        async def transcribe(self, file_path: str) -> str:
            return "local transcript"

    class FakeGroq:
        def __init__(self, api_key: str | None = None) -> None:
            raise AssertionError("Groq fallback should not be used when local Whisper succeeds")

    transcription_module = ModuleType("nanobot.providers.transcription")
    transcription_module.LocalWhisperTranscriptionProvider = FakeLocalWhisper
    transcription_module.GroqTranscriptionProvider = FakeGroq
    providers_package = ModuleType("nanobot.providers")
    providers_package.__path__ = []
    providers_package.transcription = transcription_module

    monkeypatch.setitem(sys.modules, "nanobot.providers", providers_package)
    monkeypatch.setitem(sys.modules, "nanobot.providers.transcription", transcription_module)

    assert await channel.transcribe_audio("voice.ogg") == "local transcript"


@pytest.mark.asyncio
async def test_transcribe_audio_falls_back_to_groq(monkeypatch) -> None:
    channel = _DummyChannel(SimpleNamespace(allow_from=["*"]), MessageBus())
    channel.transcription_api_key = "groq-key"

    class FakeLocalWhisper:
        def __init__(self) -> None:
            pass

        async def transcribe(self, file_path: str) -> str:
            return ""

    class FakeGroq:
        def __init__(self, api_key: str | None = None) -> None:
            assert api_key == "groq-key"

        async def transcribe(self, file_path: str) -> str:
            return "groq transcript"

    transcription_module = ModuleType("nanobot.providers.transcription")
    transcription_module.LocalWhisperTranscriptionProvider = FakeLocalWhisper
    transcription_module.GroqTranscriptionProvider = FakeGroq
    providers_package = ModuleType("nanobot.providers")
    providers_package.__path__ = []
    providers_package.transcription = transcription_module

    monkeypatch.setitem(sys.modules, "nanobot.providers", providers_package)
    monkeypatch.setitem(sys.modules, "nanobot.providers.transcription", transcription_module)

    assert await channel.transcribe_audio("voice.ogg") == "groq transcript"
