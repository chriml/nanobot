from pathlib import Path

from nanobot.admin.db import BotAdminStore, admin_db_path, bot_ui_dist_dir, bot_ui_meta_path, bot_ui_src_dir


def test_admin_store_bootstrap_and_usage(tmp_path: Path) -> None:
    db_path = admin_db_path(tmp_path / "workspace")
    store = BotAdminStore(db_path)

    store.bootstrap(
        bot_name="Atlas",
        bot_slug="atlas",
        model="openai/gpt-5",
        mode="gateway",
        workspace_path=tmp_path / "workspace",
        config_path=tmp_path / "workspace" / "config.json",
        host_port=19100,
        status="running",
    )
    store.record_usage(
        {
            "prompt_tokens": 42,
            "completion_tokens": 11,
            "cached_tokens": 5,
            "total_tokens": 53,
        },
        session_key="cli:direct",
    )

    runtime = store.runtime_state()

    assert runtime["bot_name"] == "Atlas"
    assert runtime["bot_slug"] == "atlas"
    assert runtime["host_port"] == 19100
    assert runtime["prompt_tokens"] == 42
    assert runtime["completion_tokens"] == 11
    assert runtime["cached_tokens"] == 5
    assert runtime["total_runs"] == 1
    assert store.token_history()[-1]["total_tokens"] == 53
    assert {brick["id"] for brick in store.bricks()} >= {"status", "tokens", "workspace", "overview"}
    assert {page["id"] for page in store.pages()} >= {"overview", "bot-home"}
    manifest = store.manifest()
    assert manifest["version"] == 1
    assert manifest["botLayout"]["hero"] == ["status"]
    assert bot_ui_src_dir(tmp_path / "workspace").name == "ui-src"
    assert bot_ui_dist_dir(tmp_path / "workspace").name == "ui-dist"
    assert bot_ui_meta_path(tmp_path / "workspace").name == "ui-meta.json"
