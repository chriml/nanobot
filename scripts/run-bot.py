#!/usr/bin/env python3
"""Run a nanobot command against a named instance."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from nanobot.instances import build_instance_command, resolve_instance_paths

def parse_args() -> tuple[argparse.Namespace, list[str]]:
    """Parse CLI arguments and return the remaining nanobot command."""
    parser = argparse.ArgumentParser(
        description=(
            "Run nanobot against a named instance without retyping config/workspace flags."
        ),
    )
    parser.add_argument("name", help="Display name or slug for the bot instance.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        help="Override the instance root directory. Defaults to ~/.nanobot/instances.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )
    args, command = parser.parse_known_args()
    return args, command


def main() -> int:
    """Entrypoint."""
    args, command = parse_args()
    command = command or ["agent"]
    if command and command[0] == "--":
        command = command[1:]

    instance = resolve_instance_paths(args.name, base_dir=args.base_dir)
    resolved = build_instance_command(
        instance,
        python_executable=sys.executable,
        command=command,
    )

    print(f"Instance:  {instance.name} ({instance.slug})")
    print(f"Config:    {instance.config_path}")
    print(f"Workspace: {instance.workspace_path}")
    print(f"Command:   {' '.join(resolved)}")

    if args.dry_run:
        return 0

    return subprocess.run(resolved, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
