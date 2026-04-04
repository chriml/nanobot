#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

find_python_bin() {
  local candidate
  for candidate in \
    "$PYTHON_BIN" \
    /opt/homebrew/bin/python3 \
    /opt/homebrew/bin/python3.14 \
    python3.14 \
    python3 \
    python
  do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python_bin || true)"

if [ -z "${PYTHON_BIN:-}" ]; then
  echo "python executable not found" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "pip is not available for $PYTHON_BIN, attempting to bootstrap it with ensurepip"
  if ! "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1; then
    for fallback in /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.14 python3.14 python3 python; do
      if command -v "$fallback" >/dev/null 2>&1 && "$fallback" -m pip --version >/dev/null 2>&1; then
        PYTHON_BIN="$fallback"
        break
      fi
    done
    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
      echo "failed to bootstrap pip via ensurepip for $PYTHON_BIN" >&2
      echo "install pip or use a Python build that includes ensurepip, then rerun this script" >&2
      echo "tip: on this machine /opt/homebrew/bin/python3 looks like the right candidate" >&2
      exit 1
    fi
  fi
fi

echo "Using Python: $PYTHON_BIN"

if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.prefix != getattr(sys, "base_prefix", sys.prefix) else 1)
PY
then
  INSTALL_ARGS=(-e "$ROOT_DIR")
else
  INSTALL_ARGS=(--user --break-system-packages -e "$ROOT_DIR")
fi

echo "Installing nanobot from $ROOT_DIR"
"$PYTHON_BIN" -m pip install "${INSTALL_ARGS[@]}"

DOCKER_IMAGE="${NANOCHRIS_DOCKER_IMAGE:-nanochris:local}"
SEARXNG_IMAGE="${NANOCHRIS_SEARXNG_IMAGE:-docker.io/searxng/searxng:latest}"
if [ "${NANOCHRIS_SKIP_DOCKER_BUILD:-0}" != "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not available; skipping image build for $DOCKER_IMAGE" >&2
  else
    echo "Building Docker image: $DOCKER_IMAGE"
    docker build -t "$DOCKER_IMAGE" "$ROOT_DIR"
    echo "Pulling shared SearXNG image: $SEARXNG_IMAGE"
    docker pull "$SEARXNG_IMAGE"
  fi
fi

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
echo "Docker image:"
echo "  $DOCKER_IMAGE"
echo "Shared search image:"
echo "  $SEARXNG_IMAGE"
echo
echo "If your shell cannot find them yet, add this to your PATH:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
