import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from nanobot.cli.commands import app
from nanobot.config.schema import Config
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.openai_codex_provider import _strip_model_prefix
from nanobot.providers.registry import find_by_model

runner = CliRunner()


class _StopGatewayError(RuntimeError):
    pass


@pytest.fixture
def mock_paths():
    """Mock config/workspace paths for test isolation."""
    with patch("nanobot.config.loader.get_config_path") as mock_cp, \
         patch("nanobot.config.loader.save_config") as mock_sc, \
         patch("nanobot.config.loader.load_config"), \
         patch("nanobot.cli.commands.get_workspace_path") as mock_ws:

        base_dir = Path("./test_onboard_data")
        if base_dir.exists():
            shutil.rmtree(base_dir)
        base_dir.mkdir()

        config_file = base_dir / "config.json"
        workspace_dir = base_dir / "workspace"

        mock_cp.return_value = config_file
        mock_ws.return_value = workspace_dir
        mock_sc.side_effect = lambda config: config_file.write_text("{}")

        yield config_file, workspace_dir

        if base_dir.exists():
            shutil.rmtree(base_dir)


def test_onboard_fresh_install(mock_paths):
    """No existing config — should create from scratch."""
    config_file, workspace_dir = mock_paths

    with patch("nanobot.cli.commands._get_openai_codex_account_id", return_value=None):
        result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 0
    assert "Created config" in result.stdout
    assert "Created workspace" in result.stdout
    assert "nanobot is ready" in result.stdout
    assert "OpenAI Codex login skipped because onboarding is running non-interactively" in result.stdout
    assert "nanobot provider login openai-codex" in result.stdout
    assert "openai-codex/gpt-5.4" in result.stdout
    assert config_file.exists()
    assert (workspace_dir / "AGENTS.md").exists()
    assert (workspace_dir / "memory" / "MEMORY.md").exists()


def test_onboard_existing_config_refresh(mock_paths):
    """Config exists, user declines overwrite — should refresh (load-merge-save)."""
    config_file, workspace_dir = mock_paths
    config_file.write_text('{"existing": true}')

    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0
    assert "Config already exists" in result.stdout
    assert "existing values preserved" in result.stdout
    assert workspace_dir.exists()
    assert (workspace_dir / "AGENTS.md").exists()


def test_onboard_existing_config_overwrite(mock_paths):
    """Config exists, user confirms overwrite — should reset to defaults."""
    config_file, workspace_dir = mock_paths
    config_file.write_text('{"existing": true}')

    result = runner.invoke(app, ["onboard"], input="y\n")

    assert result.exit_code == 0
    assert "Config already exists" in result.stdout
    assert "Config reset to defaults" in result.stdout
    assert workspace_dir.exists()


def test_onboard_existing_workspace_safe_create(mock_paths):
    """Workspace exists — should not recreate, but still add missing templates."""
    config_file, workspace_dir = mock_paths
    workspace_dir.mkdir(parents=True)
    config_file.write_text("{}")

    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0
    assert "Created workspace" not in result.stdout
    assert "Created AGENTS.md" in result.stdout
    assert (workspace_dir / "AGENTS.md").exists()


def test_onboard_noninteractive_skips_bitwarden_prompt(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: False)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: None)

    result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 0
    assert "OpenAI Codex login skipped because onboarding is running non-interactively" in result.stdout
    assert "Bitwarden setup skipped because onboarding is running non-interactively" in result.stdout

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["tools"]["mcpServers"] == {}


def test_onboard_interactive_runs_openai_codex_login(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    called: dict[str, bool] = {"login": False}

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: None)
    monkeypatch.setattr("nanobot.cli.commands._configure_bitwarden_onboarding", lambda _config: False)
    monkeypatch.setattr("nanobot.cli.commands._configure_channels_onboarding", lambda _config: False)
    monkeypatch.setattr(
        "nanobot.cli.commands._login_openai_codex",
        lambda: called.__setitem__("login", True),
    )

    result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 0
    assert called["login"] is True
    assert "Default: sign in to OpenAI Codex for the default provider." in result.stdout
    assert "nanobot provider login openai-codex" not in result.stdout
    assert "Default model: openai-codex/gpt-5.4" in result.stdout
    assert "  1. Chat:" in result.stdout


def test_onboard_interactive_can_skip_openai_codex_update_when_already_configured(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    called: dict[str, bool] = {"login": False}

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: "acct-123")
    monkeypatch.setattr("nanobot.cli.commands._configure_bitwarden_onboarding", lambda _config: False)
    monkeypatch.setattr("nanobot.cli.commands._configure_channels_onboarding", lambda _config: False)
    monkeypatch.setattr(
        "nanobot.cli.commands._login_openai_codex",
        lambda: called.__setitem__("login", True),
    )

    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0
    assert called["login"] is False
    assert "OpenAI Codex is already configured." in result.stdout
    assert "Update OpenAI Codex access?" in result.stdout
    assert "  1. Chat:" in result.stdout


def test_onboard_interactive_can_update_openai_codex_when_already_configured(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    called: dict[str, bool] = {"login": False}

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: "acct-123")
    monkeypatch.setattr("nanobot.cli.commands._configure_bitwarden_onboarding", lambda _config: False)
    monkeypatch.setattr("nanobot.cli.commands._configure_channels_onboarding", lambda _config: False)
    monkeypatch.setattr(
        "nanobot.cli.commands._login_openai_codex",
        lambda: called.__setitem__("login", True),
    )

    result = runner.invoke(app, ["onboard"], input="y\n")

    assert result.exit_code == 0
    assert called["login"] is True
    assert "OpenAI Codex is already configured." in result.stdout
    assert "Update OpenAI Codex access?" in result.stdout


def test_onboard_can_configure_bitwarden_mcp(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    password_file = tmp_path / ".nanobot" / "bitwarden-password"

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: None)
    monkeypatch.setattr("nanobot.cli.commands._login_openai_codex", lambda: None)
    monkeypatch.setattr("nanobot.cli.commands._configure_channels_onboarding", lambda _config: False)
    monkeypatch.setattr("nanobot.cli.commands.Path.home", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["onboard"],
        input="y\ncli-client-id\ncli-client-secret\nbitwarden-master-password\n",
    )

    assert result.exit_code == 0
    assert "Bitwarden MCP access saved to your config" in result.stdout

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    bitwarden = saved["tools"]["mcpServers"]["bitwarden"]

    assert bitwarden["type"] == "stdio"
    assert bitwarden["command"] == "nanobot"
    assert bitwarden["args"] == ["bitwarden-mcp"]
    assert bitwarden["toolTimeout"] == 60
    assert bitwarden["env"]["BW_CLIENTID"] == "cli-client-id"
    assert bitwarden["env"]["BW_CLIENTSECRET"] == "cli-client-secret"
    assert bitwarden["env"]["BW_PASSWORD_FILE"] == str(password_file)
    assert "BW_SESSION" not in bitwarden["env"]
    assert password_file.read_text(encoding="utf-8") == "bitwarden-master-password\n"


def test_onboard_does_not_save_incomplete_bitwarden_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    password_file = tmp_path / ".nanobot" / "bitwarden-password"

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._get_openai_codex_account_id", lambda: None)
    monkeypatch.setattr("nanobot.cli.commands._login_openai_codex", lambda: None)
    monkeypatch.setattr("nanobot.cli.commands._configure_channels_onboarding", lambda _config: False)
    monkeypatch.setattr("nanobot.cli.commands.Path.home", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["onboard"],
        input="y\ncli-client-id\ncli-client-secret\n\n",
    )

    assert result.exit_code == 0
    assert "Bitwarden setup not saved" in result.stdout

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["tools"]["mcpServers"] == {}
    assert not password_file.exists()


def test_onboard_can_configure_telegram_channel(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda: workspace)
    monkeypatch.setattr("nanobot.cli.commands._supports_interactive_onboarding", lambda: True)
    monkeypatch.setattr("nanobot.cli.commands._run_openai_codex_onboarding_login", lambda: False)
    monkeypatch.setattr("nanobot.cli.commands._configure_bitwarden_onboarding", lambda _config: False)

    class _TelegramChannel:
        display_name = "Telegram"

    monkeypatch.setattr("nanobot.channels.registry.discover_channel_names", lambda: ["telegram"])
    monkeypatch.setattr("nanobot.channels.registry.load_channel_class", lambda _name: _TelegramChannel)

    result = runner.invoke(
        app,
        ["onboard"],
        input="y\n1\ntelegram-token\n*\nmention\nn\nn\n",
    )

    assert result.exit_code == 0
    assert "Channel configuration saved to your config" in result.stdout

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    telegram = saved["channels"]["telegram"]

    assert telegram["enabled"] is True
    assert telegram["token"] == "telegram-token"
    assert telegram["allowFrom"] == ["*"]
    assert telegram["groupPolicy"] == "mention"
    assert telegram["replyToMessage"] is False


def test_config_matches_github_copilot_codex_with_hyphen_prefix():
    config = Config()
    config.agents.defaults.model = "github-copilot/gpt-5.3-codex"

    assert config.get_provider_name() == "github_copilot"


def test_config_defaults_to_latest_openai_codex_model():
    config = Config()

    assert config.agents.defaults.model == "openai-codex/gpt-5.4"
    assert config.get_provider_name() == "openai_codex"


def test_config_matches_openai_codex_with_hyphen_prefix():
    config = Config()
    config.agents.defaults.model = "openai-codex/gpt-5.4"

    assert config.get_provider_name() == "openai_codex"


def test_config_matches_explicit_ollama_prefix_without_api_key():
    config = Config()
    config.agents.defaults.model = "ollama/llama3.2"

    assert config.get_provider_name() == "ollama"
    assert config.get_api_base() == "http://localhost:11434"


def test_config_explicit_ollama_provider_uses_default_localhost_api_base():
    config = Config()
    config.agents.defaults.provider = "ollama"
    config.agents.defaults.model = "llama3.2"

    assert config.get_provider_name() == "ollama"
    assert config.get_api_base() == "http://localhost:11434"


def test_config_auto_detects_ollama_from_local_api_base():
    config = Config.model_validate(
        {
            "agents": {"defaults": {"provider": "auto", "model": "llama3.2"}},
            "providers": {"ollama": {"apiBase": "http://localhost:11434"}},
        }
    )

    assert config.get_provider_name() == "ollama"
    assert config.get_api_base() == "http://localhost:11434"


def test_find_by_model_prefers_explicit_prefix_over_generic_codex_keyword():
    spec = find_by_model("github-copilot/gpt-5.3-codex")

    assert spec is not None
    assert spec.name == "github_copilot"


def test_litellm_provider_canonicalizes_github_copilot_hyphen_prefix():
    provider = LiteLLMProvider(default_model="github-copilot/gpt-5.3-codex")

    resolved = provider._resolve_model("github-copilot/gpt-5.3-codex")

    assert resolved == "github_copilot/gpt-5.3-codex"


def test_openai_codex_strip_prefix_supports_hyphen_and_underscore():
    assert _strip_model_prefix("openai-codex/gpt-5.4") == "gpt-5.4"
    assert _strip_model_prefix("openai_codex/gpt-5.4") == "gpt-5.4"


@pytest.fixture
def mock_agent_runtime(tmp_path):
    """Mock agent command dependencies for focused CLI tests."""
    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "default-workspace")
    cron_dir = tmp_path / "data" / "cron"

    with patch("nanobot.config.loader.load_config", return_value=config) as mock_load_config, \
         patch("nanobot.config.paths.get_cron_dir", return_value=cron_dir), \
         patch("nanobot.cli.commands.sync_workspace_templates") as mock_sync_templates, \
         patch("nanobot.cli.commands._make_provider", return_value=object()), \
         patch("nanobot.cli.commands._print_agent_response") as mock_print_response, \
         patch("nanobot.bus.queue.MessageBus"), \
         patch("nanobot.cron.service.CronService"), \
         patch("nanobot.agent.loop.AgentLoop") as mock_agent_loop_cls:

        agent_loop = MagicMock()
        agent_loop.channels_config = None
        agent_loop.process_direct = AsyncMock(return_value="mock-response")
        agent_loop.close_mcp = AsyncMock(return_value=None)
        mock_agent_loop_cls.return_value = agent_loop

        yield {
            "config": config,
            "load_config": mock_load_config,
            "sync_templates": mock_sync_templates,
            "agent_loop_cls": mock_agent_loop_cls,
            "agent_loop": agent_loop,
            "print_response": mock_print_response,
        }


def test_agent_help_shows_workspace_and_config_options():
    result = runner.invoke(app, ["agent", "--help"])

    assert result.exit_code == 0
    assert "--workspace" in result.stdout
    assert "-w" in result.stdout
    assert "--config" in result.stdout
    assert "-c" in result.stdout


def test_agent_uses_default_config_when_no_workspace_or_config_flags(mock_agent_runtime):
    result = runner.invoke(app, ["agent", "-m", "hello"])

    assert result.exit_code == 0
    assert mock_agent_runtime["load_config"].call_args.args == (None,)
    assert mock_agent_runtime["sync_templates"].call_args.args == (
        mock_agent_runtime["config"].workspace_path,
    )
    assert mock_agent_runtime["agent_loop_cls"].call_args.kwargs["workspace"] == (
        mock_agent_runtime["config"].workspace_path
    )
    assert mock_agent_runtime["agent_loop_cls"].call_args.kwargs["web_search_base_url"] is None
    assert mock_agent_runtime["agent_loop_cls"].call_args.kwargs["web_search_max_results"] == 5
    mock_agent_runtime["agent_loop"].process_direct.assert_awaited_once()
    mock_agent_runtime["print_response"].assert_called_once_with("mock-response", render_markdown=True)


def test_agent_uses_explicit_config_path(mock_agent_runtime, tmp_path: Path):
    config_path = tmp_path / "agent-config.json"
    config_path.write_text("{}")

    result = runner.invoke(app, ["agent", "-m", "hello", "-c", str(config_path)])

    assert result.exit_code == 0
    assert mock_agent_runtime["load_config"].call_args.args == (config_path.resolve(),)


def test_agent_config_sets_active_path(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    seen: dict[str, Path] = {}

    monkeypatch.setattr(
        "nanobot.config.loader.set_config_path",
        lambda path: seen.__setitem__("config_path", path),
    )
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr("nanobot.config.paths.get_cron_dir", lambda: config_file.parent / "cron")
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _path: None)
    monkeypatch.setattr("nanobot.cli.commands._make_provider", lambda _config: object())
    monkeypatch.setattr("nanobot.bus.queue.MessageBus", lambda: object())
    monkeypatch.setattr("nanobot.cron.service.CronService", lambda _store: object())

    class _FakeAgentLoop:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def process_direct(self, *_args, **_kwargs) -> str:
            return "ok"

        async def close_mcp(self) -> None:
            return None

    monkeypatch.setattr("nanobot.agent.loop.AgentLoop", _FakeAgentLoop)
    monkeypatch.setattr("nanobot.cli.commands._print_agent_response", lambda *_args, **_kwargs: None)

    result = runner.invoke(app, ["agent", "-m", "hello", "-c", str(config_file)])

    assert result.exit_code == 0
    assert seen["config_path"] == config_file.resolve()


def test_agent_overrides_workspace_path(mock_agent_runtime):
    workspace_path = Path("/tmp/agent-workspace")

    result = runner.invoke(app, ["agent", "-m", "hello", "-w", str(workspace_path)])

    assert result.exit_code == 0
    assert mock_agent_runtime["config"].agents.defaults.workspace == str(workspace_path)
    assert mock_agent_runtime["sync_templates"].call_args.args == (workspace_path,)
    assert mock_agent_runtime["agent_loop_cls"].call_args.kwargs["workspace"] == workspace_path


def test_agent_workspace_override_wins_over_config_workspace(mock_agent_runtime, tmp_path: Path):
    config_path = tmp_path / "agent-config.json"
    config_path.write_text("{}")
    workspace_path = Path("/tmp/agent-workspace")

    result = runner.invoke(
        app,
        ["agent", "-m", "hello", "-c", str(config_path), "-w", str(workspace_path)],
    )

    assert result.exit_code == 0
    assert mock_agent_runtime["load_config"].call_args.args == (config_path.resolve(),)
    assert mock_agent_runtime["config"].agents.defaults.workspace == str(workspace_path)
    assert mock_agent_runtime["sync_templates"].call_args.args == (workspace_path,)
    assert mock_agent_runtime["agent_loop_cls"].call_args.kwargs["workspace"] == workspace_path


def test_agent_warns_about_deprecated_memory_window(mock_agent_runtime):
    mock_agent_runtime["config"].agents.defaults.memory_window = 100

    result = runner.invoke(app, ["agent", "-m", "hello"])

    assert result.exit_code == 0
    assert "memoryWindow" in result.stdout
    assert "contextWindowTokens" in result.stdout


def test_gateway_uses_workspace_from_config_by_default(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "config-workspace")
    seen: dict[str, Path] = {}

    monkeypatch.setattr(
        "nanobot.config.loader.set_config_path",
        lambda path: seen.__setitem__("config_path", path),
    )
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr(
        "nanobot.cli.commands.sync_workspace_templates",
        lambda path: seen.__setitem__("workspace", path),
    )
    monkeypatch.setattr(
        "nanobot.cli.commands._make_provider",
        lambda _config: (_ for _ in ()).throw(_StopGatewayError("stop")),
    )

    result = runner.invoke(app, ["gateway", "--config", str(config_file)])

    assert isinstance(result.exception, _StopGatewayError)
    assert seen["config_path"] == config_file.resolve()
    assert seen["workspace"] == Path(config.agents.defaults.workspace)


def test_gateway_workspace_option_overrides_config(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "config-workspace")
    override = tmp_path / "override-workspace"
    seen: dict[str, Path] = {}

    monkeypatch.setattr("nanobot.config.loader.set_config_path", lambda _path: None)
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr(
        "nanobot.cli.commands.sync_workspace_templates",
        lambda path: seen.__setitem__("workspace", path),
    )
    monkeypatch.setattr(
        "nanobot.cli.commands._make_provider",
        lambda _config: (_ for _ in ()).throw(_StopGatewayError("stop")),
    )

    result = runner.invoke(
        app,
        ["gateway", "--config", str(config_file), "--workspace", str(override)],
    )

    assert isinstance(result.exception, _StopGatewayError)
    assert seen["workspace"] == override
    assert config.workspace_path == override


def test_gateway_warns_about_deprecated_memory_window(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.agents.defaults.memory_window = 100

    monkeypatch.setattr("nanobot.config.loader.set_config_path", lambda _path: None)
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _path: None)
    monkeypatch.setattr(
        "nanobot.cli.commands._make_provider",
        lambda _config: (_ for _ in ()).throw(_StopGatewayError("stop")),
    )

    result = runner.invoke(app, ["gateway", "--config", str(config_file)])

    assert isinstance(result.exception, _StopGatewayError)
    assert "memoryWindow" in result.stdout
    assert "contextWindowTokens" in result.stdout

def test_gateway_uses_config_directory_for_cron_store(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "config-workspace")
    seen: dict[str, Path] = {}

    monkeypatch.setattr("nanobot.config.loader.set_config_path", lambda _path: None)
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr("nanobot.config.paths.get_cron_dir", lambda: config_file.parent / "cron")
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _path: None)
    monkeypatch.setattr("nanobot.cli.commands._make_provider", lambda _config: object())
    monkeypatch.setattr("nanobot.bus.queue.MessageBus", lambda: object())
    monkeypatch.setattr("nanobot.session.manager.SessionManager", lambda _workspace: object())

    class _StopCron:
        def __init__(self, store_path: Path) -> None:
            seen["cron_store"] = store_path
            raise _StopGatewayError("stop")

    monkeypatch.setattr("nanobot.cron.service.CronService", _StopCron)

    result = runner.invoke(app, ["gateway", "--config", str(config_file)])

    assert isinstance(result.exception, _StopGatewayError)
    assert seen["cron_store"] == config_file.parent / "cron" / "jobs.json"


def test_gateway_uses_configured_port_when_cli_flag_is_missing(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.gateway.port = 18791

    monkeypatch.setattr("nanobot.config.loader.set_config_path", lambda _path: None)
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _path: None)
    monkeypatch.setattr(
        "nanobot.cli.commands._make_provider",
        lambda _config: (_ for _ in ()).throw(_StopGatewayError("stop")),
    )

    result = runner.invoke(app, ["gateway", "--config", str(config_file)])

    assert isinstance(result.exception, _StopGatewayError)
    assert "port 18791" in result.stdout


def test_gateway_cli_port_overrides_configured_port(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    config = Config()
    config.gateway.port = 18791

    monkeypatch.setattr("nanobot.config.loader.set_config_path", lambda _path: None)
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda _path=None: config)
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _path: None)
    monkeypatch.setattr(
        "nanobot.cli.commands._make_provider",
        lambda _config: (_ for _ in ()).throw(_StopGatewayError("stop")),
    )

    result = runner.invoke(app, ["gateway", "--config", str(config_file), "--port", "18792"])

    assert isinstance(result.exception, _StopGatewayError)
    assert "port 18792" in result.stdout
