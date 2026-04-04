"""Helpers for applying local config presets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def merge_config_overlay(base: Any, overlay: Any) -> Any:
    """Deep-merge a config overlay into a base object."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    merged = dict(base)
    for key, value in overlay.items():
        merged[key] = merge_config_overlay(merged.get(key), value) if key in merged else value
    return merged


def get_presets_dir() -> Path:
    """Return the repository presets directory."""
    return Path(__file__).resolve().parents[2] / "presets"


def resolve_preset_path(name: str) -> Path:
    """Resolve a preset by name or explicit file path."""
    raw = Path(name).expanduser()
    if raw.exists():
        return raw.resolve()

    candidate = get_presets_dir() / f"{name}.json"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Preset not found: {name}")


def apply_presets(config_path: Path, presets: list[str]) -> Path:
    """Merge one or more presets into a config file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))

    for preset_name in presets:
        preset_path = resolve_preset_path(preset_name)
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        data = merge_config_overlay(data, preset)

    config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return config_path
