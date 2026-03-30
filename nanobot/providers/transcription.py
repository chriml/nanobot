"""Audio transcription providers."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class LocalWhisperTranscriptionProvider:
    """Run local Faster-Whisper for zero-cost transcription."""

    def __init__(
        self,
        model: str | None = None,
        language: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        download_root: str | None = None,
    ):
        self.model = model or os.environ.get("NANOBOT_TRANSCRIBE_MODEL", "base")
        self.language = language or os.environ.get("NANOBOT_TRANSCRIBE_LANGUAGE")
        self.device = device or os.environ.get("NANOBOT_TRANSCRIBE_DEVICE", "auto")
        self.compute_type = compute_type or os.environ.get("NANOBOT_TRANSCRIBE_COMPUTE_TYPE", "int8")
        self.download_root = str(
            Path(download_root or os.environ.get("NANOBOT_TRANSCRIBE_DOWNLOAD_ROOT", "~/.cache/whisper"))
            .expanduser()
        )
        self._model_instance: Any | None = None

    def is_available(self) -> bool:
        """Return True when faster-whisper can be imported."""
        try:
            import faster_whisper  # noqa: F401
        except Exception:
            return False
        return True

    def _get_model(self):
        if self._model_instance is not None:
            return self._model_instance

        from faster_whisper import WhisperModel

        self._model_instance = WhisperModel(
            self.model,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root,
        )
        return self._model_instance

    def _transcribe_sync(self, file_path: Path) -> str:
        model = self._get_model()
        kwargs: dict[str, Any] = {"vad_filter": True}
        if self.language:
            kwargs["language"] = self.language
        segments, _info = model.transcribe(str(file_path), **kwargs)
        return " ".join(segment.text.strip() for segment in segments if segment.text).strip()

    async def transcribe(self, file_path: str | Path) -> str:
        """Transcribe an audio file using Faster-Whisper."""
        if not self.is_available():
            return ""

        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._transcribe_sync, path),
                timeout=300.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Local Faster-Whisper transcription timed out for {}", path.name)
            return ""
        except Exception as e:
            logger.warning("Local Faster-Whisper transcription failed for {}: {}", path.name, e)
            return ""


class GroqTranscriptionProvider:
    """Use Groq Whisper API as a fallback transcription provider."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, file_path: str | Path) -> str:
        """Transcribe an audio file using Groq."""
        if not self.api_key:
            logger.warning("Groq API key not configured for transcription")
            return ""

        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    files = {
                        "file": (path.name, f),
                        "model": (None, "whisper-large-v3"),
                    }
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data.get("text", "")
        except Exception as e:
            logger.error("Groq transcription error: {}", e)
            return ""
