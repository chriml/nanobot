#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "pip is not available for $PYTHON_BIN, attempting to bootstrap it with ensurepip"
  if ! "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1; then
    echo "failed to bootstrap pip via ensurepip for $PYTHON_BIN" >&2
    echo "install pip or use a Python build that includes ensurepip, then rerun this script" >&2
    exit 1
  fi
fi

if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.prefix != getattr(sys, "base_prefix", sys.prefix) else 1)
PY
then
  INSTALL_ARGS=(-e "$ROOT_DIR")
else
  INSTALL_ARGS=(--user -e "$ROOT_DIR")
fi

echo "Installing nanobot from $ROOT_DIR"
"$PYTHON_BIN" -m pip install "${INSTALL_ARGS[@]}"

BIN_DIR="$("$PYTHON_BIN" - <<'PY'
import site
import sys
from pathlib import Path

in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
if in_venv:
    print(Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin"))
else:
    print(Path(site.USER_BASE) / ("Scripts" if sys.platform == "win32" else "bin"))
PY
)"

echo
echo "Installed commands:"
echo "  nanobot"
echo "  nanochris"
echo "  nanchris"
echo
echo "If your shell cannot find them yet, add this to your PATH:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
