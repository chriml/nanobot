"""Tests for the runtime-owned spawned agent service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from nanobot.config.schema import Config


def test_spawned_runtime_reuses_default_provider_without_overrides(tmp_path):
    from nanobot.agent.spawned import SpawnOverrides, SpawnedAgentRuntime
    from nanobot.bus.queue import MessageBus

    provider = MagicMock()
    provider.get_default_model.return_value = "anthropic/claude-sonnet-4-5"

    runtime = SpawnedAgentRuntime(
        provider=provider,
        workspace=tmp_path,
        bus=MessageBus(),
        config=Config(),
    )

    assert runtime._resolve_provider(SpawnOverrides()) is provider


def test_spawned_runtime_builds_override_provider_from_config(tmp_path, monkeypatch):
    from nanobot.agent.spawned import SpawnOverrides, SpawnedAgentRuntime
    from nanobot.bus.queue import MessageBus

    default_provider = MagicMock()
    default_provider.get_default_model.return_value = "anthropic/claude-sonnet-4-5"
    override_provider = MagicMock()

    config = Config.model_validate(
        {
            "agents": {"defaults": {"model": "anthropic/claude-sonnet-4-5"}},
            "providers": {
                "anthropic": {"apiKey": "anthropic-key"},
                "openai": {"apiKey": "openai-key"},
            },
        }
    )

    captured: dict[str, object] = {}

    def fake_make_provider(runtime_config, model=None):
        captured["config"] = runtime_config
        captured["model"] = model
        return override_provider

    monkeypatch.setattr("nanobot.providers.factory.make_provider", fake_make_provider)

    runtime = SpawnedAgentRuntime(
        provider=default_provider,
        workspace=tmp_path,
        bus=MessageBus(),
        config=config,
    )

    provider = runtime._resolve_provider(
        SpawnOverrides(
            model="openai/gpt-4.1-mini",
            provider="openai",
            api_key="override-key",
            api_base="https://example.com/v1",
            extra_headers={"X-Test": "1"},
        )
    )

    assert provider is override_provider
    assert captured["model"] == "openai/gpt-4.1-mini"
    runtime_config = captured["config"]
    assert runtime_config.agents.defaults.model == "openai/gpt-4.1-mini"
    assert runtime_config.agents.defaults.provider == "openai"
    assert runtime_config.providers.openai.api_key == "override-key"
    assert runtime_config.providers.openai.api_base == "https://example.com/v1"
    assert runtime_config.providers.openai.extra_headers == {"X-Test": "1"}


@pytest.mark.asyncio
async def test_spawned_runtime_archives_completed_agent_records(tmp_path, monkeypatch):
    from nanobot.agent.spawned import SpawnedAgentRuntime
    from nanobot.bus.queue import MessageBus
    from nanobot.providers.base import LLMResponse

    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))

    runtime = SpawnedAgentRuntime(provider=provider, workspace=tmp_path, bus=MessageBus())
    runtime._announce_result = AsyncMock()

    message = await runtime.spawn(
        task="analyze market",
        label="market scan",
        origin_channel="test",
        origin_chat_id="c1",
        session_key="test:c1",
        role="researcher",
    )

    agent_id = message.split("(id: ", 1)[1].split(")", 1)[0]
    await runtime._running_tasks[agent_id]

    archived = runtime.list_archived("test:c1")
    assert len(archived) == 1
    assert archived[0]["agent_id"] == agent_id
    assert archived[0]["label"] == "market scan"
    assert archived[0]["status"] == "completed"
    assert archived[0]["role"] == "researcher"
    assert archived[0]["result_preview"] == "done"
    assert runtime.list_active("test:c1") == []

    archive_lines = (tmp_path / "agents" / "archive.jsonl").read_text(encoding="utf-8").strip().splitlines()
    persisted = json.loads(archive_lines[-1])
    assert persisted["agent_id"] == agent_id
    assert persisted["status"] == "completed"
