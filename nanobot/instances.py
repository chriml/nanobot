"""Helpers for managing named nanobot instances."""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstancePaths:
    """Resolved paths for a named nanobot instance."""

    name: str
    slug: str
    root: Path
    config_path: Path
    workspace_path: Path


def slugify_instance_name(name: str | None) -> str:
    """Convert a user-facing instance name into a filesystem-safe slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return cleaned or "default"


def get_instances_dir(base_dir: str | Path | None = None) -> Path:
    """Return the root directory used for named instances."""
    override = base_dir or os.environ.get("NANOBOT_INSTANCES_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".nanobot" / "instances"


def resolve_instance_paths(name: str, base_dir: str | Path | None = None) -> InstancePaths:
    """Resolve the config/workspace layout for a named instance."""
    cleaned_name = (name or "").strip() or "default"
    slug = slugify_instance_name(cleaned_name)
    root = get_instances_dir(base_dir) / slug
    return InstancePaths(
        name=cleaned_name,
        slug=slug,
        root=root,
        config_path=root / "config.json",
        workspace_path=root / "workspace",
    )


def build_onboard_command(
    instance: InstancePaths,
    *,
    python_executable: str,
    wizard: bool = True,
) -> list[str]:
    """Build a command that onboards a named instance."""
    command = [
        python_executable,
        "-m",
        "nanobot",
        "onboard",
        "--config",
        str(instance.config_path),
        "--workspace",
        str(instance.workspace_path),
        "--name",
        instance.name,
    ]
    if wizard:
        command.append("--wizard")
    return command


def build_instance_command(
    instance: InstancePaths,
    *,
    python_executable: str,
    command: list[str] | None = None,
) -> list[str]:
    """Build a nanobot command targeted at a named instance."""
    resolved_command = list(command or ["agent"])
    if "--config" not in resolved_command and "-c" not in resolved_command:
        resolved_command.extend(["--config", str(instance.config_path)])
    if "--workspace" not in resolved_command and "-w" not in resolved_command:
        resolved_command.extend(["--workspace", str(instance.workspace_path)])
    return [python_executable, "-m", "nanobot", *resolved_command]


def list_instances(base_dir: str | Path | None = None) -> list[InstancePaths]:
    """Return discovered named instances from the instances directory."""
    instances_dir = get_instances_dir(base_dir)
    if not instances_dir.exists():
        return []

    instances: list[InstancePaths] = []
    for root in sorted(path for path in instances_dir.iterdir() if path.is_dir()):
        config_path = root / "config.json"
        workspace_path = root / "workspace"
        name = _load_instance_name(config_path) or root.name
        instances.append(
            InstancePaths(
                name=name,
                slug=root.name,
                root=root,
                config_path=config_path,
                workspace_path=workspace_path,
            )
        )
    return instances


def _load_instance_name(config_path: Path) -> str | None:
    """Best-effort read of the configured display name from an instance config."""
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data.get("agents", {}).get("defaults", {}).get("name")
