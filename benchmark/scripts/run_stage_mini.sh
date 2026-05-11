#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

usage() {
  cat <<'EOF'
Usage:
  run_stage_mini.sh [STAGE_WORKSPACE]

Runs the mini-SWE-agent benchmark image against a stage-local workspace.
If STAGE_WORKSPACE is omitted, the current working directory is used.

Expected workspace layout:
  repo/
  task/prompt.md

Environment:
  OPENAI_API_KEY / OPENROUTER_API_KEY / DEEPSEEK_API_KEY
                                         API key for the selected backend
  MSWEA_MODEL_NAME                       Optional, defaults to google/gemma-4-26b-a4b-it:free
  OPENAI_API_BASE                        Optional, defaults to https://openrouter.ai/api/v1
  MSWEA_MODEL_BACKEND                    Optional, auto-detects openrouter vs openai-compat
  CONTAINER_RUNTIME                      Optional, defaults to docker
  MINI_IMAGE                             Optional, defaults to csc6052-mini-swe-agent
EOF
}

fail() {
  printf '%s\n' "$*" >&2
  exit 2
}

resolve_proxy_value() {
  local primary_lower="$1"
  local primary_upper="$2"
  local fallback_lower="$3"
  local fallback_upper="$4"

  if [[ -n "${!primary_lower:-}" ]]; then
    printf '%s' "${!primary_lower}"
    return 0
  fi
  if [[ -n "${!primary_upper:-}" ]]; then
    printf '%s' "${!primary_upper}"
    return 0
  fi
  if [[ -n "${!fallback_lower:-}" ]]; then
    printf '%s' "${!fallback_lower}"
    return 0
  fi
  if [[ -n "${!fallback_upper:-}" ]]; then
    printf '%s' "${!fallback_upper}"
    return 0
  fi
  return 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

WORKSPACE_ROOT=${1:-$PWD}
WORKSPACE_ROOT=$(cd -- "${WORKSPACE_ROOT}" && pwd)

if [[ "${WORKSPACE_ROOT}" == "${REPO_ROOT}" ]]; then
  fail "refusing to mount the benchmark repository root; cd into a stage workspace or pass its path explicitly"
fi

if [[ ! -d "${WORKSPACE_ROOT}/repo" ]]; then
  fail "expected ${WORKSPACE_ROOT}/repo to exist"
fi

if [[ ! -f "${WORKSPACE_ROOT}/task/prompt.md" ]]; then
  fail "expected ${WORKSPACE_ROOT}/task/prompt.md to exist"
fi

API_KEY=${OPENAI_API_KEY:-${OPENROUTER_API_KEY:-${DEEPSEEK_API_KEY:-}}}
if [[ -z "${API_KEY}" ]]; then
  fail "set OPENAI_API_KEY, OPENROUTER_API_KEY, or DEEPSEEK_API_KEY before running mini"
fi

IMAGE=${MINI_IMAGE:-csc6052-mini-swe-agent}
if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
  RUNTIME=${CONTAINER_RUNTIME}
elif command -v docker >/dev/null 2>&1; then
  RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
else
  RUNTIME=docker
fi
MODEL=${MSWEA_MODEL_NAME:-google/gemma-4-26b-a4b-it:free}
BASE_URL=${OPENAI_API_BASE:-https://openrouter.ai/api/v1}
MODEL_BACKEND=${MSWEA_MODEL_BACKEND:-}
TASK_PROMPT="Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior."

RUNTIME_ARGS=(
  run
  --rm
  -it
  -v "${WORKSPACE_ROOT}:/workspace"
  -e "MSWEA_MODEL_NAME=${MODEL}"
  -e "OPENAI_API_KEY=${API_KEY}"
  -e "OPENAI_API_BASE=${BASE_URL}"
  -e "MSWEA_MODEL_BACKEND=${MODEL_BACKEND}"
)

if PROXY_VALUE=$(resolve_proxy_value http_proxy HTTP_PROXY https_proxy HTTPS_PROXY); then
  RUNTIME_ARGS+=(
    -e "http_proxy=${PROXY_VALUE}"
    -e "HTTP_PROXY=${PROXY_VALUE}"
    -e "https_proxy=${PROXY_VALUE}"
    -e "HTTPS_PROXY=${PROXY_VALUE}"
  )
fi

if NO_PROXY_VALUE=$(resolve_proxy_value no_proxy NO_PROXY no_proxy NO_PROXY); then
  RUNTIME_ARGS+=(
    -e "no_proxy=${NO_PROXY_VALUE}"
    -e "NO_PROXY=${NO_PROXY_VALUE}"
  )
fi

exec "${RUNTIME}" "${RUNTIME_ARGS[@]}" \
  "${IMAGE}" \
  mini -t "${TASK_PROMPT}"
