import subprocess

import pytest

from nanobot.integrations.bitwarden_mcp import ensure_session


def test_ensure_session_requires_permanent_credentials():
    with pytest.raises(RuntimeError, match="BW_CLIENTID, BW_CLIENTSECRET, and BW_PASSWORD_FILE"):
        ensure_session({})


def test_ensure_session_logs_in_and_unlocks_with_cli_credentials(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["bw", "status"]:
            return subprocess.CompletedProcess(args, 0, '{"status":"unauthenticated"}', "")
        if args == ["bw", "login", "--apikey"]:
            assert env["BW_CLIENTID"] == "client-id"
            assert env["BW_CLIENTSECRET"] == "client-secret"
            return subprocess.CompletedProcess(args, 0, "", "")
        if args == ["bw", "unlock", "--raw", "--passwordfile", "/tmp/bw-pass"]:
            return subprocess.CompletedProcess(args, 0, "session-from-unlock\n", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr("nanobot.integrations.bitwarden_mcp._run_command", fake_run_command)

    result = ensure_session(
        {
            "BW_CLIENTID": "client-id",
            "BW_CLIENTSECRET": "client-secret",
            "BW_PASSWORD_FILE": "/tmp/bw-pass",
        }
    )

    assert result["BW_SESSION"] == "session-from-unlock"
    assert calls == [
        ["bw", "status"],
        ["bw", "login", "--apikey"],
        ["bw", "unlock", "--raw", "--passwordfile", "/tmp/bw-pass"],
    ]


def test_ensure_session_supports_password_file(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["bw", "status"]:
            return subprocess.CompletedProcess(args, 0, '{"status":"locked"}', "")
        if args == ["bw", "unlock", "--raw", "--passwordfile", "/tmp/bw-pass"]:
            return subprocess.CompletedProcess(args, 0, "session-from-file\n", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr("nanobot.integrations.bitwarden_mcp._run_command", fake_run_command)

    result = ensure_session(
        {
            "BW_CLIENTID": "client-id",
            "BW_CLIENTSECRET": "client-secret",
            "BW_PASSWORD_FILE": "/tmp/bw-pass",
        }
    )

    assert result["BW_SESSION"] == "session-from-file"
    assert calls == [
        ["bw", "status"],
        ["bw", "unlock", "--raw", "--passwordfile", "/tmp/bw-pass"],
    ]
