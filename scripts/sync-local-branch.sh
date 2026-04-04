#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-upstream}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-main}"
BASE_BRANCH="${BASE_BRANCH:-main}"
LOCAL_BRANCH="${LOCAL_BRANCH:-nanobot-local}"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Worktree is dirty. Commit or stash changes before syncing." >&2
  exit 1
fi

git config rerere.enabled true
git fetch "${UPSTREAM_REMOTE}" --prune

git switch "${BASE_BRANCH}"
git merge --ff-only "${UPSTREAM_REMOTE}/${UPSTREAM_BRANCH}"

if git show-ref --verify --quiet "refs/heads/${LOCAL_BRANCH}"; then
  git switch "${LOCAL_BRANCH}"
  git rebase "${BASE_BRANCH}"
else
  git switch -c "${LOCAL_BRANCH}"
fi

echo "Synced ${BASE_BRANCH} with ${UPSTREAM_REMOTE}/${UPSTREAM_BRANCH} and rebased ${LOCAL_BRANCH}."
