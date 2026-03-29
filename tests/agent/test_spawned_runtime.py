"""Tests for the runtime-owned spawned agent service."""

from __future__ import annotations

from unittest.mock import MagicMock

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
