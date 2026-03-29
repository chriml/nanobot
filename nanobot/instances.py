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


def get_instance_container_name(instance: InstancePaths) -> str:
    """Return the default Docker container name for an instance."""
    return f"nanochris-{instance.slug}"


def get_instance_image(image: str | None = None) -> str:
    """Return the Docker image used for per-instance containers."""
    return image or os.environ.get("NANOCHRIS_DOCKER_IMAGE") or "nanochris:local"


def get_container_config_path() -> str:
    """Return the config path used inside a per-instance container."""
    return "/root/.nanobot/config.json"


def get_container_workspace_path() -> str:
    """Return the workspace path used inside a per-instance container."""
    return "/root/.nanobot/workspace"


def build_docker_instance_command(
    instance: InstancePaths,
    *,
    image: str | None,
    nanobot_args: list[str],
    interactive: bool = False,
    remove: bool = True,
    detached: bool = False,
    host_port: int | None = None,
    container_name: str | None = None,
) -> list[str]:
    """Build a Docker command for an isolated instance container."""
    command = ["docker", "run"]
    if interactive:
        command.append("-it")
    if remove:
        command.append("--rm")
    if detached:
        command.append("-d")

    resolved_name = container_name or get_instance_container_name(instance)
    if resolved_name and not remove:
        command.extend(["--name", resolved_name])

    command.extend(
        [
            "-v",
            f"{instance.root.expanduser().resolve(strict=False)}:/root/.nanobot",
        ]
    )
    if host_port is not None:
        command.extend(["-p", f"{host_port}:18790"])

    command.append(get_instance_image(image))
    command.extend(nanobot_args)
    return command


def build_docker_remove_command(instance: InstancePaths) -> list[str]:
    """Build a command that stops and removes an instance container."""
    return ["docker", "rm", "-f", get_instance_container_name(instance)]


def build_docker_logs_command(instance: InstancePaths, *, follow: bool = True) -> list[str]:
    """Build a command that shows logs for an instance container."""
    command = ["docker", "logs"]
    if follow:
        command.append("-f")
    command.append(get_instance_container_name(instance))
    return command


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
