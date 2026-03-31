"""Wrapper CLI that injects the workspace git sync hook."""

from __future__ import annotations

from functools import wraps
import os
from pathlib import Path
from typing import Any

from nanobot.agent.loop import AgentLoop
from nanobot.cli.commands import app
from nanobot.workspace_git import DEFAULT_COMMIT_MESSAGE, WorkspaceGitSyncHook


def install_workspace_git_hook() -> None:
    """Patch AgentLoop so all CLI-created loops include the git sync hook."""
    if getattr(AgentLoop, "_workspace_git_hook_installed", False):
        return

    original_init = AgentLoop.__init__

    @wraps(original_init)
    def patched_init(self: AgentLoop, *args: Any, **kwargs: Any) -> None:
        hooks = list(kwargs.pop("hooks", []) or [])
        workspace = _resolve_workspace_arg(args, kwargs)

        if workspace is not None and not any(isinstance(h, WorkspaceGitSyncHook) for h in hooks):
            hooks.append(_build_workspace_git_hook(Path(workspace)))

        kwargs["hooks"] = hooks
        original_init(self, *args, **kwargs)

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


def _build_workspace_git_hook(workspace: Path) -> WorkspaceGitSyncHook:
    return WorkspaceGitSyncHook(
        workspace,
        remote=os.environ.get("NANOBOT_GIT_HOOK_REMOTE", "origin"),
        branch=os.environ.get("NANOBOT_GIT_HOOK_BRANCH", "main"),
        commit_message=os.environ.get(
            "NANOBOT_GIT_HOOK_COMMIT_MESSAGE",
            DEFAULT_COMMIT_MESSAGE,
        ),
        sync_on_errors=os.environ.get("NANOBOT_GIT_HOOK_SYNC_ERRORS", "1") != "0",
    )


__all__ = ["install_workspace_git_hook", "main"]


if __name__ == "__main__":
    main()
