"""Helpers for publishing a workspace to a remote git host."""

from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from nanobot.config.paths import slugify_agent_name
from nanobot.config.schema import WorkspaceGitConfig


@dataclass(slots=True)
class WorkspaceGitBootstrapResult:
    """Outcome of GitHub workspace bootstrap."""

    owner: str
    repo: str
    clone_url: str
    created_repo: bool = False
    configured_remote: bool = False
    pushed: bool = False
    push_skipped_reason: str | None = None


def bootstrap_workspace_git(
    workspace: Path,
    *,
    bot_name: str,
    config: WorkspaceGitConfig,
) -> WorkspaceGitBootstrapResult | None:
    """Create/configure the remote and push an initial clean workspace state."""
    if not config.enabled or config.provider != "github" or not config.github_token.strip():
        return None

    owner = _github_login(config.github_token)
    repo = config.repo.strip() or slugify_agent_name(bot_name) or workspace.name
    clone_url, created_repo = _ensure_github_repo(
        token=config.github_token,
        owner=owner,
        repo=repo,
        private=config.private,
    )
    configured_remote = _configure_remote(workspace, config.remote, clone_url)
    pushed, push_skipped_reason = _ensure_published_head(
        workspace=workspace,
        remote=config.remote,
        branch=config.branch,
        bot_name=bot_name,
        token=config.github_token,
    )
    return WorkspaceGitBootstrapResult(
        owner=owner,
        repo=repo,
        clone_url=clone_url,
        created_repo=created_repo,
        configured_remote=configured_remote,
        pushed=pushed,
        push_skipped_reason=push_skipped_reason,
    )


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nanobot",
    }


def _github_login(token: str) -> str:
    response = httpx.get("https://api.github.com/user", headers=_github_headers(token), timeout=20.0)
    response.raise_for_status()
    login = (response.json() or {}).get("login", "").strip()
    if not login:
        raise RuntimeError("GitHub token is valid but no user login was returned")
    return login


def _ensure_github_repo(*, token: str, owner: str, repo: str, private: bool) -> tuple[str, bool]:
    payload = {"name": repo, "private": private}
    response = httpx.post(
        "https://api.github.com/user/repos",
        headers=_github_headers(token),
        json=payload,
        timeout=20.0,
    )
    if response.status_code == 201:
        data = response.json() or {}
        return str(data.get("clone_url") or f"https://github.com/{owner}/{repo}.git"), True
    if response.status_code not in {409, 422}:
        response.raise_for_status()

    repo_response = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_github_headers(token),
        timeout=20.0,
    )
    repo_response.raise_for_status()
    data = repo_response.json() or {}
    return str(data.get("clone_url") or f"https://github.com/{owner}/{repo}.git"), False


def _configure_remote(workspace: Path, remote: str, clone_url: str) -> bool:
    current = _git_capture(workspace, "remote", "get-url", remote, check=False)
    if current == clone_url:
        return False
    if current:
        _git(workspace, "remote", "set-url", remote, clone_url)
    else:
        _git(workspace, "remote", "add", remote, clone_url)
    return True


def _ensure_published_head(
    *,
    workspace: Path,
    remote: str,
    branch: str,
    bot_name: str,
    token: str,
) -> tuple[bool, str | None]:
    has_commits = _git_has_commits(workspace)
    dirty = _git_is_dirty(workspace)

    if not has_commits:
        if not dirty:
            return False, "workspace has no commits and no files to publish"
        _git(workspace, "checkout", "--orphan", branch)
        _git(workspace, "add", "-A")
        _commit(workspace, message="Initialize workspace", bot_name=bot_name)
        _push(workspace, remote=remote, branch=branch, token=token, set_upstream=True)
        return True, None

    current_branch = _git_capture(workspace, "branch", "--show-current", check=False) or branch
    if current_branch == "HEAD":
        current_branch = branch
    if dirty:
        return False, "workspace has uncommitted changes; remote configured but push skipped"

    _push(workspace, remote=remote, branch=current_branch, token=token, set_upstream=True)
    return True, None


def _commit(workspace: Path, *, message: str, bot_name: str) -> None:
    email_local = slugify_agent_name(bot_name) or "nanobot"
    _git(
        workspace,
        "-c",
        f"user.name={bot_name}",
        "-c",
        f"user.email={email_local}@users.noreply.github.com",
        "commit",
        "-m",
        message,
    )


def _push(workspace: Path, *, remote: str, branch: str, token: str, set_upstream: bool) -> None:
    basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    args = [
        "-c",
        f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}",
        "push",
    ]
    if set_upstream:
        args.append("-u")
    args.extend([remote, branch])
    _git(workspace, *args)


def _git_has_commits(workspace: Path) -> bool:
    return _git_capture(workspace, "rev-parse", "--verify", "HEAD", check=False) is not None


def _git_is_dirty(workspace: Path) -> bool:
    status = _git_capture(workspace, "status", "--porcelain", check=False)
    return bool(status)


def _git_capture(workspace: Path, *args: str, check: bool = True) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=check,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        if check:
            raise
        return None
    except FileNotFoundError as exc:
        raise RuntimeError("git is not installed") from exc
    if not check and completed.returncode != 0:
        return None
    return (completed.stdout or "").strip()


def _git(workspace: Path, *args: str) -> None:
    try:
        subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        logger.error("workspace git command failed: git {}", " ".join(args))
        raise RuntimeError(f"git {' '.join(args)} failed") from exc
