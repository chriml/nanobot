"""Audio transcription providers."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import tempfile
from pathlib import Path

import httpx
from loguru import logger


class LocalWhisperTranscriptionProvider:
    """Run local Whisper CLI for zero-cost transcription."""

    def __init__(
        self,
        command: str | None = None,
        model: str | None = None,
        language: str | None = None,
    ):
        raw_command = command or os.environ.get("NANOBOT_TRANSCRIBE_COMMAND")
        self.command = self._resolve_command(raw_command)
        self.model = model or os.environ.get("NANOBOT_TRANSCRIBE_MODEL", "base")
        self.language = language or os.environ.get("NANOBOT_TRANSCRIBE_LANGUAGE")

    def _resolve_command(self, raw_command: str | None) -> list[str]:
        """Pick an explicit command first, then common local defaults."""
        if raw_command:
            return shlex.split(raw_command)
        if shutil.which("whisper"):
            return ["whisper"]

        repo_python = Path(__file__).resolve().parents[2] / ".venv-whisper" / "bin" / "python"
        if repo_python.exists():
            return [str(repo_python), "-m", "whisper"]

        cwd_python = Path.cwd() / ".venv-whisper" / "bin" / "python"
        if cwd_python.exists():
            return [str(cwd_python), "-m", "whisper"]

        return ["whisper"]

    def is_available(self) -> bool:
        """Return True when the configured Whisper command is installed."""
        if not self.command:
            return False
        executable = Path(self.command[0]).expanduser()
        if executable.exists():
            return os.access(executable, os.X_OK)
        return shutil.which(self.command[0]) is not None

    async def transcribe(self, file_path: str | Path) -> str:
        """Transcribe an audio file using the local Whisper CLI."""
        if not self.is_available():
            return ""

        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        with tempfile.TemporaryDirectory(prefix="nanobot-whisper-") as output_dir:
            command = [
                *self.command,
                str(path),
                "--model",
                self.model,
                "--output_format",
                "txt",
                "--output_dir",
                output_dir,
                "--fp16",
                "False",
            ]
            if self.language:
                command.extend(["--language", self.language])

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                logger.warning("Local Whisper transcription timed out for {}", path.name)
                return ""

            if process.returncode != 0:
                logger.warning(
                    "Local Whisper transcription failed for {}: {}",
                    path.name,
                    stderr.decode("utf-8", "ignore").strip(),
                )
                return ""

            transcript_path = Path(output_dir) / f"{path.stem}.txt"
            if not transcript_path.exists():
                logger.warning("Local Whisper did not produce transcript output for {}", path.name)
                return ""

            return transcript_path.read_text(encoding="utf-8").strip()


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
