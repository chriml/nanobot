"""Repository auto-update service."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger

from nanobot.config.schema import UpdatesConfig


class AutoUpdateService:
    """Periodically sync a git checkout and trigger a restart when it changes."""

    def __init__(
        self,
        config: UpdatesConfig,
        on_updated: Callable[[], Awaitable[None]] | None = None,
        repo_root: Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        self.config = config
        self.on_updated = on_updated
        self.repo_root = repo_root or self._find_repo_root()
        self._runner = runner or subprocess.run
        self._running = False
        self._task: asyncio.Task | None = None

    @staticmethod
    def _find_repo_root() -> Path | None:
        for candidate in [Path.cwd(), *Path(__file__).resolve().parents]:
            if (candidate / ".git").exists():
                return candidate
        return None

    def _run(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not self.repo_root:
            raise RuntimeError("repo root not found")
        result = self._runner(
            args,
            cwd=self.repo_root,
            env=env,
            text=True,
            capture_output=True,
        )
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"command failed: {' '.join(args)}")
        return result

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self._run(["git", *args], check=check)

    def _sync_ff_only(self) -> bool:
        current_branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if current_branch != self.config.branch:
            logger.debug(
                "Auto-update: current branch {} != configured branch {}, skipping ff_only sync",
                current_branch,
                self.config.branch,
            )
            return False

        old_head = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("fetch", self.config.remote, "--prune")
        remote_ref = f"{self.config.remote}/{self.config.branch}"
        remote_head = self._git("rev-parse", remote_ref).stdout.strip()
        if old_head == remote_head:
            return False

        ancestor = self._git("merge-base", "--is-ancestor", old_head, remote_head, check=False)
        if ancestor.returncode != 0:
            logger.warning("Auto-update: local branch is not a fast-forward of {}", remote_ref)
            return False

        self._git("merge", "--ff-only", remote_ref)
        new_head = self._git("rev-parse", "HEAD").stdout.strip()
        return new_head != old_head

    def _sync_local_branch(self) -> bool:
        current_branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if current_branch != self.config.local_branch:
            logger.debug(
                "Auto-update: current branch {} != configured local branch {}, skipping local_branch sync",
                current_branch,
                self.config.local_branch,
            )
            return False

        script = self.repo_root / "scripts" / "sync-local-branch.sh"
        if not script.exists():
            logger.warning("Auto-update: sync script not found at {}", script)
            return False

        old_head = self._git("rev-parse", "HEAD").stdout.strip()
        env = {
            **os.environ,
            "UPSTREAM_REMOTE": self.config.remote,
            "UPSTREAM_BRANCH": self.config.branch,
            "BASE_BRANCH": self.config.branch,
            "LOCAL_BRANCH": self.config.local_branch,
        }
        self._run([str(script)], env=env)
        new_head = self._git("rev-parse", "HEAD").stdout.strip()
        return new_head != old_head

    def _sync_once(self) -> bool:
        if not self.repo_root:
            logger.debug("Auto-update: no git repo detected, skipping")
            return False

        dirty = self._git("status", "--porcelain", check=False).stdout.strip()
        if dirty:
            logger.warning("Auto-update: worktree is dirty, skipping")
            return False

        if self.config.mode == "local_branch":
            return self._sync_local_branch()
        return self._sync_ff_only()

    async def _tick(self) -> None:
        updated = await asyncio.to_thread(self._sync_once)
        if updated and self.on_updated:
            logger.info("Auto-update: repository advanced, restarting process")
            await self.on_updated()

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.config.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Auto-update failed: {}", e)

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("Auto-update disabled")
            return
        if self._running:
            logger.warning("Auto-update already running")
            return
        if not self.repo_root:
            logger.warning("Auto-update enabled but no git checkout was detected")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Auto-update started (every {}s)", self.config.interval_s)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
