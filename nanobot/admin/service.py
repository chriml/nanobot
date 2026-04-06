"""Admin discovery and orchestration service for bot dashboards."""

from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from nanobot.admin.db import (
    BotAdminStore,
    admin_db_path,
    bot_ui_dist_dir,
    bot_ui_meta_path,
    bot_ui_src_dir,
)
from nanobot.config.loader import save_config
from nanobot.config.paths import slugify_agent_name
from nanobot.config.presets import apply_presets
from nanobot.config.schema import Config
from nanobot.instances import (
    build_docker_instance_command,
    build_docker_remove_command,
    get_instance_container_name,
    get_instance_image,
    list_instances,
    resolve_instance_paths,
)
from nanobot.utils.helpers import sync_workspace_templates


class BotAdminService:
    """Expose self/global bot admin data using per-bot SQLite state."""

    def __init__(
        self,
        *,
        workspace: Path,
        bot_name: str,
        model: str,
        mode: str,
        config_path: Path | None = None,
        instances_dir: Path | None = None,
        image: str | None = None,
        loop: Any | None = None,
    ):
        self.workspace = workspace
        self.bot_name = bot_name
        self.bot_slug = slugify_agent_name(bot_name)
        self.model = model
        self.mode = mode
        self.config_path = config_path
        self.instances_dir = instances_dir
        self.image = image
        self.loop = loop
        self.store = BotAdminStore(admin_db_path(workspace))
        self.store.bootstrap(
            bot_name=bot_name,
            bot_slug=self.bot_slug,
            model=model,
            mode=mode,
            workspace_path=workspace,
            config_path=config_path,
            host_port=None,
            status="running",
        )

    def _docker_available(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{json .Server.Version}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            return False
        return result.returncode == 0

    def _docker_state(self, container_name: str) -> dict[str, Any]:
        if not self._docker_available():
            return {"available": False, "status": "unknown", "running": False}
        result = subprocess.run(
            [
                "docker",
                "inspect",
                container_name,
                "--format",
                "{{json .State}}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            return {"available": True, "status": "missing", "running": False}
        try:
            state = json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return {"available": True, "status": "unknown", "running": False}
        return {
            "available": True,
            "status": state.get("Status") or "unknown",
            "running": bool(state.get("Running")),
            "startedAt": state.get("StartedAt"),
            "finishedAt": state.get("FinishedAt"),
            "exitCode": state.get("ExitCode"),
            "health": (state.get("Health") or {}).get("Status"),
        }

    def _docker_logs(self, container_name: str, *, tail: int = 200) -> str:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(max(1, tail)), container_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return result.stderr.strip() or f"Container '{container_name}' is not available."
        return (result.stdout or result.stderr).strip()

    @staticmethod
    def _read_ui_meta(workspace_path: Path) -> dict[str, Any]:
        dist_dir = bot_ui_dist_dir(workspace_path)
        src_dir = bot_ui_src_dir(workspace_path)
        meta_path = bot_ui_meta_path(workspace_path)
        payload: dict[str, Any] = {}
        if meta_path.is_file():
            try:
                raw = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    payload = raw
            except Exception:
                payload = {}

        entry = str(payload.get("entry") or "entry.js")
        css = str(payload.get("css") or "")
        entry_path = dist_dir / entry
        css_path = dist_dir / css if css else None
        version = str(payload.get("version") or "")
        if not version and entry_path.is_file():
            version = str(entry_path.stat().st_mtime_ns)
        updated_at = float(payload.get("updatedAt") or 0)
        if not updated_at and entry_path.is_file():
            updated_at = entry_path.stat().st_mtime

        return {
            "sourceDir": str(src_dir),
            "distDir": str(dist_dir),
            "metaPath": str(meta_path),
            "entry": entry,
            "entryExists": entry_path.is_file(),
            "css": css,
            "cssExists": bool(css_path and css_path.is_file()),
            "version": version or "0",
            "updatedAt": updated_at,
            "status": str(payload.get("status") or ("ready" if entry_path.is_file() else "missing")),
            "error": str(payload.get("error") or ""),
        }

    def _instance_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if self.instances_dir and self.instances_dir.exists():
            instances = list_instances(base_dir=self.instances_dir)
        else:
            instances = []

        seen = set()
        for instance in instances:
            db_path = admin_db_path(instance.workspace_path)
            store = BotAdminStore(db_path) if db_path.exists() else None
            runtime = store.runtime_state() if store else {}
            slug = instance.slug
            records.append(
                self._bot_record(
                    name=runtime.get("bot_name") or instance.name,
                    slug=slug,
                    workspace_path=instance.workspace_path,
                    config_path=instance.config_path,
                    model=runtime.get("model") or "",
                    mode=runtime.get("mode") or "gateway",
                    runtime=runtime,
                    store=store,
                    container_name=get_instance_container_name(instance),
                )
            )
            seen.add(slug)

        if self.bot_slug not in seen:
            records.append(self._self_record())

        records.sort(key=lambda item: (item["name"].lower(), item["slug"]))
        return records

    def _live_runtime(self) -> dict[str, Any]:
        if self.loop is None:
            return {}
        last_usage = getattr(self.loop, "_last_usage", {}) or {}
        active_tasks = getattr(self.loop, "_active_tasks", {}) or {}
        subagents = getattr(self.loop, "subagents", None)
        return {
            "prompt_tokens": int(last_usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(last_usage.get("completion_tokens", 0) or 0),
            "cached_tokens": int(last_usage.get("cached_tokens", 0) or 0),
            "started_at": getattr(self.loop, "_start_time", time.time()),
            "updated_at": time.time(),
            "status": "running",
            "active_tasks": sum(1 for tasks in active_tasks.values() for task in tasks if not task.done()),
            "subagents": subagents.get_running_count() if hasattr(subagents, "get_running_count") else 0,
        }

    def _bot_record(
        self,
        *,
        name: str,
        slug: str,
        workspace_path: Path,
        config_path: Path | None,
        model: str,
        mode: str,
        runtime: dict[str, Any],
        store: BotAdminStore | None,
        container_name: str,
    ) -> dict[str, Any]:
        docker = self._docker_state(container_name)
        prompt = int(runtime.get("prompt_tokens", 0) or 0)
        completion = int(runtime.get("completion_tokens", 0) or 0)
        cached = int(runtime.get("cached_tokens", 0) or 0)
        runtime_status = runtime.get("status") or "unknown"
        docker_status = docker.get("status") or "unknown"
        resolved_status = runtime_status if docker_status in {"unknown", "missing"} else docker_status
        resolved_running = bool(docker.get("running")) or runtime_status == "running"
        ui_meta = self._read_ui_meta(workspace_path)
        return {
            "name": name,
            "slug": slug,
            "model": model,
            "mode": mode,
            "workspacePath": str(workspace_path),
            "configPath": str(config_path) if config_path else "",
            "databasePath": str(store.db_path) if store else str(admin_db_path(workspace_path)),
            "containerName": container_name,
            "host": socket.gethostname(),
            "hostPort": int(runtime.get("host_port", 0) or 0),
            "status": resolved_status,
            "running": resolved_running,
            "docker": docker,
            "lastUsage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "cached_tokens": cached,
                "total_tokens": prompt + completion,
            },
            "updatedAt": runtime.get("updated_at", 0),
            "startedAt": runtime.get("started_at", 0),
            "totalRuns": int(runtime.get("total_runs", 0) or 0),
            "lastError": runtime.get("last_error") or "",
            "activeTasks": int(runtime.get("active_tasks", 0) or 0),
            "subagents": int(runtime.get("subagents", 0) or 0),
            "customUi": {
                "sourceDir": ui_meta["sourceDir"],
                "distDir": ui_meta["distDir"],
                "metaPath": ui_meta["metaPath"],
                "entry": ui_meta["entry"],
                "entryPath": str(Path(ui_meta["distDir"]) / ui_meta["entry"]),
                "exists": bool(ui_meta["entryExists"]),
                "css": ui_meta["css"],
                "cssExists": bool(ui_meta["cssExists"]),
                "version": ui_meta["version"],
                "updatedAt": ui_meta["updatedAt"],
                "status": ui_meta["status"],
                "error": ui_meta["error"],
                "route": f"/admin/custom/{slug}/",
                "apiRoute": f"/admin/api/bots/{slug}/ui",
            },
        }

    def _self_record(self) -> dict[str, Any]:
        runtime = self.store.runtime_state()
        live = self._live_runtime()
        runtime = {**runtime, **{k: v for k, v in live.items() if v not in (None, "")}}
        return self._bot_record(
            name=self.bot_name,
            slug=self.bot_slug,
            workspace_path=self.workspace,
            config_path=self.config_path,
            model=runtime.get("model") or self.model,
            mode=runtime.get("mode") or self.mode,
            runtime=runtime,
            store=self.store,
            container_name=socket.gethostname(),
        )

    def _brick_payload(self, kind: str, bot: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        if kind == "status":
            return {
                "status": bot["status"],
                "running": bot["running"],
                "mode": bot["mode"],
                "model": bot["model"],
                "containerName": bot["containerName"],
                "startedAt": bot["startedAt"],
                "updatedAt": bot["updatedAt"],
                "activeTasks": bot.get("activeTasks", 0),
                "subagents": bot.get("subagents", 0),
                "lastError": bot["lastError"],
            }
        if kind == "tokens":
            return {
                "latest": bot["lastUsage"],
                "history": history,
                "totalRuns": bot["totalRuns"],
            }
        if kind == "workspace":
            return {
                "workspacePath": bot["workspacePath"],
                "configPath": bot["configPath"],
                "databasePath": bot["databasePath"],
                "host": bot["host"],
            }
        if kind == "overview":
            return {
                "name": bot["name"],
                "slug": bot["slug"],
                "status": bot["status"],
                "running": bot["running"],
                "mode": bot["mode"],
                "model": bot["model"],
                "lastUsage": bot["lastUsage"],
            }
        return {}

    @staticmethod
    def _slugify_section(value: str) -> str:
        return value.strip().lower().replace(" ", "-") if value.strip() else "section"

    def _resolve_sections(
        self,
        layout_spec: dict[str, Any],
        *,
        bricks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        brick_map = {brick["id"]: brick for brick in bricks}
        sections: list[dict[str, Any]] = []
        for raw_name, raw_ids in layout_spec.items():
            ids = [item for item in list(raw_ids or []) if item in brick_map]
            sections.append(
                {
                    "id": self._slugify_section(str(raw_name)),
                    "title": str(raw_name).replace("-", " ").title(),
                    "bricks": [brick_map[item] for item in ids],
                }
            )
        return sections

    def _ui_spec(
        self,
        *,
        store: BotAdminStore,
        bot: dict[str, Any],
        bot_bricks: list[dict[str, Any]],
        global_bricks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        manifest = store.manifest()
        global_pages = store.pages(scope="global")
        bot_pages = store.pages(scope="bot")
        return {
            "manifest": manifest,
            "pages": {
                "global": global_pages,
                "bot": bot_pages,
            },
            "layouts": {
                "global": self._resolve_sections(manifest.get("globalLayout") or {}, bricks=global_bricks),
                "bot": self._resolve_sections(manifest.get("botLayout") or {}, bricks=bot_bricks),
            },
            "links": {
                "self": f"/admin/bot/{bot['slug']}",
                "fleet": "/admin",
                "customUi": bot["customUi"]["route"],
            },
        }

    def resolve_bot_record(self, slug: str) -> dict[str, Any] | None:
        for bot in self._instance_records():
            if bot["slug"] == slug:
                return bot
        return None

    def custom_ui_dir(self, slug: str) -> Path | None:
        bot = self.resolve_bot_record(slug)
        if bot is None:
            return None
        return Path(bot["customUi"]["distDir"])

    def bot_ui_status(self, slug: str) -> dict[str, Any] | None:
        bot = self.resolve_bot_record(slug)
        if bot is None:
            return None
        custom_ui = dict(bot["customUi"])
        custom_ui["entryUrl"] = f"{custom_ui['route']}{custom_ui['entry']}"
        custom_ui["cssUrl"] = (
            f"{custom_ui['route']}{custom_ui['css']}" if custom_ui.get("css") and custom_ui.get("cssExists") else ""
        )
        return {
            "slug": slug,
            "ui": custom_ui,
        }

    def _bot_detail(self, record: dict[str, Any]) -> dict[str, Any]:
        store = BotAdminStore(Path(record["databasePath"]))
        history = store.token_history()
        bot_bricks = []
        for brick in store.bricks(scope="bot"):
            bot_bricks.append({**brick, "payload": self._brick_payload(brick["kind"], record, history)})
        global_bricks = []
        for brick in store.bricks(scope="global"):
            global_bricks.append({**brick, "payload": self._brick_payload(brick["kind"], record, history)})
        return {
            "bot": record,
            "botBricks": bot_bricks,
            "globalBricks": global_bricks,
            "tokenHistory": history,
            "ui": self._ui_spec(
                store=store,
                bot=record,
                bot_bricks=bot_bricks,
                global_bricks=global_bricks,
            ),
        }

    def overview(self) -> dict[str, Any]:
        bots = self._instance_records()
        running = sum(1 for bot in bots if bot["running"])
        return {
            "self": self._self_record(),
            "bots": bots,
            "summary": {
                "totalBots": len(bots),
                "runningBots": running,
                "stoppedBots": len(bots) - running,
                "dockerAvailable": self._docker_available(),
                "globalAvailable": len(bots) > 1,
            },
        }

    def bot_detail(self, slug: str) -> dict[str, Any] | None:
        for bot in self._instance_records():
            if bot["slug"] == slug:
                return self._bot_detail(bot)
        return None

    def bot_logs(self, slug: str, *, tail: int = 200) -> dict[str, Any] | None:
        detail = self.bot_detail(slug)
        if not detail:
            return None
        container_name = detail["bot"]["containerName"]
        return {"slug": slug, "logs": self._docker_logs(container_name, tail=tail)}

    def create_bot(
        self,
        *,
        name: str,
        presets: list[str] | None = None,
        image: str | None = None,
        auto_start: bool = False,
        host_port: int | None = None,
    ) -> dict[str, Any]:
        if not self.instances_dir:
            raise ValueError("Global bot creation requires an instances directory.")
        instance = resolve_instance_paths(name, base_dir=self.instances_dir)
        config = Config()
        config.agents.defaults.name = name
        config.agents.defaults.workspace = str(instance.workspace_path)
        save_config(config, instance.config_path)
        if presets:
            apply_presets(instance.config_path, presets)
        sync_workspace_templates(instance.workspace_path)
        store = BotAdminStore(admin_db_path(instance.workspace_path))
        store.bootstrap(
            bot_name=name,
            bot_slug=instance.slug,
            model=config.agents.defaults.model,
            mode="gateway",
            workspace_path=instance.workspace_path,
            config_path=instance.config_path,
            host_port=host_port,
            status="created",
        )
        result = {
            "name": name,
            "slug": instance.slug,
            "configPath": str(instance.config_path),
            "workspacePath": str(instance.workspace_path),
            "hostPort": host_port,
        }
        if auto_start:
            command = build_docker_instance_command(
                instance,
                image=image,
                interactive=False,
                remove=False,
                detached=True,
                host_port=host_port,
                nanobot_args=["gateway", "--config", "/root/.nanobot/config.json", "--workspace", "/root/.nanobot/workspace"],
            )
            proc = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
            result["start"] = {
                "ok": proc.returncode == 0,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "image": get_instance_image(image),
            }
            result["started"] = proc.returncode == 0
        return result

    def run_action(self, slug: str, action: str) -> dict[str, Any]:
        if not self.instances_dir:
            raise ValueError("Container actions require an instances directory.")
        instance = resolve_instance_paths(slug, base_dir=self.instances_dir)
        store = BotAdminStore(admin_db_path(instance.workspace_path))
        runtime = store.runtime_state()
        host_port = int(runtime.get("host_port", 0) or 0) or None
        if action == "stop":
            command = build_docker_remove_command(instance)
        elif action == "start":
            command = build_docker_instance_command(
                instance,
                image=self.image,
                interactive=False,
                remove=False,
                detached=True,
                host_port=host_port,
                nanobot_args=["gateway", "--config", "/root/.nanobot/config.json", "--workspace", "/root/.nanobot/workspace"],
            )
        elif action == "restart":
            self.run_action(slug, "stop")
            return self.run_action(slug, "start")
        else:
            raise ValueError(f"Unsupported action: {action}")
        proc = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "action": action,
            "slug": slug,
        }
