"""Wrapper CLI that injects the workspace git sync hook."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from functools import wraps
import os
from pathlib import Path
import subprocess
from typing import Any

from loguru import logger

from nanobot.agent.hook import AgentHook, AgentHookContext
from nanobot.agent.loop import AgentLoop
from nanobot.agent.runner import AgentRunSpec
from nanobot.cli.commands import app
from nanobot.config.loader import load_config
from nanobot.config.schema import WorkspaceGitConfig
from nanobot.workspace_git import (
    DEFAULT_COMMIT_MESSAGE,
    WorkspaceGitSyncHook,
    prepare_workspace_git_access,
    refresh_workspace_repo,
)


def install_workspace_git_hook() -> None:
    """Patch AgentLoop so all CLI-created loops include the git sync hook."""
    if getattr(AgentLoop, "_workspace_git_hook_installed", False):
        return

    original_init = AgentLoop.__init__

    @wraps(original_init)
    def patched_init(self: AgentLoop, *args: Any, **kwargs: Any) -> None:
        workspace = _resolve_workspace_arg(args, kwargs)
        original_init(self, *args, **kwargs)
        if workspace is None:
            return
        if getattr(self.runner, "_workspace_git_hook_installed", False):
            return

        workspace_hook = _build_workspace_git_hook(Path(workspace))
        if workspace_hook is None:
            return
        original_run = self.runner.run

        @wraps(original_run)
        async def patched_run(spec: AgentRunSpec):
            await _prepare_workspace_before_run(workspace_hook)
            hook = _CombinedHook(spec.hook or AgentHook(), workspace_hook)
            return await original_run(replace(spec, hook=hook))

        self.runner.run = patched_run  # type: ignore[method-assign]
        self.runner._workspace_git_hook_installed = True  # type: ignore[attr-defined]
        self._workspace_git_sync_hook = workspace_hook  # type: ignore[attr-defined]

    AgentLoop.__init__ = patched_init  # type: ignore[method-assign]
    AgentLoop._workspace_git_hook_installed = True  # type: ignore[attr-defined]


def main() -> None:
    """Run the standard CLI with the workspace git hook injected."""
    install_workspace_git_hook()
    app()


def _resolve_workspace_arg(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if "workspace" in kwargs:
        return kwargs["workspace"]
    if len(args) >= 3:
        return args[2]
    return None


def _build_workspace_git_hook(workspace: Path) -> WorkspaceGitSyncHook | None:
    config = _load_workspace_git_config()
    if config is None:
        return None
    prepare_workspace_git_access(workspace)
    if not _workspace_has_git_setup(workspace, remote=config.remote):
        return None

    return WorkspaceGitSyncHook(
        workspace,
        remote=os.environ.get("NANOBOT_GIT_HOOK_REMOTE", config.remote),
        branch=os.environ.get("NANOBOT_GIT_HOOK_BRANCH", config.branch),
        commit_message=os.environ.get(
            "NANOBOT_GIT_HOOK_COMMIT_MESSAGE",
            DEFAULT_COMMIT_MESSAGE,
        ),
        sync_on_errors=os.environ.get("NANOBOT_GIT_HOOK_SYNC_ERRORS", "1") != "0",
        github_token=config.github_token,
    )


def _load_workspace_git_config() -> WorkspaceGitConfig | None:
    try:
        config = load_config()
    except Exception as exc:
        logger.debug("Workspace git hook config load skipped: {}", exc)
        return None
    if not config.workspace_git.enabled:
        return None
    return config.workspace_git


def _workspace_has_git_setup(workspace: Path, *, remote: str) -> bool:
    if not (workspace / ".git").exists():
        return False
    try:
        completed = subprocess.run(
            ["git", "config", "--get", f"remote.{remote}.url"],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return bool(completed.stdout.strip())


async def _prepare_workspace_before_run(hook: WorkspaceGitSyncHook) -> None:
    try:
        await asyncio.to_thread(prepare_workspace_git_access, hook.workspace)
        result = await asyncio.to_thread(
            refresh_workspace_repo,
            hook.workspace,
            remote=hook.remote,
            branch=hook.branch,
            github_token=hook.github_token,
        )
    except Exception as exc:
        logger.warning("Workspace git pre-run sync skipped: {}", exc)
        return

    if result not in {"up_to_date", "updated"}:
        logger.info("Workspace git pre-run sync result: {}", result)


class _CombinedHook(AgentHook):
    def __init__(self, primary: AgentHook, extra: AgentHook) -> None:
        self._primary = primary
        self._extra = extra

    def wants_streaming(self) -> bool:
        return self._primary.wants_streaming() or self._extra.wants_streaming()

    async def before_iteration(self, context: AgentHookContext) -> None:
        await self._primary.before_iteration(context)
        await self._extra.before_iteration(context)

    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        await self._primary.on_stream(context, delta)
        await self._extra.on_stream(context, delta)

    async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
        await self._primary.on_stream_end(context, resuming=resuming)
        await self._extra.on_stream_end(context, resuming=resuming)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        await self._primary.before_execute_tools(context)
        await self._extra.before_execute_tools(context)

    async def after_iteration(self, context: AgentHookContext) -> None:
        await self._primary.after_iteration(context)
        await self._extra.after_iteration(context)

    def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
        return self._extra.finalize_content(
            context,
            self._primary.finalize_content(context, content),
        )


__all__ = ["install_workspace_git_hook", "main"]


if __name__ == "__main__":
    main()
