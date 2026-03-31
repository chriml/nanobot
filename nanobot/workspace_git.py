"""Helpers for publishing and syncing a workspace git repository."""

from __future__ import annotations

import asyncio
import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from nanobot.agent.hook import AgentHook, AgentHookContext
from nanobot.config.paths import slugify_agent_name
from nanobot.config.schema import WorkspaceGitConfig

DEFAULT_COMMIT_MESSAGE = "chore(workspace): sync automated changes"


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

    _ensure_safe_directory(workspace)
    owner = _github_login(config.github_token)
    repo = config.repo.strip() or slugify_agent_name(bot_name) or workspace.name
    clone_url, created_repo = _ensure_github_repo(
        token=config.github_token,
        owner=owner,
        repo=repo,
        private=config.private,
    )
    _prepare_initial_workspace_commit(
        workspace,
        branch=config.branch,
        bot_name=bot_name,
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


def sync_workspace_repo(
    workspace: Path,
    *,
    remote: str = "origin",
    branch: str = "main",
    commit_message: str = DEFAULT_COMMIT_MESSAGE,
) -> str:
    """Commit and push workspace changes on a fixed branch."""
    _ensure_safe_directory(workspace)
    top_level = _git_capture(workspace, "rev-parse", "--show-toplevel", check=False)
    if top_level is None:
        logger.debug("Workspace git sync skipped: workspace is not a git repo")
        return "not_a_repo"

    if Path(top_level).resolve() != workspace.resolve():
        logger.warning(
            "Workspace git sync skipped: workspace {} is inside repo {}",
            workspace,
            top_level,
        )
        return "workspace_not_repo_root"

    current_branch = _git_capture(workspace, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if current_branch is None:
        logger.warning("Workspace git sync skipped: detached HEAD")
        return "detached_head"
    if current_branch != branch:
        logger.warning(
            "Workspace git sync skipped: current branch is {}, expected {}",
            current_branch,
            branch,
        )
        return "wrong_branch"

    if _has_in_progress_git_state(workspace):
        logger.warning("Workspace git sync skipped: git operation already in progress")
        return "git_busy"

    if _has_conflicts(workspace):
        logger.warning("Workspace git sync skipped: unresolved merge conflicts")
        return "conflicts"

    if _git_capture(workspace, "remote", "get-url", remote, check=False) is None:
        logger.warning("Workspace git sync skipped: remote {} is not configured", remote)
        return "missing_remote"

    _git(workspace, "fetch", remote)

    has_changes = _git_is_dirty(workspace)
    remote_ref = f"{remote}/{branch}"
    remote_exists = _git_capture(workspace, "rev-parse", "--verify", remote_ref, check=False) is not None

    if not has_changes and remote_exists and _is_up_to_date(workspace, remote_ref):
        return "up_to_date"

    if has_changes:
        _git(workspace, "add", "-A")
        _commit_workspace_sync(workspace, commit_message)

    if remote_exists:
        _git(workspace, "rebase", remote_ref)

    _git(workspace, "push", remote, f"HEAD:{branch}")
    return "synced"


class WorkspaceGitSyncHook(AgentHook):
    """Sync the workspace repo after completed agent turns."""

    def __init__(
        self,
        workspace: Path,
        *,
        remote: str = "origin",
        branch: str = "main",
        commit_message: str = DEFAULT_COMMIT_MESSAGE,
        sync_on_errors: bool = True,
    ) -> None:
        self.workspace = workspace
        self.remote = remote
        self.branch = branch
        self.commit_message = commit_message
        self.sync_on_errors = sync_on_errors

    async def after_iteration(self, context: AgentHookContext) -> None:
        if not self._should_sync(context):
            return

        result = await asyncio.to_thread(
            sync_workspace_repo,
            self.workspace,
            remote=self.remote,
            branch=self.branch,
            commit_message=self.commit_message,
        )
        if result not in {"up_to_date", "synced"}:
            logger.info("Workspace git sync hook result: {}", result)

    def _should_sync(self, context: AgentHookContext) -> bool:
        if context.final_content is not None:
            return True
        return self.sync_on_errors and context.stop_reason in {"error", "tool_error"}


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
        try:
            _git(workspace, "remote", "add", remote, clone_url)
        except RuntimeError:
            retry_current = _git_capture(workspace, "remote", "get-url", remote, check=False)
            if not retry_current:
                raise
            if retry_current != clone_url:
                _git(workspace, "remote", "set-url", remote, clone_url)
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
        _prepare_initial_workspace_commit(workspace, branch=branch, bot_name=bot_name)
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


def _ensure_safe_directory(workspace: Path) -> None:
    resolved = str(workspace.expanduser().resolve(strict=False))
    existing = _git_global_capture("config", "--global", "--get-all", "safe.directory")
    entries = {line.strip() for line in (existing or "").splitlines() if line.strip()}
    if resolved in entries or "*" in entries:
        return
    _git_global("config", "--global", "--add", "safe.directory", resolved)


def _prepare_initial_workspace_commit(workspace: Path, *, branch: str, bot_name: str) -> bool:
    """Create the initial branch commit for a fresh dirty repo."""
    if _git_has_commits(workspace) or not _git_is_dirty(workspace):
        return False

    current_branch = _git_capture(workspace, "branch", "--show-current", check=False)
    if current_branch != branch:
        _git(workspace, "checkout", "--orphan", branch)
    _git(workspace, "add", "-A")
    _commit(workspace, message="Initialize workspace", bot_name=bot_name)
    return True


def _commit_workspace_sync(workspace: Path, message: str) -> None:
    _git(workspace, "commit", "-m", message)


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


def _is_up_to_date(workspace: Path, remote_ref: str) -> bool:
    counts = _git_capture(workspace, "rev-list", "--left-right", "--count", f"HEAD...{remote_ref}")
    if not counts:
        return False
    ahead_str, behind_str = counts.split()
    return ahead_str == "0" and behind_str == "0"


def _has_conflicts(workspace: Path) -> bool:
    conflicts = _git_capture(workspace, "diff", "--name-only", "--diff-filter=U")
    return bool(conflicts and conflicts.strip())


def _has_in_progress_git_state(workspace: Path) -> bool:
    for git_path in [
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-merge",
        "rebase-apply",
    ]:
        resolved = _git_capture(workspace, "rev-parse", "--git-path", git_path)
        if not resolved:
            continue
        resolved_path = Path(resolved)
        if not resolved_path.is_absolute():
            resolved_path = workspace / resolved_path
        if resolved_path.exists():
            return True
    return False


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
        completed = subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        logger.error("workspace git command failed: git {}: {}", " ".join(args), stderr or exc.returncode)
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr or exc.returncode}") from exc


def _git_global_capture(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError as exc:
        raise RuntimeError("git is not installed") from exc
    return (completed.stdout or "").strip()


def _git_global(*args: str) -> None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        logger.error("git {} failed: {}", " ".join(args), stderr or exc.returncode)
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr or exc.returncode}") from exc


__all__ = [
    "DEFAULT_COMMIT_MESSAGE",
    "WorkspaceGitBootstrapResult",
    "WorkspaceGitSyncHook",
    "bootstrap_workspace_git",
    "sync_workspace_repo",
]
