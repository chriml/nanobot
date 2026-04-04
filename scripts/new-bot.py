#!/usr/bin/env python3
"""Create a named nanobot instance and launch onboarding."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from nanobot.instances import build_onboard_command, resolve_instance_paths

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create a named nanobot instance and run onboarding for it.",
    )
    parser.add_argument("name", help="Display name for the bot instance.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        help="Override the instance root directory. Defaults to ~/.nanobot/instances.",
    )
    parser.add_argument(
        "--no-wizard",
        action="store_true",
        help="Skip the interactive onboarding wizard.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without running it.",
    )
    return parser.parse_args()


def main() -> int:
    """Entrypoint."""
    args = parse_args()
    instance = resolve_instance_paths(args.name, base_dir=args.base_dir)
    command = build_onboard_command(
        instance,
        python_executable=sys.executable,
        wizard=not args.no_wizard,
    )

    print(f"Instance:  {instance.name} ({instance.slug})")
    print(f"Config:    {instance.config_path}")
    print(f"Workspace: {instance.workspace_path}")
    print(f"Command:   {' '.join(command)}")

    if args.dry_run:
        return 0

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
