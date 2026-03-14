from types import SimpleNamespace
from types import ModuleType
import sys

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

    class FakeLocalWhisper:
        def __init__(self) -> None:
            pass

        async def transcribe(self, file_path: str) -> str:
            return "local transcript"

    transcription_module = ModuleType("nanobot.providers.transcription")
    transcription_module.LocalWhisperTranscriptionProvider = FakeLocalWhisper
    providers_package = ModuleType("nanobot.providers")
    providers_package.__path__ = []
    providers_package.transcription = transcription_module

    monkeypatch.setitem(sys.modules, "nanobot.providers", providers_package)
    monkeypatch.setitem(sys.modules, "nanobot.providers.transcription", transcription_module)

    assert await channel.transcribe_audio("voice.ogg") == "local transcript"


@pytest.mark.asyncio
async def test_transcribe_audio_returns_empty_when_local_whisper_has_no_result(monkeypatch) -> None:
    channel = _DummyChannel(SimpleNamespace(allow_from=["*"]), MessageBus())

    class FakeLocalWhisper:
        def __init__(self) -> None:
            pass

        async def transcribe(self, file_path: str) -> str:
            return ""

    transcription_module = ModuleType("nanobot.providers.transcription")
    transcription_module.LocalWhisperTranscriptionProvider = FakeLocalWhisper
    providers_package = ModuleType("nanobot.providers")
    providers_package.__path__ = []
    providers_package.transcription = transcription_module

    monkeypatch.setitem(sys.modules, "nanobot.providers", providers_package)
    monkeypatch.setitem(sys.modules, "nanobot.providers.transcription", transcription_module)

    assert await channel.transcribe_audio("voice.ogg") == ""
