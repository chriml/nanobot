"""aiohttp routes for the local/global bot admin UI."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

from nanobot.admin.service import BotAdminService
from nanobot.utils.runtime import EMPTY_FINAL_RESPONSE_MESSAGE

_ADMIN_SERVICE_KEY = web.AppKey("admin_service", BotAdminService)
_ADMIN_UI_DIR_KEY = web.AppKey("admin_ui_dir", Path | None)
_ADMIN_AUTH_COOKIE = "nanobot_admin_auth"


def _admin_password() -> str:
    password = os.environ.get("NANOBOT_ADMIN_PASSWORD", "").strip()
    if password:
        return password
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "NANOBOT_ADMIN_PASSWORD":
                return value.strip().strip("\"'")
    return ""


def _auth_enabled() -> bool:
    return bool(_admin_password())


def _password_digest(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _is_authorized(request: web.Request) -> bool:
    password = _admin_password()
    if not password:
        return True
    cookie = request.cookies.get(_ADMIN_AUTH_COOKIE, "")
    expected = _password_digest(password)
    return bool(cookie) and hmac.compare_digest(cookie, expected)


def _unauthorized(request: web.Request) -> web.StreamResponse:
    path = request.path
    if path.startswith("/admin/api/"):
        return _json({"error": "Authentication required."}, status=401)
    raise web.HTTPFound("/admin/login")


def _require_authorized(request: web.Request) -> web.StreamResponse | None:
    if _is_authorized(request):
        return None
    return _unauthorized(request)


async def _handle_login_page(_request: web.Request) -> web.Response:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Nanobot Admin Login</title>
  <style>
    body { margin: 0; font-family: sans-serif; background: #f3efe4; color: #1f1a11; }
    main { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    form { width: min(420px, 100%); display: grid; gap: 12px; background: #fffaf1; padding: 24px; border-radius: 20px; border: 1px solid rgba(36,30,19,.12); }
    input, button { font: inherit; padding: 12px 14px; border-radius: 12px; }
    input { border: 1px solid rgba(36,30,19,.16); }
    button { border: 0; background: #1f1a11; color: #fffaf1; cursor: pointer; }
    p { margin: 0; color: #655a49; }
  </style>
</head>
<body>
  <main>
    <form id="login-form">
      <h1>Admin Login</h1>
      <p>Enter the admin password from <code>.env</code> to access the bot shell.</p>
      <input id="password" type="password" autocomplete="current-password" placeholder="Admin password" required />
      <button type="submit">Unlock admin</button>
      <p id="status">Ready.</p>
    </form>
  </main>
  <script>
    document.getElementById("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const password = document.getElementById("password").value;
      const status = document.getElementById("status");
      status.textContent = "Checking...";
      const response = await fetch("/admin/api/auth/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ password }),
      });
      const payload = await response.json();
      if (!response.ok) {
        status.textContent = payload.error || "Login failed.";
        return;
      }
      window.location.href = payload.redirect || "/admin";
    });
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def _handle_login(request: web.Request) -> web.Response:
    body = await request.json()
    password = str(body.get("password") or "")
    expected = _admin_password()
    if not expected:
        response = _json({"ok": True, "redirect": "/admin"})
        return response
    if not hmac.compare_digest(password, expected):
        return _json({"error": "Invalid password."}, status=401)
    response = _json({"ok": True, "redirect": "/admin"})
    response.set_cookie(
        _ADMIN_AUTH_COOKIE,
        _password_digest(expected),
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )
    return response


async def _handle_logout(_request: web.Request) -> web.Response:
    response = _json({"ok": True})
    response.del_cookie(_ADMIN_AUTH_COOKIE, path="/")
    return response


def _ui_dir() -> Path | None:
    candidates = [
        os.environ.get("NANOBOT_ADMIN_UI_DIR"),
        "/app/admin-ui",
        str(Path(__file__).resolve().parents[2] / "website" / "dist"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _json(data: Any, *, status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


async def _handle_overview(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    return _json(service.overview())


async def _handle_bots(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    return _json({"bots": service.overview()["bots"]})


async def _handle_bot_detail(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    detail = service.bot_detail(request.match_info["slug"])
    if detail is None:
        return _json({"error": "Bot not found"}, status=404)
    return _json(detail)


async def _handle_logs(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    logs = service.bot_logs(request.match_info["slug"], tail=int(request.query.get("tail", "200")))
    if logs is None:
        return _json({"error": "Bot not found"}, status=404)
    return _json(logs)


async def _handle_bot_ui(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    payload = service.bot_ui_status(request.match_info["slug"])
    if payload is None:
        return _json({"error": "Bot not found"}, status=404)
    return _json(payload)


async def _handle_create_bot(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    body = await request.json()
    try:
        result = service.create_bot(
            name=str(body["name"]).strip(),
            presets=list(body.get("presets") or []),
            image=body.get("image"),
            auto_start=bool(body.get("autoStart")),
            host_port=int(body["hostPort"]) if body.get("hostPort") else None,
        )
    except Exception as exc:
        return _json({"error": str(exc)}, status=400)
    return _json(result, status=201)


async def _handle_action(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    try:
        result = service.run_action(request.match_info["slug"], request.match_info["action"])
    except Exception as exc:
        return _json({"error": str(exc)}, status=400)
    return _json(result)


async def _handle_chat(request: web.Request) -> web.Response:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    body = await request.json()
    prompt = str(body.get("message") or "").strip()
    scope = str(body.get("scope") or "global").strip().lower()
    slug = str(body.get("slug") or service.bot_slug).strip()
    if not prompt:
        return _json({"error": "Message is required."}, status=400)
    if scope not in {"global", "bot"}:
        return _json({"error": "Unsupported chat scope."}, status=400)

    session_key = f"admin-ui:{scope}:{slug}"
    if scope == "bot" and slug != service.bot_slug:
        target = service.resolve_bot_record(slug)
        if target is None:
            return _json({"error": "Bot not found"}, status=404)
        host_port = int(target.get("hostPort", 0) or 0)
        if not host_port:
            return _json({"error": "Bot-specific chat requires a configured host port."}, status=400)
        try:
            async with ClientSession(timeout=ClientTimeout(total=120)) as session:
                async with session.post(
                    f"http://127.0.0.1:{host_port}/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "session_id": session_key,
                    },
                ) as response:
                    payload = await response.json()
        except Exception as exc:
            return _json({"error": f"Failed to reach bot runtime: {exc}"}, status=502)
        if response.status >= 400:
            error = payload.get("error", {})
            if isinstance(error, dict):
                message = error.get("message") or "Bot chat failed."
            else:
                message = str(error or "Bot chat failed.")
            return _json({"error": message}, status=response.status)
        choices = payload.get("choices") or []
        first = choices[0] if choices else {}
        message = first.get("message") or {}
        content = str(message.get("content") or EMPTY_FINAL_RESPONSE_MESSAGE)
        return _json(
            {
                "scope": scope,
                "slug": slug,
                "content": content,
                "sessionKey": session_key,
                "proxied": True,
            }
        )

    loop = service.loop
    if loop is None:
        return _json({"error": "Chat is not available for this runtime."}, status=503)

    response = await loop.process_direct(
        content=prompt,
        session_key=session_key,
        channel="admin_ui",
        chat_id=scope if scope == "global" else slug,
    )
    content = getattr(response, "content", "") if response is not None else ""
    return _json(
        {
            "scope": scope,
            "slug": slug,
            "content": content or EMPTY_FINAL_RESPONSE_MESSAGE,
            "sessionKey": session_key,
        }
    )


async def _serve_custom_bot_asset(request: web.Request) -> web.StreamResponse:
    if unauthorized := _require_authorized(request):
        return unauthorized
    service = request.app[_ADMIN_SERVICE_KEY]
    slug = request.match_info["slug"]
    ui_dir = service.custom_ui_dir(slug)
    if ui_dir is None:
        raise web.HTTPNotFound()

    tail = request.match_info.get("tail", "").strip("/")
    relative = Path(tail or "entry.js")
    candidate = (ui_dir / relative).resolve(strict=False)
    try:
        candidate.relative_to(ui_dir.resolve(strict=False))
    except ValueError as exc:
        raise web.HTTPForbidden(text="Invalid custom UI path.") from exc

    if candidate.is_file():
        return web.FileResponse(candidate)
    raise web.HTTPNotFound()


async def _serve_admin_asset(request: web.Request) -> web.StreamResponse:
    if unauthorized := _require_authorized(request):
        return unauthorized
    ui_dir = request.app.get(_ADMIN_UI_DIR_KEY) or _ui_dir()
    if ui_dir is not None and request.app.get(_ADMIN_UI_DIR_KEY) is None:
        request.app[_ADMIN_UI_DIR_KEY] = ui_dir
    if ui_dir is None:
        return web.Response(
            text="Admin UI assets are not built yet. Run the Astro build or use a container image that bundles /app/admin-ui.",
            status=503,
            content_type="text/plain",
        )

    tail = request.match_info.get("tail", "").strip("/")
    if not tail:
        tail = "index.html"
    candidate = ui_dir / tail
    if candidate.is_file():
        return web.FileResponse(candidate)

    if tail.startswith("assets/"):
        raise web.HTTPNotFound()

    bot_page = ui_dir / "bot" / "index.html"
    if tail.startswith("bot") and bot_page.exists():
        return web.FileResponse(bot_page)
    return web.FileResponse(ui_dir / "index.html")


def mount_admin_routes(app: web.Application, service: BotAdminService) -> web.Application:
    """Attach admin API routes and UI serving to an aiohttp app."""
    app[_ADMIN_SERVICE_KEY] = service
    app[_ADMIN_UI_DIR_KEY] = _ui_dir()
    app.router.add_get("/admin/login", _handle_login_page)
    app.router.add_post("/admin/api/auth/login", _handle_login)
    app.router.add_post("/admin/api/auth/logout", _handle_logout)
    app.router.add_get("/admin/api/overview", _handle_overview)
    app.router.add_get("/admin/api/bots", _handle_bots)
    app.router.add_get("/admin/api/bots/{slug}", _handle_bot_detail)
    app.router.add_get("/admin/api/bots/{slug}/ui", _handle_bot_ui)
    app.router.add_get("/admin/api/bots/{slug}/logs", _handle_logs)
    app.router.add_post("/admin/api/bots", _handle_create_bot)
    app.router.add_post("/admin/api/bots/{slug}/actions/{action}", _handle_action)
    app.router.add_post("/admin/api/chat", _handle_chat)
    app.router.add_get("/admin/custom/{slug}", _serve_custom_bot_asset)
    app.router.add_get("/admin/custom/{slug}/", _serve_custom_bot_asset)
    app.router.add_get("/admin/custom/{slug}/{tail:.*}", _serve_custom_bot_asset)
    app.router.add_get("/admin", _serve_admin_asset)
    app.router.add_get("/admin/", _serve_admin_asset)
    app.router.add_get("/admin/{tail:.*}", _serve_admin_asset)
    return app


async def _handle_admin_health(_request: web.Request) -> web.Response:
    return _json({"status": "ok"})


def create_admin_app(service: BotAdminService) -> web.Application:
    """Create a standalone admin-only aiohttp application."""
    app = web.Application()
    app.router.add_get("/health", _handle_admin_health)
    return mount_admin_routes(app, service)
