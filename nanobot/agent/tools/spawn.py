"""Spawn tool for creating background agents."""

from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import ObjectSchema, StringSchema, tool_parameters_schema


@tool_parameters(
    tool_parameters_schema(
        task=StringSchema("The task for the subagent to complete"),
        label=StringSchema("Optional short label for the task (for display)"),
        role=StringSchema("Optional workspace harness role name for this spawned agent"),
        model=StringSchema("Optional model override; defaults to the main runtime model"),
        provider=StringSchema("Optional provider override; defaults to provider auto-resolution"),
        api_key=StringSchema("Optional API key override for this spawned agent only"),
        api_base=StringSchema("Optional API base override for this spawned agent only"),
        extra_headers=ObjectSchema(
            "Optional provider header overrides for this spawned agent only",
            additional_properties=StringSchema("Header value"),
        ),
        required=["task"],
    )
)
class SpawnTool(Tool):
    """Tool to spawn a background agent for runtime-managed execution."""

    def __init__(self, manager: Any):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for background agent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a dedicated agent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The agent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )

    async def execute(
        self,
        task: str,
        label: str | None = None,
        role: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        extra_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a background agent to execute the given task."""
        return await self._manager.spawn(
            task=task,
            label=label,
            role=role,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
            model=model,
            provider=provider,
            api_key=api_key,
            api_base=api_base,
            extra_headers=extra_headers,
        )
