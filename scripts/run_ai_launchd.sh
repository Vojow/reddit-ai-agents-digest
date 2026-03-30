#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export GIT_TERMINAL_PROMPT=0

notify_failure() {
  local message="$1"
  osascript -e "display notification \"${message}\" with title \"reddit-ai-agents-digest\"" >/dev/null 2>&1 || true
}

fail() {
  local reason="$1"
  printf "RUN_AI_LAUNCHD FAIL: %s\n" "${reason}"
  notify_failure "${reason}"
  exit 1
}

printf "RUN_AI_LAUNCHD START: repo=%s\n" "${REPO_ROOT}"

if ! branch="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null)"; then
  fail "unable to determine current branch"
fi
if [[ "${branch}" != "main" ]]; then
  fail "expected main branch, got ${branch}"
fi

if [[ -n "$(git -C "${REPO_ROOT}" status --porcelain)" ]]; then
  fail "worktree is dirty"
fi

if ! git -C "${REPO_ROOT}" fetch origin main; then
  fail "git fetch origin main failed"
fi
if ! git -C "${REPO_ROOT}" pull --ff-only origin main; then
  fail "git pull --ff-only origin main failed"
fi
if ! make -C "${REPO_ROOT}" run-ai; then
  fail "make run-ai failed"
fi

printf "RUN_AI_LAUNCHD OK: make run-ai completed\n"
