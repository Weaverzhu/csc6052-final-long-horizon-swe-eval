#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
  RUNTIME=${CONTAINER_RUNTIME}
elif command -v docker >/dev/null 2>&1; then
  RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
else
  RUNTIME=docker
fi

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

cd "${REPO_ROOT}"

"${RUNTIME}" build -t csc6052-claude docker/agents/claude
"${RUNTIME}" build -t csc6052-project-1-evaluator docker/evaluator

IMAGE="${CLAUDE_IMAGE:-csc6052-claude}"
MODEL="${CLAUDE_MODEL:-}"
CLAUDE_PROVIDER_VALUE=$(resolve_claude_provider)
case "${CLAUDE_PROVIDER_VALUE}" in
  deepseek)
    configure_deepseek_claude_provider
    ;;
  anthropic)
    MODEL="${MODEL:-claude-sonnet-4-6}"
    if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
      fail "provide CLAUDE_CODE_OAUTH_TOKEN before running this script"
    fi
    ;;
esac
MODEL_SLUG="${MODEL//\//__}"
STAGE_NUM="${STAGE_NUM:-1}"
END_STAGE="${END_STAGE:-3}"
RESULT_DIR=".agent_workspaces/claude/${MODEL_SLUG}/${STAGE_NUM}-${END_STAGE}"
TASK_PROMPT="${CLAUDE_TASK_PROMPT:-Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.}"

rm -rf "${RESULT_DIR}"
mkdir -p "${RESULT_DIR}"

export PYTHONPATH="${REPO_ROOT}"
export BENCHMARK_CONTAINER_RUNTIME="${RUNTIME}"

CMD=(
  uv run python -m benchmark.harness.run_trajectory
  --results-dir "${RESULT_DIR}"
  --start-stage "${STAGE_NUM}"
  --end-stage "${END_STAGE}"
  --
  "${RUNTIME}" run --rm
  -v "{workspace_dir}:/workspace"
  -e "CLAUDE_MODEL=${MODEL}"
  -e "CLAUDE_MAX_TURNS=${CLAUDE_MAX_TURNS:-120}"
)

if [[ "${CLAUDE_PROVIDER_VALUE}" == "deepseek" ]]; then
  CMD+=(
    -e "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}"
    -e ANTHROPIC_AUTH_TOKEN
    -e "ANTHROPIC_MODEL=${ANTHROPIC_MODEL}"
    -e "ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL}"
    -e "ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL}"
    -e "ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL}"
    -e "CLAUDE_CODE_SUBAGENT_MODEL=${CLAUDE_CODE_SUBAGENT_MODEL}"
    -e "CLAUDE_CODE_EFFORT_LEVEL=${CLAUDE_CODE_EFFORT_LEVEL}"
  )
elif [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  CMD+=(-e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}")
fi

CMD+=(
  "${IMAGE}"
  claude -p "${TASK_PROMPT}"
)

exec "${CMD[@]}"
