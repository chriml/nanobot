#!/usr/bin/env python3
"""Merge one or more local presets into a nanobot config file."""

from __future__ import annotations

import argparse
from pathlib import Path

from nanobot.config.presets import apply_presets


DEFAULT_CONFIG = Path.home() / ".nanobot" / "config.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("presets", nargs="+", help="Preset names or JSON file paths")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Target config path (default: {DEFAULT_CONFIG})",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    apply_presets(config_path, args.presets)
    print(f"Applied preset(s) to {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
