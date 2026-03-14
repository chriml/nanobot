"""Audio transcription providers."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import tempfile
from pathlib import Path

from loguru import logger


class LocalWhisperTranscriptionProvider:
    """Run local OpenAI Whisper CLI for zero-cost transcription."""

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

    def is_available(self) -> bool:
        """Return True when the configured Whisper command is installed."""
        return bool(self.command) and shutil.which(self.command[0]) is not None

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

    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file using the local Whisper CLI.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text.
        """
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
