"""Helpers for launching the Bitwarden MCP server with permanent access."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _run_command(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run a Bitwarden CLI command and capture output."""
    return subprocess.run(args, env=env, check=True, capture_output=True, text=True)


def _load_status(env: dict[str, str]) -> str | None:
    """Return Bitwarden CLI status if available."""
    try:
        result = _run_command(["bw", "status"], env)
    except Exception:
        return None

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    status = payload.get("status")
    return status if isinstance(status, str) else None


def ensure_session(env: dict[str, str] | None = None) -> dict[str, str]:
    """Ensure BW_SESSION is populated from permanent Bitwarden CLI credentials."""
    prepared = dict(env or os.environ)
    client_id = prepared.get("BW_CLIENTID")
    client_secret = prepared.get("BW_CLIENTSECRET")
    password_file = prepared.get("BW_PASSWORD_FILE")
    server_url = prepared.get("BW_SERVER_URL")
    if not server_url or not client_id or not client_secret or not password_file:
        raise RuntimeError(
            "BW_SERVER_URL, BW_CLIENTID, BW_CLIENTSECRET, and BW_PASSWORD_FILE are required "
            "for permanent Bitwarden access"
        )
    if server_url:
        _run_command(["bw", "config", "server", server_url], prepared)

    status = _load_status(prepared)
    if status == "unauthenticated":
        _run_command(["bw", "login", "--apikey"], prepared)

    result = _run_command(
        ["bw", "unlock", "--raw", "--passwordfile", password_file],
        prepared,
    )
    session = (result.stdout or "").strip()
    if session:
        prepared["BW_SESSION"] = session
    return prepared


def exec_mcp_server() -> int:
    """Exec the Bitwarden MCP server with the best available auth state."""
    env = ensure_session()
    os.execvpe("npx", ["npx", "-y", "@bitwarden/mcp-server"], env)
    return 0


def main() -> int:
    """CLI entrypoint for `nanobot bitwarden-mcp`."""
    try:
        return exec_mcp_server()
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(f"Bitwarden setup failed: {message}", file=sys.stderr)
        return exc.returncode or 1
    except FileNotFoundError as exc:
        print(f"Bitwarden setup failed: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
