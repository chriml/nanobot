"""Dedicated CLI for managing named nanochris instances."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from platformdirs import user_data_dir

from nanobot import __logo__, __version__
from nanobot.config.presets import apply_presets, merge_config_overlay
from nanobot.instances import (
    build_docker_instance_command,
    build_docker_logs_command,
    build_docker_remove_command,
    get_container_config_path,
    get_container_workspace_path,
    get_instance_container_name,
    get_instance_image,
    get_nanochris_network_name,
    get_searxng_container_name,
    get_searxng_image,
    resolve_instance_paths,
)

app = typer.Typer(
    name="nanochris",
    context_settings={"help_option_names": ["-h", "--help"]},
    help=f"{__logo__} nanochris - Manage named bot instances",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanochris v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanochris - Manage named bot instances."""
    pass


def _print_instance_summary(instance) -> None:
    console.print(f"[dim]Instance:[/dim] {instance.name} ({instance.slug})")
    console.print(f"[dim]Root:[/dim] {instance.root}")
    console.print(f"[dim]Config:[/dim] {instance.config_path}")
    console.print(f"[dim]Workspace:[/dim] {instance.workspace_path}")


def _run_command(command: list[str], *, dry_run: bool) -> int:
    console.print(f"[dim]Command:[/dim] {' '.join(command)}")
    if dry_run:
        return 0
    return subprocess.run(command, check=False).returncode


def _show_config(instance) -> int:
    _print_instance_summary(instance)
    if not instance.config_path.exists():
        console.print("[yellow]Config does not exist yet. Run onboarding first.[/yellow]")
        return 1
    console.print()
    console.print(Text(instance.config_path.read_text(encoding="utf-8")))
    return 0


def _save_config_overlay(config_path: Path, overlay: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    merged = merge_config_overlay(data, overlay)
    config_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _oauth_host_dir() -> Path:
    return Path(user_data_dir("oauth-cli-kit", appauthor=False))


def _oauth_volume_mount() -> str:
    oauth_dir = _oauth_host_dir()
    oauth_dir.mkdir(parents=True, exist_ok=True)
    return f"{oauth_dir.expanduser().resolve(strict=False)}:/root/.local/share/oauth-cli-kit"


def _whisper_cache_host_dir() -> Path:
    return Path.home() / ".cache" / "whisper"


def _whisper_cache_volume_mount() -> str:
    cache_dir = _whisper_cache_host_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return f"{cache_dir.expanduser().resolve(strict=False)}:/root/.cache/whisper"


def _shared_service_dir() -> Path:
    path = Path.home() / ".nanobot" / "services"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _searxng_settings_path() -> Path:
    settings_dir = _shared_service_dir() / "searxng"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.yml"
    settings_path.write_text(
        """use_default_settings: true

general:
  instance_name: "nanochris searxng"

search:
  formats:
    - html
    - json

server:
  secret_key: "nanochris-searxng-change-me"
""",
        encoding="utf-8",
    )
    return settings_path


def _searxng_volume_mount() -> str:
    settings_path = _searxng_settings_path()
    return f"{settings_path.expanduser().resolve(strict=False)}:/etc/searxng/settings.yml:ro"


def _shared_search_base_url() -> str:
    return f"http://{get_searxng_container_name()}:8080"


def _shared_runtime_env() -> dict[str, str]:
    return {
        "NANOBOT_TOOLS__WEB__SEARCH__PROVIDER": "searxng",
        "NANOBOT_TOOLS__WEB__SEARCH__BASE_URL": _shared_search_base_url(),
    }


def _ensure_nanochris_network(*, dry_run: bool) -> int:
    network = get_nanochris_network_name()
    if dry_run:
        return _run_command(["docker", "network", "create", network], dry_run=True)
    inspect = subprocess.run(
        ["docker", "network", "inspect", network],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if inspect.returncode == 0:
        return 0
    return _run_command(["docker", "network", "create", network], dry_run=dry_run)


def _ensure_searxng_container(*, dry_run: bool) -> int:
    name = get_searxng_container_name()
    if dry_run:
        _run_command(["docker", "rm", "-f", name], dry_run=True)
        return _run_command(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                get_nanochris_network_name(),
                "-v",
                _searxng_volume_mount(),
                get_searxng_image(),
            ],
            dry_run=True,
        )
    running = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if running.returncode == 0 and running.stdout.strip() == "true":
        return 0

    remove = ["docker", "rm", "-f", name]
    if dry_run:
        console.print(f"[dim]Command:[/dim] {' '.join(remove)}")
    else:
        subprocess.run(remove, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--network",
        get_nanochris_network_name(),
        "-v",
        _searxng_volume_mount(),
        get_searxng_image(),
    ]
    return _run_command(command, dry_run=dry_run)


@app.command()
def newbot(
    name: str = typer.Argument(..., help="Display name for the bot instance"),
    base_dir: str | None = typer.Option(
        None,
        "--base-dir",
        help="Root directory for named instances (defaults to ~/.nanobot/instances)",
    ),
    image: str | None = typer.Option(
        None,
        "--image",
        envvar="NANOCHRIS_DOCKER_IMAGE",
        help="Docker image to run (defaults to $NANOCHRIS_DOCKER_IMAGE or nanochris:local)",
    ),
    preset: list[str] = typer.Option(
        None,
        "--preset",
        help="Preset name or JSON file path to merge into the instance config before onboarding. Repeatable.",
    ),
    wizard: bool = typer.Option(
        True,
        "--wizard/--no-wizard",
        help="Run the interactive onboarding wizard immediately",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the resolved Docker command without running it",
    ),
):
    """Create a named bot instance and run onboarding for it."""
    instance = resolve_instance_paths(name, base_dir=base_dir)
    if preset:
        apply_presets(instance.config_path, preset)
    if _ensure_nanochris_network(dry_run=dry_run) != 0:
        raise typer.Exit(1)
    if _ensure_searxng_container(dry_run=dry_run) != 0:
        raise typer.Exit(1)
    _print_instance_summary(instance)
    console.print(f"[dim]Container:[/dim] {get_instance_container_name(instance)}")
    console.print(f"[dim]Image:[/dim] {get_instance_image(image)}")
    command = build_docker_instance_command(
        instance,
        image=image,
        interactive=True,
        remove=True,
        volume_mounts=[_whisper_cache_volume_mount()],
        extra_hosts=["host.docker.internal:host-gateway"],
        environment=_shared_runtime_env(),
        network=get_nanochris_network_name(),
        nanobot_args=[
            "onboard",
            "--config",
            get_container_config_path(),
            "--workspace",
            get_container_workspace_path(),
            "--name",
            instance.name,
            *(["--wizard"] if wizard else []),
        ],
    )
    raise typer.Exit(_run_command(command, dry_run=dry_run))


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def manage(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Display name for the bot instance"),
    base_dir: str | None = typer.Option(
        None,
        "--base-dir",
        help="Root directory for named instances (defaults to ~/.nanobot/instances)",
    ),
    image: str | None = typer.Option(
        None,
        "--image",
        envvar="NANOCHRIS_DOCKER_IMAGE",
        help="Docker image to run (defaults to $NANOCHRIS_DOCKER_IMAGE or nanochris:local)",
    ),
    preset: list[str] = typer.Option(
        None,
        "--preset",
        help="Preset name or JSON file path to merge into the instance config before onboarding. Repeatable.",
    ),
    host_port: int = typer.Option(
        18790,
        "--host-port",
        help="Host port that maps to the gateway port inside the container",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the resolved command without running it",
    ),
):
    """Manage an instance with actions: onboard, config, start, stop, logs, login."""
    actions = list(ctx.args)
    if not actions:
        console.print(
            "[red]Missing action.[/red] Use one of: onboard, config, start, stop, logs, login."
        )
        raise typer.Exit(2)

    action = actions[0]
    extra = actions[1:]
    instance = resolve_instance_paths(name, base_dir=base_dir)

    if action == "config":
        raise typer.Exit(_show_config(instance))

    _print_instance_summary(instance)
    console.print(f"[dim]Container:[/dim] {get_instance_container_name(instance)}")
    console.print(f"[dim]Image:[/dim] {get_instance_image(image)}")

    if action == "onboard":
        if preset:
            apply_presets(instance.config_path, preset)
        wizard = "--no-wizard" not in extra
        if _ensure_nanochris_network(dry_run=dry_run) != 0:
            raise typer.Exit(1)
        if _ensure_searxng_container(dry_run=dry_run) != 0:
            raise typer.Exit(1)
        command = build_docker_instance_command(
            instance,
            image=image,
            interactive=True,
            remove=True,
            volume_mounts=[_whisper_cache_volume_mount()],
            extra_hosts=["host.docker.internal:host-gateway"],
            environment=_shared_runtime_env(),
            network=get_nanochris_network_name(),
            nanobot_args=[
                "onboard",
                "--config",
                get_container_config_path(),
                "--workspace",
                get_container_workspace_path(),
                "--name",
                instance.name,
                *(["--wizard"] if wizard else []),
            ],
        )
        raise typer.Exit(_run_command(command, dry_run=dry_run))

    if action == "start":
        if _ensure_nanochris_network(dry_run=dry_run) != 0:
            raise typer.Exit(1)
        if _ensure_searxng_container(dry_run=dry_run) != 0:
            raise typer.Exit(1)
        command = build_docker_instance_command(
            instance,
            image=image,
            interactive=False,
            remove=False,
            detached=True,
            host_port=host_port,
            volume_mounts=[_oauth_volume_mount(), _whisper_cache_volume_mount()],
            extra_hosts=["host.docker.internal:host-gateway"],
            environment=_shared_runtime_env(),
            network=get_nanochris_network_name(),
            nanobot_args=[
                "gateway",
                *extra,
                "--config",
                get_container_config_path(),
                "--workspace",
                get_container_workspace_path(),
            ],
        )
        raise typer.Exit(_run_command(command, dry_run=dry_run))

    if action == "stop":
        command = build_docker_remove_command(instance)
        raise typer.Exit(_run_command(command, dry_run=dry_run))

    if action == "logs":
        follow = "--no-follow" not in extra
        command = build_docker_logs_command(instance, follow=follow)
        raise typer.Exit(_run_command(command, dry_run=dry_run))

    if action == "login":
        if not extra:
            console.print("[red]Missing login target.[/red] Use one of: codex, claude.")
            raise typer.Exit(2)

        target = extra[0].lower()
        if target == "codex":
            if _ensure_nanochris_network(dry_run=dry_run) != 0:
                raise typer.Exit(1)
            command = [
                "docker",
                "run",
                "-it",
                "--rm",
                "-v",
                f"{instance.root.expanduser().resolve(strict=False)}:/root/.nanobot",
                "-v",
                _oauth_volume_mount(),
                "-v",
                _whisper_cache_volume_mount(),
                "--network",
                get_nanochris_network_name(),
                "--add-host",
                "host.docker.internal:host-gateway",
                "-e",
                f"NANOBOT_TOOLS__WEB__SEARCH__BASE_URL={_shared_search_base_url()}",
                get_instance_image(image),
                "provider",
                "login",
                "openai-codex",
            ]
            raise typer.Exit(_run_command(command, dry_run=dry_run))

        if target == "claude":
            api_key = typer.prompt("Anthropic API key", hide_input=True).strip()
            if not api_key:
                console.print("[red]API key cannot be empty.[/red]")
                raise typer.Exit(1)
            overlay = {
                "agents": {
                    "defaults": {
                        "provider": "anthropic",
                        "model": "anthropic/claude-opus-4-5",
                    }
                },
                "providers": {
                    "anthropic": {
                        "apiKey": api_key,
                    }
                },
            }
            _save_config_overlay(instance.config_path, overlay)
            console.print(f"[green]Saved Claude credentials for[/green] {instance.name}")
            raise typer.Exit(0)

        console.print(
            f"[red]Unknown login target:[/red] {target} "
            "[dim](expected one of: codex, claude)[/dim]"
        )
        raise typer.Exit(2)

    console.print(
        f"[red]Unknown action:[/red] {action} "
        "[dim](expected one of: onboard, config, start, stop, logs, login)[/dim]"
    )
    raise typer.Exit(2)
