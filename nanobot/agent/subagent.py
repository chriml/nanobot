"""Backward-compatible wrapper around the runtime-owned spawned agent service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nanobot.agent.spawned import SpawnedAgentRuntime

if TYPE_CHECKING:
    from nanobot.bus.queue import MessageBus
    from nanobot.config.schema import ExecToolConfig, WebToolsConfig
    from nanobot.providers.base import LLMProvider


class SubagentManager(SpawnedAgentRuntime):
    """Compatibility shim for code paths that still import ``SubagentManager``."""

    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        bus: "MessageBus",
        max_tool_result_chars: int,
        model: str | None = None,
        web_config: "WebToolsConfig | None" = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ) -> None:
        super().__init__(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=model,
            web_search_config=web_config.search if web_config else None,
            web_proxy=web_config.proxy if web_config else None,
            exec_config=exec_config,
            restrict_to_workspace=restrict_to_workspace,
            max_tool_result_chars=max_tool_result_chars,
        )

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Preserve the legacy helper name used by older tests and callers."""
        await self._run_agent(task_id, task, label, origin)


__all__ = ["SubagentManager"]
