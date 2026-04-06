"""SQLite-backed storage for per-bot admin state."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from nanobot.utils.helpers import ensure_dir

_DEFAULT_BRICKS = (
    {"id": "status", "scope": "bot", "kind": "status", "title": "Status", "position": 10},
    {"id": "tokens", "scope": "bot", "kind": "tokens", "title": "Token Usage", "position": 20},
    {"id": "workspace", "scope": "bot", "kind": "workspace", "title": "Workspace", "position": 30},
    {"id": "overview", "scope": "global", "kind": "overview", "title": "Overview", "position": 10},
)

_DEFAULT_PAGES = (
    {
        "id": "overview",
        "scope": "global",
        "title": "Fleet",
        "path": "/admin",
        "layout": "fleet",
        "position": 10,
    },
    {
        "id": "bot-home",
        "scope": "bot",
        "title": "Bot",
        "path": "/admin/bot/{slug}",
        "layout": "bot-detail",
        "position": 10,
    },
)

_DEFAULT_MANIFEST = {
    "version": 1,
    "botLayout": {
        "hero": ["status"],
        "primary": ["tokens", "workspace"],
    },
    "globalLayout": {
        "summary": ["overview"],
        "fleet": ["overview"],
    },
}


def admin_db_path(workspace: Path) -> Path:
    """Return the default admin SQLite path for a bot workspace."""
    return ensure_dir(workspace / ".nanobot-admin") / "state.db"


def bot_admin_dir(workspace: Path) -> Path:
    """Return the shared admin directory for a bot workspace."""
    return ensure_dir(workspace / ".nanobot-admin")


def bot_ui_src_dir(workspace: Path) -> Path:
    """Return the bot-local UI source directory edited by the coding agent."""
    return ensure_dir(bot_admin_dir(workspace) / "ui-src")


def bot_ui_dist_dir(workspace: Path) -> Path:
    """Return the published bot-local UI bundle directory served by the shell."""
    return ensure_dir(bot_admin_dir(workspace) / "ui-dist")


def bot_ui_meta_path(workspace: Path) -> Path:
    """Return the metadata file that tracks the published bot UI bundle."""
    return bot_admin_dir(workspace) / "ui-meta.json"


def bot_ui_dir(workspace: Path) -> Path:
    """Backward-compatible alias for the published bot UI bundle directory."""
    return bot_ui_dist_dir(workspace)


class BotAdminStore:
    """Persist runtime/admin state for a single bot."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_dir(db_path.parent)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    bot_name TEXT NOT NULL DEFAULT '',
                    bot_slug TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT '',
                    workspace_path TEXT NOT NULL DEFAULT '',
                    config_path TEXT NOT NULL DEFAULT '',
                    host_port INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    started_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0,
                    last_error TEXT,
                    last_session_key TEXT,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    total_runs INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS token_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at REAL NOT NULL,
                    session_key TEXT,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS ui_bricks (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS ui_pages (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    layout TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS ui_manifest (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    updated_at REAL NOT NULL DEFAULT 0
                );
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(runtime_state)").fetchall()
            }
            if "host_port" not in columns:
                conn.execute("ALTER TABLE runtime_state ADD COLUMN host_port INTEGER NOT NULL DEFAULT 0")
            for brick in _DEFAULT_BRICKS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ui_bricks (id, scope, kind, title, position, config_json, enabled)
                    VALUES (?, ?, ?, ?, ?, '{}', 1)
                    """,
                    (brick["id"], brick["scope"], brick["kind"], brick["title"], brick["position"]),
                )
            for page in _DEFAULT_PAGES:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ui_pages (id, scope, title, path, layout, position, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (page["id"], page["scope"], page["title"], page["path"], page["layout"], page["position"]),
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO ui_manifest (id, manifest_json, updated_at)
                VALUES (1, ?, ?)
                """,
                (json.dumps(_DEFAULT_MANIFEST), time.time()),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO runtime_state (
                    id, bot_name, bot_slug, model, mode, workspace_path, config_path, status, started_at, updated_at
                )
                VALUES (1, '', '', '', '', '', '', 'unknown', 0, 0)
                """
            )

    def bootstrap(
        self,
        *,
        bot_name: str,
        bot_slug: str,
        model: str,
        mode: str,
        workspace_path: Path,
        config_path: Path | None = None,
        host_port: int | None = None,
        status: str = "starting",
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runtime_state
                SET bot_name = ?, bot_slug = ?, model = ?, mode = ?, workspace_path = ?,
                    config_path = ?, host_port = ?, status = ?, started_at = CASE WHEN started_at = 0 THEN ? ELSE started_at END,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    bot_name,
                    bot_slug,
                    model,
                    mode,
                    str(workspace_path),
                    str(config_path) if config_path else "",
                    int(host_port or 0),
                    status,
                    now,
                    now,
                ),
            )

    def update_runtime(
        self,
        *,
        status: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        last_error: str | None = None,
        last_session_key: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [time.time()]
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if model is not None:
            fields.append("model = ?")
            values.append(model)
        if mode is not None:
            fields.append("mode = ?")
            values.append(mode)
        if last_error is not None:
            fields.append("last_error = ?")
            values.append(last_error)
        if last_session_key is not None:
            fields.append("last_session_key = ?")
            values.append(last_session_key)
        values.append(1)
        with self._connect() as conn:
            conn.execute(f"UPDATE runtime_state SET {', '.join(fields)} WHERE id = ?", values)

    def record_usage(self, usage: dict[str, int], *, session_key: str | None = None) -> None:
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        cached = int(usage.get("cached_tokens", 0) or 0)
        total = int(usage.get("total_tokens", prompt + completion) or 0)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO token_samples (
                    recorded_at, session_key, prompt_tokens, completion_tokens, cached_tokens, total_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (time.time(), session_key, prompt, completion, cached, total),
            )
            conn.execute(
                """
                UPDATE runtime_state
                SET prompt_tokens = ?, completion_tokens = ?, cached_tokens = ?,
                    total_runs = total_runs + 1, last_session_key = ?, updated_at = ?
                WHERE id = 1
                """,
                (prompt, completion, cached, session_key, time.time()),
            )

    def runtime_state(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runtime_state WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def bricks(self, *, scope: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM ui_bricks WHERE enabled = 1"
        params: list[Any] = []
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY position ASC, id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        bricks: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            item["config"] = json.loads(item.pop("config_json") or "{}")
            bricks.append(item)
        return bricks

    def pages(self, *, scope: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM ui_pages WHERE enabled = 1"
        params: list[Any] = []
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY position ASC, id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        pages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            pages.append(item)
        return pages

    def manifest(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT manifest_json FROM ui_manifest WHERE id = 1").fetchone()
        if not row:
            return dict(_DEFAULT_MANIFEST)
        try:
            return json.loads(row["manifest_json"] or "{}")
        except json.JSONDecodeError:
            return dict(_DEFAULT_MANIFEST)

    def update_manifest(self, manifest: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ui_manifest (id, manifest_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET manifest_json = excluded.manifest_json, updated_at = excluded.updated_at
                """,
                (json.dumps(manifest), time.time()),
            )

    def token_history(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT recorded_at, session_key, prompt_tokens, completion_tokens, cached_tokens, total_tokens
                FROM token_samples
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]
