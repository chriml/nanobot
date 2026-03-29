"""Tests for runtime-native workspace harness loading."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from nanobot.agent.context import ContextBuilder
from nanobot.agent.harness import WorkspaceHarness
from nanobot.bus.queue import MessageBus


def _make_harness_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "harness" / "stages").mkdir(parents=True)
    (workspace / "harness" / "roles").mkdir(parents=True)
    (workspace / "harness" / "definition.yaml").write_text(
        "\n".join([
            "version: 1",
            "global_instructions: |",
            "  Work incrementally and verify before claiming completion.",
            "stages:",
            "  - scope",
            "  - evaluate",
            "artifacts:",
            "  handoff: memory/HANDOFF.md",
        ]),
        encoding="utf-8",
    )
    (workspace / "harness" / "stages" / "scope.md").write_text(
        "Define the next bounded milestone before coding.",
        encoding="utf-8",
    )
    (workspace / "harness" / "stages" / "evaluate.md").write_text(
        "Run checks and compare against the stated success criteria.",
        encoding="utf-8",
    )
    (workspace / "harness" / "roles" / "evaluator.md").write_text(
        "You are the evaluator. Be strict and evidence-driven.",
        encoding="utf-8",
    )
    return workspace


def test_workspace_harness_loads_definition_and_roles(tmp_path: Path) -> None:
    workspace = _make_harness_workspace(tmp_path)

    harness = WorkspaceHarness(workspace)
    definition = harness.load_definition()

    assert definition.global_instructions == "Work incrementally and verify before claiming completion."
    assert definition.stages == ["scope", "evaluate"]
    assert definition.artifacts == {"handoff": "memory/HANDOFF.md"}
    assert harness.list_roles() == ["evaluator"]
    assert "strict and evidence-driven" in harness.get_role_prompt("evaluator")


def test_context_builder_includes_workspace_harness_in_system_prompt(tmp_path: Path) -> None:
    workspace = _make_harness_workspace(tmp_path)

    prompt = ContextBuilder(workspace).build_system_prompt()

    assert "# Harness" in prompt
    assert "Work incrementally and verify before claiming completion." in prompt
    assert "## Stage: scope" in prompt
    assert "## Stage: evaluate" in prompt
    assert "handoff: memory/HANDOFF.md" in prompt


def test_spawned_runtime_includes_role_prompt_when_present(tmp_path: Path) -> None:
    from nanobot.agent.spawned import SpawnedAgentRuntime

    workspace = _make_harness_workspace(tmp_path)
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"

    runtime = SpawnedAgentRuntime(provider=provider, workspace=workspace, bus=MessageBus())
    prompt = runtime._build_agent_prompt(role="evaluator")

    assert "## Assigned Role: evaluator" in prompt
    assert "strict and evidence-driven" in prompt
