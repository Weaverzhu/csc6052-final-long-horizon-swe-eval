#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
INVOCATION_DIR=${PWD}
. "${REPO_ROOT}/benchmark/scripts/proxy-env.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/managed/go.sh

Allocates a fresh managed run directory under:
  <runs-root>/<framework>/<model>/<template>/<run_id>/

Required environment:
  FRAMEWORK                              Agent framework: codex, mini-swe-agent, or claude
  MODEL                                  Model name recorded in the manifest

Common optional environment:
  RUNS_ROOT                              Defaults to "$PWD/.agent_runs"
  TEMPLATE                               Defaults to project-1
  STAGE_NUM                              Defaults to 1
  END_STAGE                              Defaults to 3
  REPO_DIR                               Optional existing repo snapshot to resume from
  CONTAINER_RUNTIME                      Optional, auto-detects docker vs podman
  EXPERIMENT_ID                          Optional experiment id copied into run manifest
  AGENT_ID                               Optional logical agent id copied into run manifest
  REPEAT_INDEX                           Optional repeat index copied into run manifest

Codex-specific environment:
  CODEX_HOME                             Optional host Codex state dir; defaults to ~/.codex
  CRS_OAI_KEY                            Required and forwarded only for alternate CODEX_HOME
  CODEX_IMAGE                            Defaults to csc6052-codex
  CODEX_PROFILE                          Optional codex profile
  CODEX_TASK_PROMPT                      Optional prompt override
  CODEX_MODEL_REASONING_EFFORT           Optional, defaults to medium
  CODEX_PLAN_MODE_REASONING_EFFORT       Optional, defaults to medium

mini-SWE-agent-specific environment:
  API_KEY                                Required unless OPENAI_API_KEY is already set
  OPENAI_API_KEY                         Same role as API_KEY
  API_BASE                               Defaults to https://openrouter.ai/api/v1
  OPENAI_API_BASE                        Same role as API_BASE
  MODEL_BACKEND                          Optional: openrouter or openai-compat
  MSWEA_MODEL_BACKEND                    Same role as MODEL_BACKEND
  MINI_IMAGE                             Defaults to csc6052-mini-swe-agent
  MINI_TASK_PROMPT                       Optional prompt override
  MSWEA_MINI_STEP_LIMIT                  Optional, defaults to 120

Claude-specific environment:
  CLAUDE_PROVIDER                        Optional: anthropic or deepseek
  CLAUDE_CODE_OAUTH_TOKEN                Required for Anthropic subscription mode
  DEEPSEEK_API_KEY / ANTHROPIC_AUTH_TOKEN Required for DeepSeek mode
  CLAUDE_IMAGE                           Defaults to csc6052-claude
  CLAUDE_TASK_PROMPT                     Optional prompt override
  CLAUDE_MAX_TURNS                       Optional, consumed by the Claude image

Examples:
  FRAMEWORK=codex MODEL=gpt-5.4 scripts/managed/go.sh
  FRAMEWORK=codex MODEL=gpt-5.4 CODEX_HOME=/path/to/codex CRS_OAI_KEY=... scripts/managed/go.sh
  FRAMEWORK=mini-swe-agent MODEL=deepseek/deepseek-chat \
    API_KEY=... API_BASE=https://api.deepseek.com MODEL_BACKEND=openai-compat \
    scripts/managed/go.sh
  FRAMEWORK=claude MODEL='deepseek-v4-pro[1m]' \
    CLAUDE_PROVIDER=deepseek DEEPSEEK_API_KEY=... scripts/managed/go.sh
EOF
}

fail() {
  printf '%s\n' "$*" >&2
  exit 2
}

select_runtime() {
  if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
    printf '%s\n' "${CONTAINER_RUNTIME}"
  elif command -v docker >/dev/null 2>&1; then
    printf '%s\n' "docker"
  elif command -v podman >/dev/null 2>&1; then
    printf '%s\n' "podman"
  else
    printf '%s\n' "docker"
  fi
}

resolve_host_codex_home() {
  local raw_home="$1"
  case "${raw_home}" in
    "~")
      printf '%s\n' "${HOME}"
      ;;
    "~/"*)
      printf '%s/%s\n' "${HOME}" "${raw_home#\~/}"
      ;;
    *)
      printf '%s\n' "${raw_home}"
      ;;
  esac
}

normalize_framework() {
  case "$1" in
    codex)
      printf '%s\n' "codex"
      ;;
    mini|mini-swe|mini-swe-agent)
      printf '%s\n' "mini-swe-agent"
      ;;
    claude|claude-code)
      printf '%s\n' "claude"
      ;;
    *)
      fail "unsupported FRAMEWORK='$1'; use codex, mini-swe-agent, or claude"
      ;;
  esac
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
  if [[ "${MODEL:-${ANTHROPIC_MODEL:-}}" == deepseek* ]]; then
    printf '%s\n' "deepseek"
    return 0
  fi

  printf '%s\n' "anthropic"
}

configure_deepseek_claude_provider() {
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

FRAMEWORK_RAW=${FRAMEWORK:-}
MODEL=${MODEL:-}
RUNS_ROOT=${RUNS_ROOT:-"${INVOCATION_DIR}/.agent_runs"}
TEMPLATE=${TEMPLATE:-project-1}
STAGE_NUM=${STAGE_NUM:-1}
END_STAGE=${END_STAGE:-3}
REPO_DIR=${REPO_DIR:-}
EXPERIMENT_ID=${EXPERIMENT_ID:-}
AGENT_ID=${AGENT_ID:-}
REPEAT_INDEX=${REPEAT_INDEX:-}
RUNTIME=$(select_runtime)

if [[ -z "${FRAMEWORK_RAW}" ]]; then
  fail "set FRAMEWORK before running this script"
fi
if [[ -z "${MODEL}" ]]; then
  fail "set MODEL before running this script"
fi

FRAMEWORK=$(normalize_framework "${FRAMEWORK_RAW}")

cd "${REPO_ROOT}"

case "${FRAMEWORK}" in
  codex)
    "${RUNTIME}" build -t csc6052-codex docker/agents/codex
    IMAGE=${CODEX_IMAGE:-csc6052-codex}
    DEFAULT_HOST_CODEX_HOME=$(resolve_host_codex_home "~/.codex")
    HOST_CODEX_HOME_CUSTOM=0
    if [[ -n "${CODEX_HOME:-}" ]]; then
      HOST_CODEX_HOME=$(resolve_host_codex_home "${CODEX_HOME}")
      if [[ "${HOST_CODEX_HOME}" != "${DEFAULT_HOST_CODEX_HOME}" ]]; then
        HOST_CODEX_HOME_CUSTOM=1
      fi
    else
      HOST_CODEX_HOME=${DEFAULT_HOST_CODEX_HOME}
    fi
    CONTAINER_CODEX_HOME=${CONTAINER_CODEX_HOME:-/codex-home/.codex}
    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && ! -d "${HOST_CODEX_HOME}" ]]; then
      fail "CODEX_HOME must point to an existing host directory: ${HOST_CODEX_HOME}"
    fi
    AUTH_FILE="${HOST_CODEX_HOME}/auth.json"
    TASK_PROMPT=${CODEX_TASK_PROMPT:-Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it.}

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -z "${CRS_OAI_KEY:-}" ]]; then
      fail "provide CRS_OAI_KEY when using an alternate CODEX_HOME for codex"
    fi

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 0 && ! -f "${AUTH_FILE}" ]]; then
      fail "expected default Codex auth file at ${AUTH_FILE}; set CODEX_HOME with CRS_OAI_KEY for an alternate codex setup"
    fi

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${CRS_OAI_KEY:-}" ]]; then
      export OPENAI_API_KEY="${CRS_OAI_KEY}"
    fi
    ;;
  mini-swe-agent)
    "${RUNTIME}" build -t csc6052-mini-swe-agent docker/agents/mini-swe-agent
    IMAGE=${MINI_IMAGE:-csc6052-mini-swe-agent}
    TASK_PROMPT=${MINI_TASK_PROMPT:-Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.}
    API_KEY_VALUE=${API_KEY:-${OPENAI_API_KEY:-}}
    API_BASE_VALUE=${API_BASE:-${OPENAI_API_BASE:-https://openrouter.ai/api/v1}}
    MODEL_BACKEND_VALUE=${MODEL_BACKEND:-${MSWEA_MODEL_BACKEND:-}}

    if [[ -z "${API_KEY_VALUE}" ]]; then
      fail "provide API_KEY or OPENAI_API_KEY before running mini-swe-agent"
    fi

    export OPENAI_API_KEY="${API_KEY_VALUE}"
    export OPENAI_API_BASE="${API_BASE_VALUE}"
    export MSWEA_MINI_STEP_LIMIT="${MSWEA_MINI_STEP_LIMIT:-120}"
    if [[ -n "${MODEL_BACKEND_VALUE}" ]]; then
      export MSWEA_MODEL_BACKEND="${MODEL_BACKEND_VALUE}"
    fi
    ;;
  claude)
    "${RUNTIME}" build -t csc6052-claude docker/agents/claude
    IMAGE=${CLAUDE_IMAGE:-csc6052-claude}
    TASK_PROMPT=${CLAUDE_TASK_PROMPT:-Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.}
    CLAUDE_PROVIDER_VALUE=$(resolve_claude_provider)

    case "${CLAUDE_PROVIDER_VALUE}" in
      deepseek)
        configure_deepseek_claude_provider
        ;;
      anthropic)
        if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
          fail "provide CLAUDE_CODE_OAUTH_TOKEN before running claude"
        fi
        ;;
    esac
    ;;
esac

"${RUNTIME}" build -t csc6052-project-1-evaluator docker/evaluator

export PYTHONPATH="${REPO_ROOT}"
export BENCHMARK_CONTAINER_RUNTIME="${RUNTIME}"

CMD=(
  uv run python -m benchmark.harness.run_managed_trajectory
  --runs-root "${RUNS_ROOT}"
  --framework "${FRAMEWORK}"
  --model "${MODEL}"
  --template "${TEMPLATE}"
  --start-stage "${STAGE_NUM}"
  --end-stage "${END_STAGE}"
)

if [[ -n "${REPO_DIR}" ]]; then
  CMD+=(--repo-dir "${REPO_DIR}")
fi
if [[ -n "${EXPERIMENT_ID}" ]]; then
  CMD+=(--experiment-id "${EXPERIMENT_ID}")
fi
if [[ -n "${AGENT_ID}" ]]; then
  CMD+=(--agent-id "${AGENT_ID}")
fi
if [[ -n "${REPEAT_INDEX}" ]]; then
  CMD+=(--repeat-index "${REPEAT_INDEX}")
fi

CMD+=(--)

case "${FRAMEWORK}" in
  codex)
    CMD+=(
      "${RUNTIME}" run --rm
      -v "{workspace_dir}:/workspace"
    )

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 ]]; then
      CMD+=(
        -v "${HOST_CODEX_HOME}:${CONTAINER_CODEX_HOME}"
        -e "CODEX_HOME=${CONTAINER_CODEX_HOME}"
      )
    fi

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 0 && -f "${AUTH_FILE}" ]]; then
      CMD+=(-v "${AUTH_FILE}:${CONTAINER_CODEX_HOME}/auth.json:ro")
    fi

    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${OPENAI_API_KEY:-}" ]]; then
      CMD+=(-e OPENAI_API_KEY)
    fi
    if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${CRS_OAI_KEY:-}" ]]; then
      CMD+=(-e CRS_OAI_KEY)
    fi

    while IFS= read -r proxy_arg; do
      [[ -n "${proxy_arg}" ]] || continue
      CMD+=("${proxy_arg}")
    done < <(print_container_proxy_args "${RUNTIME}")

    CMD+=(
      -e "CODEX_MODEL=${MODEL}"
      -e "CODEX_MODEL_REASONING_EFFORT=${CODEX_MODEL_REASONING_EFFORT:-medium}"
      -e "CODEX_PLAN_MODE_REASONING_EFFORT=${CODEX_PLAN_MODE_REASONING_EFFORT:-medium}"
      "${IMAGE}"
      codex exec
    )

    if [[ -n "${CODEX_PROFILE:-}" ]]; then
      CMD+=(-p "${CODEX_PROFILE}")
    fi

    CMD+=("${TASK_PROMPT}")
    ;;
  mini-swe-agent)
    CMD+=(
      "${RUNTIME}" run --rm -i
      -v "{workspace_dir}:/workspace"
      -e "MSWEA_MODEL_NAME=${MODEL}"
      -e OPENAI_API_KEY
      -e "OPENAI_API_BASE=${OPENAI_API_BASE}"
      -e MSWEA_MINI_STEP_LIMIT
    )

    while IFS= read -r proxy_arg; do
      [[ -n "${proxy_arg}" ]] || continue
      CMD+=("${proxy_arg}")
    done < <(print_container_proxy_args "${RUNTIME}")

    if [[ -n "${MSWEA_MODEL_BACKEND:-}" ]]; then
      CMD+=(-e "MSWEA_MODEL_BACKEND=${MSWEA_MODEL_BACKEND}")
    fi

    CMD+=(
      "${IMAGE}"
      mini -t "${TASK_PROMPT}"
    )
    ;;
  claude)
    CMD+=(
      "${RUNTIME}" run --rm
      -v "{workspace_dir}:/workspace"
      -e "CLAUDE_MODEL=${MODEL}"
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
    else
      CMD+=(-e CLAUDE_CODE_OAUTH_TOKEN)
      while IFS= read -r proxy_arg; do
        [[ -n "${proxy_arg}" ]] || continue
        CMD+=("${proxy_arg}")
      done < <(print_container_proxy_args "${RUNTIME}")
    fi

    if [[ -n "${CLAUDE_MAX_TURNS:-}" ]]; then
      CMD+=(-e "CLAUDE_MAX_TURNS=${CLAUDE_MAX_TURNS}")
    fi

    CMD+=(
      "${IMAGE}"
      claude -p "${TASK_PROMPT}"
    )
    ;;
esac

printf 'Launching managed run under %s for %s/%s (%s)\n' \
  "${RUNS_ROOT}" "${FRAMEWORK}" "${MODEL}" "${TEMPLATE}"

exec "${CMD[@]}"
