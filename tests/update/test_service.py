import subprocess
from pathlib import Path

from nanobot.config.schema import UpdatesConfig
from nanobot.update.service import AutoUpdateService


def _cp(args: list[str], stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_sync_ff_only_updates_when_remote_head_advances(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []
    responses = iter([
        _cp(["git", "status", "--porcelain"], "\n"),
        _cp(["git", "rev-parse", "--abbrev-ref", "HEAD"], "main\n"),
        _cp(["git", "rev-parse", "HEAD"], "old\n"),
        _cp(["git", "fetch", "upstream", "--prune"]),
        _cp(["git", "rev-parse", "upstream/main"], "new\n"),
        _cp(["git", "merge-base", "--is-ancestor", "old", "new"]),
        _cp(["git", "merge", "--ff-only", "upstream/main"]),
        _cp(["git", "rev-parse", "HEAD"], "new\n"),
    ])

    def runner(args, **kwargs):
        calls.append(args)
        return next(responses)

    service = AutoUpdateService(
        UpdatesConfig(enabled=True, remote="upstream", branch="main"),
        repo_root=tmp_path,
        runner=runner,
    )

    assert service._sync_once() is True
    assert ["git", "merge", "--ff-only", "upstream/main"] in calls


def test_sync_once_skips_dirty_worktree(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    def runner(args, **kwargs):
        return _cp(args, " M README.md\n")

    service = AutoUpdateService(UpdatesConfig(enabled=True), repo_root=tmp_path, runner=runner)

    assert service._sync_once() is False


def test_sync_local_branch_uses_helper_script(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "sync-local-branch.sh"
    script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    calls: list[list[str]] = []
    responses = iter([
        _cp(["git", "status", "--porcelain"], "\n"),
        _cp(["git", "rev-parse", "--abbrev-ref", "HEAD"], "nanobot-local\n"),
        _cp(["git", "rev-parse", "HEAD"], "old\n"),
        _cp([str(script)]),
        _cp(["git", "rev-parse", "HEAD"], "new\n"),
    ])

    def runner(args, **kwargs):
        calls.append(args)
        return next(responses)

    service = AutoUpdateService(
        UpdatesConfig(enabled=True, mode="local_branch", local_branch="nanobot-local"),
        repo_root=tmp_path,
        runner=runner,
    )

    assert service._sync_once() is True
    assert [str(script)] in calls
