#!/usr/bin/env python3
"""Merge one or more local presets into a nanobot config file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PRESETS_DIR = REPO_ROOT / "presets"
DEFAULT_CONFIG = Path.home() / ".nanobot" / "config.json"


def _merge(base: Any, overlay: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    merged = dict(base)
    for key, value in overlay.items():
        merged[key] = _merge(merged.get(key), value) if key in merged else value
    return merged


def _resolve_preset(name: str) -> Path:
    raw = Path(name).expanduser()
    if raw.exists():
        return raw.resolve()

    candidate = PRESETS_DIR / f"{name}.json"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Preset not found: {name}")


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
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))

    for preset_name in args.presets:
        preset_path = _resolve_preset(preset_name)
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        data = _merge(data, preset)

    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Applied preset(s) to {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
