"""Tests for workspace GitHub bootstrap."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nanobot.config.schema import WorkspaceGitConfig
from nanobot.workspace_git import bootstrap_workspace_git


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
