#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

fail() {
  local message="${1}"
  echo "CODEX_ENV_SETUP FAIL: ${message}"
  exit 1
}

resolve_primary_worktree_root() {
  local line

  while IFS= read -r line; do
    if [[ "${line}" == worktree\ * ]]; then
      printf '%s\n' "${line#worktree }"
      return 0
    fi
  done < <(git -C "${REPO_ROOT}" worktree list --porcelain 2>/dev/null || true)

  return 1
}

resolve_primary_env_file() {
  local primary_root

  primary_root="$(resolve_primary_worktree_root || true)"
  if [[ -n "${primary_root}" && "${primary_root}" != "${REPO_ROOT}" && -f "${primary_root}/.env" ]]; then
    printf '%s\n' "${primary_root}/.env"
    return 0
  fi

  return 1
}

seed_worktree_env_file() {
  local primary_env

  if [[ -f "${REPO_ROOT}/.env" ]]; then
    printf '%s\n' "${REPO_ROOT}/.env"
    return 0
  fi

  primary_env="$(resolve_primary_env_file || true)"
  if [[ -n "${primary_env}" ]]; then
    cp "${primary_env}" "${REPO_ROOT}/.env"
    printf '%s\n' "${REPO_ROOT}/.env"
    return 0
  fi

  return 1
}

resolve_uv_bin() {
  local candidate
  local -a candidates=(
    "${HOME}/.local/bin/uv"
    "${HOME}/.cargo/bin/uv"
    "/opt/homebrew/bin/uv"
    "/usr/local/bin/uv"
  )

  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

echo "CODEX_ENV_SETUP START: repo=${REPO_ROOT}"

ENV_SOURCE="none"
if ENV_FILE="$(seed_worktree_env_file)"; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  ENV_SOURCE="${ENV_FILE}"
fi

UV_BIN="$(resolve_uv_bin || true)"
if [[ -z "${UV_BIN}" ]]; then
  fail "uv executable not found in PATH or standard install locations"
fi

export PATH="$(dirname "${UV_BIN}"):${PATH}"

if [[ -z "${UV_CACHE_DIR:-}" ]]; then
  export UV_CACHE_DIR="${REPO_ROOT}/.cache/uv"
fi

if [[ -z "${UV_PYTHON:-}" ]]; then
  if command -v python3.12 >/dev/null 2>&1; then
    export UV_PYTHON="$(command -v python3.12)"
  elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    export UV_PYTHON="${REPO_ROOT}/.venv/bin/python"
  fi
fi

if ! "${UV_BIN}" run reddit-digest preflight --base-path "${REPO_ROOT}" --skip-sheets --markdown-only; then
  fail "preflight command failed"
fi

echo "CODEX_ENV_SETUP OK: repo=${REPO_ROOT} env=${ENV_SOURCE} uv=${UV_BIN}"
