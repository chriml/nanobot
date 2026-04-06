from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from nanobot.admin.server import create_admin_app
from nanobot.admin.service import BotAdminService

try:
    from aiohttp.test_utils import TestClient, TestServer

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

pytest_plugins = ("pytest_asyncio",)


@pytest_asyncio.fixture
async def aiohttp_client():
    clients: list[TestClient] = []

    async def _make_client(app):
        client = TestClient(TestServer(app))
        await client.start_server()
        clients.append(client)
        return client

    try:
        yield _make_client
    finally:
        for client in clients:
            await client.close()


@pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed")
@pytest.mark.asyncio
async def test_admin_chat_and_custom_ui_routes(tmp_path: Path, aiohttp_client) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    ui_dist = workspace / ".nanobot-admin" / "ui-dist"
    ui_dist.mkdir(parents=True, exist_ok=True)
    (ui_dist / "entry.js").write_text("export function mount() {}", encoding="utf-8")
    (ui_dist / "entry.css").write_text("body { color: red; }", encoding="utf-8")
    (workspace / ".nanobot-admin" / "ui-meta.json").write_text(
        json.dumps({"entry": "entry.js", "css": "entry.css", "version": "3", "status": "ready"}),
        encoding="utf-8",
    )

    service = BotAdminService(
        workspace=workspace,
        bot_name="Atlas",
        model="openai/gpt-5",
        mode="gateway",
        config_path=tmp_path / "config.json",
    )
    service.loop = SimpleNamespace(
        process_direct=AsyncMock(return_value=SimpleNamespace(content="shell reply"))
    )

    client = await aiohttp_client(create_admin_app(service))

    chat = await client.post("/admin/api/chat", json={"scope": "bot", "slug": "atlas", "message": "hello"})
    assert chat.status == 200
    payload = await chat.json()
    assert payload["content"] == "shell reply"

    asset = await client.get("/admin/custom/atlas/entry.js")
    assert asset.status == 200
    text = await asset.text()
    assert "export function mount" in text

    ui = await client.get("/admin/api/bots/atlas/ui")
    assert ui.status == 200
    ui_payload = await ui.json()
    assert ui_payload["ui"]["entryUrl"] == "/admin/custom/atlas/entry.js"
    assert ui_payload["ui"]["cssUrl"] == "/admin/custom/atlas/entry.css"


@pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed")
@pytest.mark.asyncio
async def test_admin_password_protects_routes(tmp_path: Path, aiohttp_client, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    ui_dist = workspace / ".nanobot-admin" / "ui-dist"
    ui_dist.mkdir(parents=True, exist_ok=True)
    (ui_dist / "entry.js").write_text("export function mount() {}", encoding="utf-8")
    (workspace / ".nanobot-admin" / "ui-meta.json").write_text(
        json.dumps({"entry": "entry.js", "version": "1", "status": "ready"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("NANOBOT_ADMIN_PASSWORD", "secret-pass")

    service = BotAdminService(
        workspace=workspace,
        bot_name="Atlas",
        model="openai/gpt-5",
        mode="gateway",
        config_path=tmp_path / "config.json",
    )
    service.loop = SimpleNamespace(
        process_direct=AsyncMock(return_value=SimpleNamespace(content="shell reply"))
    )

    client = await aiohttp_client(create_admin_app(service))

    overview = await client.get("/admin/api/overview")
    assert overview.status == 401

    login = await client.post("/admin/api/auth/login", json={"password": "secret-pass"})
    assert login.status == 200
    login_payload = await login.json()
    assert login_payload["ok"] is True

    custom = await client.get("/admin/custom/atlas/entry.js")
    assert custom.status == 200
    assert "export function mount" in await custom.text()


@pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed")
@pytest.mark.asyncio
async def test_admin_chat_proxies_to_selected_bot_runtime(tmp_path: Path, aiohttp_client, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    service = BotAdminService(
        workspace=workspace,
        bot_name="Controller",
        model="openai/gpt-5",
        mode="gateway",
        config_path=tmp_path / "config.json",
    )
    service.loop = None
    monkeypatch.setattr(
        service,
        "resolve_bot_record",
        lambda slug: {"slug": slug, "hostPort": 18812} if slug == "scout" else None,
    )

    class _FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "proxied reply",
                        }
                    }
                ]
            }

    class _FakeSession:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            assert url == "http://127.0.0.1:18812/v1/chat/completions"
            assert json["session_id"] == "admin-ui:bot:scout"
            return _FakeResponse()

    monkeypatch.setattr("nanobot.admin.server.ClientSession", _FakeSession)

    client = await aiohttp_client(create_admin_app(service))
    chat = await client.post("/admin/api/chat", json={"scope": "bot", "slug": "scout", "message": "build ui"})

    assert chat.status == 200
    payload = await chat.json()
    assert payload["content"] == "proxied reply"
    assert payload["proxied"] is True
