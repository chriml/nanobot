from pathlib import Path

from nanobot.agent.loop import AgentLoop
from nanobot.cli.git_hooked import install_workspace_git_hook
from nanobot.workspace_git import WorkspaceGitSyncHook


def test_install_workspace_git_hook_injects_hook(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_init(self, *args, **kwargs) -> None:
        seen["hooks"] = kwargs.get("hooks")
        seen["workspace"] = kwargs.get("workspace")

    monkeypatch.setattr(AgentLoop, "__init__", fake_init)
    monkeypatch.setattr(AgentLoop, "_workspace_git_hook_installed", False, raising=False)

    install_workspace_git_hook()

    loop = object.__new__(AgentLoop)
    AgentLoop.__init__(loop, workspace=tmp_path)

    hooks = seen["hooks"]
    assert seen["workspace"] == tmp_path
    assert isinstance(hooks, list)
    assert len(hooks) == 1
    assert isinstance(hooks[0], WorkspaceGitSyncHook)
    assert hooks[0].workspace == tmp_path


def test_install_workspace_git_hook_supports_positional_workspace(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_init(self, *args, **kwargs) -> None:
        seen["args"] = args
        seen["hooks"] = kwargs.get("hooks")

    monkeypatch.setattr(AgentLoop, "__init__", fake_init)
    monkeypatch.setattr(AgentLoop, "_workspace_git_hook_installed", False, raising=False)

    install_workspace_git_hook()

    loop = object.__new__(AgentLoop)
    AgentLoop.__init__(loop, object(), object(), tmp_path)

    hooks = seen["hooks"]
    assert seen["args"][2] == tmp_path
    assert isinstance(hooks, list)
    assert len(hooks) == 1
    assert isinstance(hooks[0], WorkspaceGitSyncHook)
    assert hooks[0].workspace == tmp_path
