"""Backward-compatible alias for the runtime-owned spawned agent service."""

from nanobot.agent.spawned import SpawnedAgentRuntime as SubagentManager

__all__ = ["SubagentManager"]
