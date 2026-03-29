#!/usr/bin/env python3
"""Manage named nanobot instances from a repo checkout."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from nanobot.instances import (
    build_instance_command,
    build_onboard_command,
    list_instances,
    resolve_instance_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Manage named nanobot instances.",
        epilog=(
            "Examples:\n"
            "  ./scripts/manage-bot.py -h\n"
            "  ./scripts/manage-bot.py list\n"
            "  ./scripts/manage-bot.py show Chris\n"
            "  ./scripts/manage-bot.py onboard Chris\n"
            "  ./scripts/manage-bot.py gateway Chris\n"
            "  ./scripts/manage-bot.py agent Chris -m 'Hello'\n"
            "  ./scripts/manage-bot.py run Chris channels status"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        help="Override the instance root directory. Defaults to ~/.nanobot/instances.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List discovered instances.")

    show_parser = subparsers.add_parser("show", help="Show paths for an instance.")
    show_parser.add_argument("name", help="Display name or slug for the bot instance.")

    onboard_parser = subparsers.add_parser("onboard", help="Run onboarding for an instance.")
    onboard_parser.add_argument("name", help="Display name or slug for the bot instance.")
    onboard_parser.add_argument(
        "--no-wizard",
        action="store_true",
        help="Skip the interactive onboarding wizard.",
    )
    onboard_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )

    agent_parser = subparsers.add_parser("agent", help="Run `nanobot agent` for an instance.")
    agent_parser.add_argument("name", help="Display name or slug for the bot instance.")
    agent_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )

    gateway_parser = subparsers.add_parser(
        "gateway",
        help="Run `nanobot gateway` for an instance.",
    )
    gateway_parser.add_argument("name", help="Display name or slug for the bot instance.")
    gateway_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )

    run_parser = subparsers.add_parser("run", help="Run any nanobot command for an instance.")
    run_parser.add_argument("name", help="Display name or slug for the bot instance.")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )

    return parser


def print_instance(instance) -> None:
    """Print basic instance metadata."""
    print(f"Instance:  {instance.name} ({instance.slug})")
    print(f"Root:      {instance.root}")
    print(f"Config:    {instance.config_path}")
    print(f"Workspace: {instance.workspace_path}")


def run_command(command: list[str], *, dry_run: bool) -> int:
    """Execute or print a resolved subprocess command."""
    print(f"Command:   {' '.join(command)}")
    if dry_run:
        return 0
    return subprocess.run(command, check=False).returncode


def main() -> int:
    """Entrypoint."""
    parser = build_parser()
    args, extra_args = parser.parse_known_args()

    if args.command == "list":
        instances = list_instances(base_dir=args.base_dir)
        if not instances:
            print("No instances found.")
            return 0
        for instance in instances:
            print(f"{instance.slug}\t{instance.name}\t{instance.config_path}")
        return 0

    instance = resolve_instance_paths(args.name, base_dir=args.base_dir)
    print_instance(instance)

    if args.command == "show":
        return 0

    if args.command == "onboard":
        command = build_onboard_command(
            instance,
            python_executable=sys.executable,
            wizard=not args.no_wizard,
        )
        return run_command(command, dry_run=args.dry_run)

    command_args = list(extra_args)
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]

    if args.command == "agent":
        command = build_instance_command(
            instance,
            python_executable=sys.executable,
            command=["agent", *command_args],
        )
        return run_command(command, dry_run=args.dry_run)

    if args.command == "gateway":
        command = build_instance_command(
            instance,
            python_executable=sys.executable,
            command=["gateway", *command_args],
        )
        return run_command(command, dry_run=args.dry_run)

    if args.command == "run":
        command_args = command_args or ["agent"]
        command = build_instance_command(
            instance,
            python_executable=sys.executable,
            command=command_args,
        )
        return run_command(command, dry_run=args.dry_run)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
