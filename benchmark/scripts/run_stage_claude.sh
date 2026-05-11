#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
. "${SCRIPT_DIR}/proxy-env.sh"

usage() {
  cat <<'EOF'
Usage:
  run_stage_claude.sh [STAGE_WORKSPACE]

Runs the Claude benchmark image against a stage-local workspace.
If STAGE_WORKSPACE is omitted, the current working directory is used.

Expected workspace layout:
  repo/
  task/prompt.md

Environment:
  CLAUDE_PROVIDER                        Optional: anthropic or deepseek
  CLAUDE_CODE_OAUTH_TOKEN                Required for Anthropic subscription mode
  DEEPSEEK_API_KEY / ANTHROPIC_AUTH_TOKEN Required for DeepSeek mode
  CLAUDE_IMAGE                           Optional, defaults to csc6052-claude
  CLAUDE_MODEL                           Optional, defaults to claude-sonnet-4-6 or deepseek-v4-pro[1m]
  CLAUDE_MAX_TURNS                       Optional, defaults to 120
  CLAUDE_TASK_PROMPT                     Optional override for the Claude prompt
  CONTAINER_RUNTIME                      Optional, defaults to docker
EOF
}

fail() {
  printf '%s\n' "$*" >&2
  exit 2
}

resolve_claude_provider() {
  local configured="${CLAUDE_PROVIDER:-${CLAUDE_CODE_PROVIDER:-}}"
  case "${configured}" in
    deepseek)
      printf '%s\n' "deepseek"
      return 0
      ;;
    anthropic|subscription)
      printf '%s\n' "anthropic"
      return 0
      ;;
    "")
      ;;
    *)
      fail "unsupported CLAUDE_PROVIDER='${configured}'; use anthropic or deepseek"
      ;;
  esac

  if [[ "${ANTHROPIC_BASE_URL:-}" == *"api.deepseek.com"* ]]; then
    printf '%s\n' "deepseek"
    return 0
  fi
  if [[ "${CLAUDE_MODEL:-${ANTHROPIC_MODEL:-}}" == deepseek* ]]; then
    printf '%s\n' "deepseek"
    return 0
  fi

  printf '%s\n' "anthropic"
}

configure_deepseek_claude_provider() {
  MODEL="${MODEL:-${ANTHROPIC_MODEL:-deepseek-v4-pro[1m]}}"
  export "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" && -n "${DEEPSEEK_API_KEY:-}" ]]; then
    export "ANTHROPIC_AUTH_TOKEN=${DEEPSEEK_API_KEY}"
  elif [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" && -n "${API_KEY:-}" ]]; then
    export "ANTHROPIC_AUTH_TOKEN=${API_KEY}"
  fi

  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
    fail "provide DEEPSEEK_API_KEY or ANTHROPIC_AUTH_TOKEN before running claude with DeepSeek"
  fi

  export "ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-${MODEL}}"
  export "ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL:-${MODEL}}"
  export "ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL:-${MODEL}}"
  export "ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL:-deepseek-v4-flash}"
  export "CLAUDE_CODE_SUBAGENT_MODEL=${CLAUDE_CODE_SUBAGENT_MODEL:-deepseek-v4-flash}"
  export "CLAUDE_CODE_EFFORT_LEVEL=${CLAUDE_CODE_EFFORT_LEVEL:-max}"
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

IMAGE=${CLAUDE_IMAGE:-csc6052-claude}
MODEL=${CLAUDE_MODEL:-}
CLAUDE_PROVIDER_VALUE=$(resolve_claude_provider)
case "${CLAUDE_PROVIDER_VALUE}" in
  deepseek)
    configure_deepseek_claude_provider
    ;;
  anthropic)
    MODEL=${MODEL:-claude-sonnet-4-6}
    if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
      fail "provide CLAUDE_CODE_OAUTH_TOKEN before running claude"
    fi
    ;;
esac
MAX_TURNS=${CLAUDE_MAX_TURNS:-120}
TASK_PROMPT=${CLAUDE_TASK_PROMPT:-Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.}
if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
  RUNTIME=${CONTAINER_RUNTIME}
elif command -v docker >/dev/null 2>&1; then
  RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
else
  RUNTIME=docker
fi

RUNTIME_ARGS=(
  run
  --rm
  -v "${WORKSPACE_ROOT}:/workspace"
  -e "CLAUDE_MODEL=${MODEL}"
  -e "CLAUDE_MAX_TURNS=${MAX_TURNS}"
)

if [[ "${CLAUDE_PROVIDER_VALUE}" != "deepseek" && -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  RUNTIME_ARGS+=(-e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}")
fi

if [[ "${CLAUDE_PROVIDER_VALUE}" == "deepseek" ]]; then
  RUNTIME_ARGS+=(
    -e "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}"
    -e ANTHROPIC_AUTH_TOKEN
    -e "ANTHROPIC_MODEL=${ANTHROPIC_MODEL}"
    -e "ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL}"
    -e "ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL}"
    -e "ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL}"
    -e "CLAUDE_CODE_SUBAGENT_MODEL=${CLAUDE_CODE_SUBAGENT_MODEL}"
    -e "CLAUDE_CODE_EFFORT_LEVEL=${CLAUDE_CODE_EFFORT_LEVEL}"
  )
else
  while IFS= read -r proxy_arg; do
    [[ -n "${proxy_arg}" ]] || continue
    RUNTIME_ARGS+=("${proxy_arg}")
  done < <(print_container_proxy_args "${RUNTIME}")
fi

exec "${RUNTIME}" "${RUNTIME_ARGS[@]}" \
  "${IMAGE}" \
  claude -p "${TASK_PROMPT}"
