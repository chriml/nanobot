"""Workspace-local harness loading for runtime-native agent behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class HarnessDefinition:
    """Minimal structured harness definition loaded from the workspace."""

    version: int = 1
    global_instructions: str = ""
    stages: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)


def _strip_quotes(value: str) -> str:
    """Remove matching single or double quotes around a scalar value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_scalar(value: str) -> str | int:
    """Parse a simple scalar from the minimal YAML subset used by harness files."""
    cleaned = _strip_quotes(value.strip())
    if cleaned.isdigit():
        return int(cleaned)
    return cleaned


def _parse_minimal_yaml(text: str) -> dict[str, object]:
    """Parse a tiny YAML subset sufficient for the workspace harness definition."""
    result: dict[str, object] = {}
    lines = text.splitlines()
    idx = 0

    while idx < len(lines):
        raw = lines[idx]
        if not raw.strip() or raw.lstrip().startswith("#"):
            idx += 1
            continue
        if raw.startswith(" ") or raw.startswith("\t"):
            idx += 1
            continue

        key, sep, remainder = raw.partition(":")
        if not sep:
            idx += 1
            continue

        key = key.strip()
        remainder = remainder.strip()

        if remainder == "|":
            block: list[str] = []
            idx += 1
            while idx < len(lines):
                child = lines[idx]
                if not child.strip():
                    block.append("")
                    idx += 1
                    continue
                indent = len(child) - len(child.lstrip(" "))
                if indent < 2:
                    break
                block.append(child[2:] if child.startswith("  ") else child.lstrip())
                idx += 1
            result[key] = "\n".join(block).strip()
            continue

        if remainder:
            result[key] = _parse_scalar(remainder)
            idx += 1
            continue

        idx += 1
        values: list[str | int] = []
        mapping: dict[str, str | int] = {}
        is_list = False

        while idx < len(lines):
            child = lines[idx]
            if not child.strip() or child.lstrip().startswith("#"):
                idx += 1
                continue

            indent = len(child) - len(child.lstrip(" "))
            if indent < 2:
                break

            stripped = child[2:] if child.startswith("  ") else child.lstrip()
            if stripped.startswith("- "):
                is_list = True
                values.append(_parse_scalar(stripped[2:].strip()))
                idx += 1
                continue

            child_key, child_sep, child_remainder = stripped.partition(":")
            if not child_sep:
                idx += 1
                continue

            child_key = child_key.strip()
            child_remainder = child_remainder.strip()
            if child_remainder == "|":
                block: list[str] = []
                idx += 1
                while idx < len(lines):
                    block_line = lines[idx]
                    if not block_line.strip():
                        block.append("")
                        idx += 1
                        continue
                    block_indent = len(block_line) - len(block_line.lstrip(" "))
                    if block_indent < 4:
                        break
                    block.append(block_line[4:] if block_line.startswith("    ") else block_line.lstrip())
                    idx += 1
                mapping[child_key] = "\n".join(block).strip()
                continue

            mapping[child_key] = _parse_scalar(child_remainder)
            idx += 1

        result[key] = values if is_list else mapping

    return result


class WorkspaceHarness:
    """Read runtime harness instructions, stages, and roles from a workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.root = workspace / "harness"

    @property
    def definition_path(self) -> Path:
        return self.root / "definition.yaml"

    def exists(self) -> bool:
        """Return whether any harness files exist in the workspace."""
        return self.definition_path.exists() or self.root.exists()

    def load_definition(self) -> HarnessDefinition:
        """Load the structured harness definition from the workspace."""
        if not self.definition_path.exists():
            return HarnessDefinition()

        try:
            raw = _parse_minimal_yaml(self.definition_path.read_text(encoding="utf-8"))
        except OSError:
            return HarnessDefinition()

        stages = raw.get("stages")
        artifacts = raw.get("artifacts")
        return HarnessDefinition(
            version=int(raw.get("version", 1) or 1),
            global_instructions=str(raw.get("global_instructions", "") or ""),
            stages=[str(item) for item in stages] if isinstance(stages, list) else [],
            artifacts={str(k): str(v) for k, v in artifacts.items()} if isinstance(artifacts, dict) else {},
        )

    def _read_markdown(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def get_stage_prompt(self, stage: str) -> str:
        """Return the prompt for a named stage from the workspace harness."""
        return self._read_markdown(self.root / "stages" / f"{stage}.md")

    def get_role_prompt(self, role: str) -> str:
        """Return the prompt for a named spawned-agent role."""
        return self._read_markdown(self.root / "roles" / f"{role}.md")

    def list_roles(self) -> list[str]:
        """Return available role prompt names from the harness directory."""
        roles_dir = self.root / "roles"
        if not roles_dir.is_dir():
            return []
        return sorted(
            path.stem
            for path in roles_dir.iterdir()
            if path.is_file() and path.suffix == ".md"
        )

    def build_system_prompt(self) -> str:
        """Build the harness section injected into the main agent system prompt."""
        definition = self.load_definition()
        parts: list[str] = []

        if definition.global_instructions:
            parts.append(f"## Global Instructions\n\n{definition.global_instructions}")

        for stage in definition.stages:
            stage_prompt = self.get_stage_prompt(stage)
            if stage_prompt:
                parts.append(f"## Stage: {stage}\n\n{stage_prompt}")

        if definition.artifacts:
            artifact_lines = "\n".join(
                f"- {name}: {path}"
                for name, path in definition.artifacts.items()
            )
            parts.append(f"## Artifacts\n\n{artifact_lines}")

        roles = self.list_roles()
        if roles:
            role_lines = "\n".join(f"- {role}" for role in roles)
            parts.append(
                "## Spawned Roles\n\n"
                "Spawned agents can be bound to an explicit workspace role. "
                "Use the `spawn` tool `role` parameter when a role-specific prompt is needed.\n\n"
                f"{role_lines}"
            )

        if not parts:
            return ""

        return "# Harness\n\n" + "\n\n".join(parts)
