"""Tests for workspace git bootstrap and sync helpers."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from nanobot.agent.hook import AgentHookContext
from nanobot.config.schema import WorkspaceGitConfig
from nanobot.workspace_git import (
    WorkspaceGitSyncHook,
    bootstrap_workspace_git,
    sync_workspace_repo,
)


def _git(workspace: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_bootstrap_workspace_git_creates_remote_and_initial_commit(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("hello\n", encoding="utf-8")
    _git(workspace, "init", "-q")

    pushed: list[tuple[str, str]] = []
    monkeypatch.setattr("nanobot.workspace_git._github_login", lambda _token: "octocat")
    monkeypatch.setattr(
        "nanobot.workspace_git._ensure_github_repo",
        lambda **_kwargs: ("https://github.com/octocat/alpha-bot.git", True),
    )
    monkeypatch.setattr(
        "nanobot.workspace_git._push",
        lambda _workspace, *, remote, branch, token, set_upstream: pushed.append((remote, branch)),
    )

    result = bootstrap_workspace_git(
        workspace,
        bot_name="Alpha Bot",
        config=WorkspaceGitConfig(enabled=True, github_token="ghp_test", repo="alpha-bot"),
    )

    assert result is not None
    assert result.owner == "octocat"
    assert result.repo == "alpha-bot"
    assert result.created_repo is True
    assert result.configured_remote is True
    assert result.pushed is True
    assert result.push_skipped_reason is None
    assert _git(workspace, "remote", "get-url", "origin") == "https://github.com/octocat/alpha-bot.git"
    assert _git(workspace, "rev-parse", "--verify", "HEAD")
    assert pushed == [("origin", "main")]


def test_bootstrap_workspace_git_skips_push_for_dirty_existing_repo(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("hello\n", encoding="utf-8")
    _git(workspace, "init", "-q")
    _git(workspace, "add", "-A")
    _git(
        workspace,
        "-c",
        "user.name=Tester",
        "-c",
        "user.email=tester@example.com",
        "commit",
        "-m",
        "init",
    )
    (workspace / "README.md").write_text("changed\n", encoding="utf-8")

    monkeypatch.setattr("nanobot.workspace_git._github_login", lambda _token: "octocat")
    monkeypatch.setattr(
        "nanobot.workspace_git._ensure_github_repo",
        lambda **_kwargs: ("https://github.com/octocat/alpha-bot.git", False),
    )
    pushed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "nanobot.workspace_git._push",
        lambda _workspace, *, remote, branch, token, set_upstream: pushed.append((remote, branch)),
    )

    result = bootstrap_workspace_git(
        workspace,
        bot_name="Alpha Bot",
        config=WorkspaceGitConfig(enabled=True, github_token="ghp_test", repo="alpha-bot"),
    )

    assert result is not None
    assert result.created_repo is False
    assert result.pushed is False
    assert "uncommitted changes" in (result.push_skipped_reason or "")
    assert _git(workspace, "remote", "get-url", "origin") == "https://github.com/octocat/alpha-bot.git"
    assert pushed == []


def _init_workspace_repo(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    workspace = tmp_path / "workspace"

    _git(tmp_path, "init", "--bare", str(remote))
    _git(tmp_path, "clone", str(remote), str(workspace))
    _git(workspace, "checkout", "-b", "main")
    _git(workspace, "config", "user.name", "Nanobot")
    _git(workspace, "config", "user.email", "nanobot@example.com")

    (workspace / "README.md").write_text("initial\n", encoding="utf-8")
    _git(workspace, "add", "README.md")
    _git(workspace, "commit", "-m", "initial")
    _git(workspace, "push", "-u", "origin", "main")

    return workspace, remote


def test_sync_workspace_repo_commits_and_pushes_changes(tmp_path: Path) -> None:
    workspace, remote = _init_workspace_repo(tmp_path)

    (workspace / "notes.txt").write_text("synced\n", encoding="utf-8")
    result = sync_workspace_repo(workspace)

    assert result == "synced"
    assert _git(workspace, "status", "--porcelain") == ""
    pushed = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "refs/heads/main:notes.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert pushed.stdout == "synced\n"


def test_sync_workspace_repo_skips_nested_workspace(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / "nested-workspace"

    repo.mkdir()
    workspace.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Nanobot")
    _git(repo, "config", "user.email", "nanobot@example.com")
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    result = sync_workspace_repo(workspace)

    assert result == "workspace_not_repo_root"


def test_workspace_git_sync_hook_only_runs_on_completed_turn(monkeypatch, tmp_path: Path) -> None:
    seen: list[Path] = []
    hook = WorkspaceGitSyncHook(tmp_path)

    def fake_sync(workspace: Path, **_kwargs) -> str:
        seen.append(workspace)
        return "synced"

    monkeypatch.setattr("nanobot.workspace_git.sync_workspace_repo", fake_sync)

    pending = AgentHookContext(iteration=0, messages=[], stop_reason=None)
    asyncio.run(hook.after_iteration(pending))
    assert seen == []

    completed = AgentHookContext(
        iteration=1,
        messages=[],
        final_content="done",
        stop_reason="completed",
    )
    asyncio.run(hook.after_iteration(completed))
    assert seen == [tmp_path]
