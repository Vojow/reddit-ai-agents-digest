#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${REPO_ROOT}/.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Environment file not found: ${ENV_FILE}" >&2
  exit 1
fi

cd "${REPO_ROOT}"

set -a
source "${ENV_FILE}"
set +a

if [[ -z "${UV_CACHE_DIR:-}" ]]; then
  export UV_CACHE_DIR="${REPO_ROOT}/.cache/uv"
fi
mkdir -p "${UV_CACHE_DIR}"

if [[ -z "${UV_PYTHON:-}" ]] && command -v python3.12 >/dev/null 2>&1; then
  export UV_PYTHON="$(command -v python3.12)"
fi

exec make run-markdown
