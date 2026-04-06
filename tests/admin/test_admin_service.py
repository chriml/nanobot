from pathlib import Path

import json

from nanobot.admin.db import BotAdminStore, admin_db_path, bot_ui_dist_dir, bot_ui_meta_path, bot_ui_src_dir
from nanobot.admin.service import BotAdminService


def test_overview_includes_self_runtime(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    service = BotAdminService(
        workspace=workspace,
        bot_name="Atlas",
        model="anthropic/claude-opus-4-5",
        mode="gateway",
        config_path=tmp_path / "config.json",
        instances_dir=None,
    )

    overview = service.overview()

    assert overview["summary"]["totalBots"] == 1
    assert overview["self"]["slug"] == "atlas"
    assert overview["bots"][0]["databasePath"] == str(admin_db_path(workspace))
    assert overview["bots"][0]["customUi"]["route"] == "/admin/custom/atlas/"
    assert overview["bots"][0]["customUi"]["sourceDir"] == str(bot_ui_src_dir(workspace))
    assert overview["bots"][0]["customUi"]["distDir"] == str(bot_ui_dist_dir(workspace))
    detail = service.bot_detail("atlas")
    assert detail is not None
    assert detail["ui"]["pages"]["bot"][0]["id"] == "bot-home"
    assert detail["ui"]["layouts"]["bot"][0]["bricks"][0]["id"] == "status"
    assert detail["ui"]["links"]["customUi"] == "/admin/custom/atlas/"
    assert service.custom_ui_dir("atlas") == bot_ui_dist_dir(workspace)


def test_bot_ui_status_reads_published_bundle_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    dist_dir = bot_ui_dist_dir(workspace)
    (dist_dir / "entry.js").write_text("export function mount() {}", encoding="utf-8")
    (dist_dir / "entry.css").write_text(":host { display: block; }", encoding="utf-8")
    bot_ui_meta_path(workspace).write_text(
        json.dumps(
            {
                "entry": "entry.js",
                "css": "entry.css",
                "version": "17",
                "updatedAt": 123.5,
                "status": "ready",
            }
        ),
        encoding="utf-8",
    )

    service = BotAdminService(
        workspace=workspace,
        bot_name="Atlas",
        model="anthropic/claude-opus-4-5",
        mode="gateway",
        config_path=tmp_path / "config.json",
        instances_dir=None,
    )

    payload = service.bot_ui_status("atlas")

    assert payload is not None
    assert payload["ui"]["entryUrl"] == "/admin/custom/atlas/entry.js"
    assert payload["ui"]["cssUrl"] == "/admin/custom/atlas/entry.css"
    assert payload["ui"]["version"] == "17"


def test_create_bot_bootstraps_database_and_returns_start_result(tmp_path: Path, monkeypatch) -> None:
    instances_dir = tmp_path / "instances"
    service = BotAdminService(
        workspace=tmp_path / "controller",
        bot_name="Controller",
        model="openai/gpt-5",
        mode="gateway",
        instances_dir=instances_dir,
    )

    commands = []

    class _Proc:
        returncode = 0
        stdout = "started"
        stderr = ""

    def _fake_run(command, **_kwargs):
        commands.append(command)
        return _Proc()

    monkeypatch.setattr("nanobot.admin.service.subprocess.run", _fake_run)

    result = service.create_bot(name="Scout", presets=["local-stack"], host_port=18801, auto_start=True)

    assert result["slug"] == "scout"
    assert result["started"] is True
    assert any("gateway" in part for part in commands[0])

    store = BotAdminStore(admin_db_path(instances_dir / "scout" / "workspace"))
    runtime = store.runtime_state()
    assert runtime["bot_name"] == "Scout"
    assert runtime["host_port"] == 18801


def test_run_action_uses_saved_host_port(tmp_path: Path, monkeypatch) -> None:
    instances_dir = tmp_path / "instances"
    workspace = instances_dir / "scout" / "workspace"
    store = BotAdminStore(admin_db_path(workspace))
    store.bootstrap(
        bot_name="Scout",
        bot_slug="scout",
        model="openai/gpt-5",
        mode="gateway",
        workspace_path=workspace,
        config_path=instances_dir / "scout" / "config.json",
        host_port=18812,
        status="created",
    )

    service = BotAdminService(
        workspace=tmp_path / "controller",
        bot_name="Controller",
        model="openai/gpt-5",
        mode="gateway",
        instances_dir=instances_dir,
        image="nanochris:test",
    )

    calls = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(command, **_kwargs):
        calls.append(command)
        return _Proc()

    monkeypatch.setattr("nanobot.admin.service.subprocess.run", _fake_run)

    result = service.run_action("scout", "start")

    assert result["ok"] is True
    assert "-p" in calls[0]
    assert "18812:18790" in calls[0]
