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
    _print_instance_summary(instance)
    console.print(f"[dim]Container:[/dim] {get_instance_container_name(instance)}")
    console.print(f"[dim]Image:[/dim] {get_instance_image(image)}")
    command = build_docker_instance_command(
        instance,
        image=image,
        interactive=True,
        remove=True,
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
        command = build_docker_instance_command(
            instance,
            image=image,
            interactive=True,
            remove=True,
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
        command = build_docker_instance_command(
            instance,
            image=image,
            interactive=False,
            remove=False,
            detached=True,
            host_port=host_port,
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
            oauth_dir = _oauth_host_dir()
            oauth_dir.mkdir(parents=True, exist_ok=True)
            command = [
                "docker",
                "run",
                "-it",
                "--rm",
                "-v",
                f"{instance.root.expanduser().resolve(strict=False)}:/root/.nanobot",
                "-v",
                f"{oauth_dir.expanduser().resolve(strict=False)}:/root/.local/share/oauth-cli-kit",
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
