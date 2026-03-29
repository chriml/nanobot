"""Configuration module for nanobot."""

from nanobot.config.loader import get_config_path, load_config
from nanobot.config.paths import (
    get_agent_workspace_path,
    get_bridge_install_dir,
    get_cli_history_path,
    get_cron_dir,
    get_data_dir,
    get_legacy_sessions_dir,
    is_default_workspace,
    get_logs_dir,
    get_media_dir,
    get_runtime_subdir,
    get_workspace_path,
    slugify_agent_name,
)
from nanobot.config.schema import Config

__all__ = [
    "Config",
    "load_config",
    "get_config_path",
    "get_data_dir",
    "get_runtime_subdir",
    "get_media_dir",
    "get_cron_dir",
    "get_logs_dir",
    "get_agent_workspace_path",
    "get_workspace_path",
    "is_default_workspace",
    "slugify_agent_name",
    "get_cli_history_path",
    "get_bridge_install_dir",
    "get_legacy_sessions_dir",
]
