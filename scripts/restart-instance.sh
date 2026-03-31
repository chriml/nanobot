#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOT_NAME="${1:-Chris}"

cd "$ROOT_DIR"

git pull --ff-only
"$ROOT_DIR"/scripts/install-local.sh
nanochris manage "$BOT_NAME" stop
nanochris manage "$BOT_NAME" start
