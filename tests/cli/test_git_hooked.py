import asyncio
from pathlib import Path
from types import SimpleNamespace

from nanobot.agent.loop import AgentLoop
from nanobot.agent.runner import AgentRunResult, AgentRunSpec
from nanobot.cli.git_hooked import install_workspace_git_hook
from nanobot.workspace_git import WorkspaceGitSyncHook


def test_install_workspace_git_hook_wraps_runner_for_keyword_workspace(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    async def fake_run(spec: AgentRunSpec) -> AgentRunResult:
        seen["hook"] = spec.hook
        return AgentRunResult(final_content="ok", messages=[])

    def fake_init(self, *args, **kwargs) -> None:
        seen["workspace"] = kwargs.get("workspace")
        self.runner = SimpleNamespace(run=fake_run)

    monkeypatch.setattr(AgentLoop, "__init__", fake_init)
    monkeypatch.setattr(AgentLoop, "_workspace_git_hook_installed", False, raising=False)

    install_workspace_git_hook()

    loop = object.__new__(AgentLoop)
    AgentLoop.__init__(loop, workspace=tmp_path)
    spec = AgentRunSpec(initial_messages=[], tools=SimpleNamespace(), model="m", max_iterations=1)
    asyncio.run(loop.runner.run(spec))

    assert seen["workspace"] == tmp_path
    assert getattr(loop, "_workspace_git_sync_hook").workspace == tmp_path
    assert seen["hook"] is not None


def test_install_workspace_git_hook_refreshes_workspace_before_run(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    async def fake_run(spec: AgentRunSpec) -> AgentRunResult:
        seen["hook"] = spec.hook
        return AgentRunResult(final_content="ok", messages=[])

    def fake_init(self, *args, **kwargs) -> None:
        self.runner = SimpleNamespace(run=fake_run)

    monkeypatch.setattr(AgentLoop, "__init__", fake_init)
    monkeypatch.setattr(AgentLoop, "_workspace_git_hook_installed", False, raising=False)
    monkeypatch.setattr(
        "nanobot.cli.git_hooked.prepare_workspace_git_access",
        lambda workspace: seen.__setitem__("prepared", workspace),
    )
    monkeypatch.setattr(
        "nanobot.cli.git_hooked.refresh_workspace_repo",
        lambda workspace, *, remote, branch: seen.__setitem__(
            "refreshed",
            (workspace, remote, branch),
        ) or "updated",
    )

    install_workspace_git_hook()

    loop = object.__new__(AgentLoop)
    AgentLoop.__init__(loop, workspace=tmp_path)
    spec = AgentRunSpec(initial_messages=[], tools=SimpleNamespace(), model="m", max_iterations=1)
    asyncio.run(loop.runner.run(spec))

    assert seen["prepared"] == tmp_path
    assert seen["refreshed"] == (tmp_path, "origin", "main")
    assert seen["hook"] is not None


def test_install_workspace_git_hook_supports_positional_workspace(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    async def fake_run(spec: AgentRunSpec) -> AgentRunResult:
        seen["hook"] = spec.hook
        return AgentRunResult(final_content="ok", messages=[])

    def fake_init(self, *args, **kwargs) -> None:
        seen["args"] = args
        self.runner = SimpleNamespace(run=fake_run)

    monkeypatch.setattr(AgentLoop, "__init__", fake_init)
    monkeypatch.setattr(AgentLoop, "_workspace_git_hook_installed", False, raising=False)

    install_workspace_git_hook()

    loop = object.__new__(AgentLoop)
    AgentLoop.__init__(loop, object(), object(), tmp_path)
    spec = AgentRunSpec(initial_messages=[], tools=SimpleNamespace(), model="m", max_iterations=1)
    asyncio.run(loop.runner.run(spec))

    assert seen["args"][2] == tmp_path
    assert isinstance(getattr(loop, "_workspace_git_sync_hook"), WorkspaceGitSyncHook)
    assert getattr(loop, "_workspace_git_sync_hook").workspace == tmp_path
    assert seen["hook"] is not None
