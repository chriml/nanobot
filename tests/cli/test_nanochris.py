import json
import re

from typer.testing import CliRunner

from nanobot.cli.nanochris import app
from nanobot.instances import resolve_instance_paths

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_nanochris_help_only_shows_main_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    stripped_output = _strip_ansi(result.stdout)
    assert "newbot" in stripped_output
    assert "manage" in stripped_output
    assert "gateway" not in stripped_output
    assert "channels" not in stripped_output


def test_nanochris_newbot_applies_presets(tmp_path):
    result = runner.invoke(
        app,
        [
            "newbot",
            "Chris",
            "--base-dir",
            str(tmp_path),
            "--preset",
            "telegram",
            "--preset",
            "openai-codex-gpt-5.2",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    instance = resolve_instance_paths("Chris", base_dir=tmp_path)
    saved = json.loads(instance.config_path.read_text(encoding="utf-8"))
    assert saved["channels"]["telegram"]["enabled"] is True
    assert saved["agents"]["defaults"]["model"] == "openai-codex/gpt-5.2-codex"


def test_nanochris_manage_main_actions(tmp_path):
    instance = resolve_instance_paths("Chris", base_dir=tmp_path)
    instance.root.mkdir(parents=True)
    instance.config_path.write_text('{"providers":{"openai":{"apiKey":"sk-test"}}}', encoding="utf-8")

    config_result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "config"],
    )
    start_result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "--dry-run", "start"],
    )
    stop_result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "--dry-run", "stop"],
    )
    logs_result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "--dry-run", "logs"],
    )

    assert config_result.exit_code == 0
    assert '"openai"' in _strip_ansi(config_result.stdout)

    assert start_result.exit_code == 0
    assert "docker network create nanochris-net" in _strip_ansi(start_result.stdout)
    assert "docker run -d --name nanochris-searxng --network nanochris-net" in _strip_ansi(start_result.stdout)
    assert "docker run -d --name nanochris-chris" in _strip_ansi(start_result.stdout)
    assert "--network nanochris-net" in _strip_ansi(start_result.stdout)
    assert "/root/.local/share/oauth-cli-kit" in _strip_ansi(start_result.stdout)
    assert "/root/.cache/whisper" in _strip_ansi(start_result.stdout)
    assert "host.docker.internal:host-gateway" in _strip_ansi(start_result.stdout)
    assert "NANOBOT_TOOLS__WEB__SEARCH__PROVIDER=searxng" in _strip_ansi(start_result.stdout)
    assert "NANOBOT_TOOLS__WEB__SEARCH__BASE_URL=http://nanochris-searxng:8080" in _strip_ansi(start_result.stdout)

    assert stop_result.exit_code == 0
    assert "docker rm -f nanochris-chris" in _strip_ansi(stop_result.stdout)

    assert logs_result.exit_code == 0
    assert "docker logs -f nanochris-chris" in _strip_ansi(logs_result.stdout)


def test_nanochris_manage_login_codex_dry_run(tmp_path):
    result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "--dry-run", "login", "codex"],
    )

    assert result.exit_code == 0
    stripped_output = _strip_ansi(result.stdout)
    assert "docker network create nanochris-net" in stripped_output
    assert "provider login openai-codex" in stripped_output
    assert "/root/.local/share/oauth-cli-kit" in stripped_output
    assert "/root/.cache/whisper" in stripped_output
    assert "--network nanochris-net" in stripped_output
    assert "host.docker.internal:host-gateway" in stripped_output
    assert "NANOBOT_TOOLS__WEB__SEARCH__BASE_URL=http://nanochris-searxng:8080" in stripped_output


def test_nanochris_manage_login_claude_saves_config(tmp_path):
    result = runner.invoke(
        app,
        ["manage", "Chris", "--base-dir", str(tmp_path), "login", "claude"],
        input="sk-ant-test\n",
    )

    assert result.exit_code == 0
    instance = resolve_instance_paths("Chris", base_dir=tmp_path)
    saved = json.loads(instance.config_path.read_text(encoding="utf-8"))
    assert saved["agents"]["defaults"]["provider"] == "anthropic"
    assert saved["providers"]["anthropic"]["apiKey"] == "sk-ant-test"
