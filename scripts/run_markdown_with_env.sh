#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREFLIGHT_ONLY="false"

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

resolve_env_file() {
  local requested="${1:-}"
  local primary_root

  if [[ -n "${requested}" ]]; then
    if [[ -f "${requested}" ]]; then
      printf '%s\n' "${requested}"
      return 0
    fi

    echo "Environment file not found: ${requested}" >&2
    return 1
  fi

  if [[ -f "${REPO_ROOT}/.env" ]]; then
    printf '%s\n' "${REPO_ROOT}/.env"
    return 0
  fi

  primary_root="$(resolve_primary_worktree_root || true)"
  if [[ -n "${primary_root}" && "${primary_root}" != "${REPO_ROOT}" && -f "${primary_root}/.env" ]]; then
    printf '%s\n' "${primary_root}/.env"
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

  echo "uv executable not found. Install uv or add it to PATH." >&2
  return 1
}

ENV_FILE=""
FORWARD_ARGS=()
while (($#)); do
  case "${1}" in
    --preflight-only)
      PREFLIGHT_ONLY="true"
      shift
      ;;
    --env-file)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --env-file" >&2
        exit 1
      fi
      ENV_FILE="${2}"
      shift 2
      ;;
    *.env|/*|./*|../*)
      if [[ -z "${ENV_FILE}" ]]; then
        ENV_FILE="${1}"
      else
        FORWARD_ARGS+=("${1}")
      fi
      shift
      ;;
    *)
      FORWARD_ARGS+=("${1}")
      shift
      ;;
  esac
done

if ENV_FILE="$(resolve_env_file "${ENV_FILE}")"; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

UV_BIN="$(resolve_uv_bin)"
export PATH="$(dirname "${UV_BIN}"):${PATH}"

cd "${REPO_ROOT}"

if [[ -z "${UV_CACHE_DIR:-}" ]]; then
  export UV_CACHE_DIR="${REPO_ROOT}/.cache/uv"
fi
mkdir -p "${UV_CACHE_DIR}"

if [[ -z "${UV_PYTHON:-}" ]] && command -v python3.12 >/dev/null 2>&1; then
  export UV_PYTHON="$(command -v python3.12)"
fi

"${UV_BIN}" run reddit-digest preflight --base-path "${REPO_ROOT}" --skip-sheets --markdown-only

if [[ "${PREFLIGHT_ONLY}" == "true" ]]; then
  exit 0
fi

exec "${UV_BIN}" run reddit-digest run-daily --base-path "${REPO_ROOT}" --skip-sheets --markdown-only "${FORWARD_ARGS[@]}"
