#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "claude runtime error: $*" >&2
  exit 2
}

sync_env_pair() {
  local lower_name="$1"
  local upper_name="$2"
  local lower_value="${!lower_name-}"
  local upper_value="${!upper_name-}"

  if [[ -n "${lower_value}" && -z "${upper_value}" ]]; then
    export "${upper_name}=${lower_value}"
    return 0
  fi
  if [[ -n "${upper_value}" && -z "${lower_value}" ]]; then
    export "${lower_name}=${upper_value}"
  fi
}

normalize_proxy_env() {
  local shared_proxy=""

  if [[ -n "${http_proxy-}" ]]; then
    shared_proxy="${http_proxy}"
  elif [[ -n "${HTTP_PROXY-}" ]]; then
    shared_proxy="${HTTP_PROXY}"
  elif [[ -n "${https_proxy-}" ]]; then
    shared_proxy="${https_proxy}"
  elif [[ -n "${HTTPS_PROXY-}" ]]; then
    shared_proxy="${HTTPS_PROXY}"
  fi

  if [[ -n "${shared_proxy}" ]]; then
    export "http_proxy=${shared_proxy}"
    export "HTTP_PROXY=${shared_proxy}"
    export "https_proxy=${shared_proxy}"
    export "HTTPS_PROXY=${shared_proxy}"
  fi

  sync_env_pair no_proxy NO_PROXY
}

normalize_proxy_env

is_deepseek_claude_provider() {
  local configured="${CLAUDE_PROVIDER:-${CLAUDE_CODE_PROVIDER:-}}"
  case "${configured}" in
    deepseek)
      return 0
      ;;
    anthropic|subscription)
      return 1
      ;;
    "")
      ;;
    *)
      fail "unsupported CLAUDE_PROVIDER='${configured}'; use anthropic or deepseek"
      ;;
  esac

  if [[ "${ANTHROPIC_BASE_URL:-}" == *"api.deepseek.com"* ]]; then
    return 0
  fi
  if [[ "${ANTHROPIC_MODEL:-${CLAUDE_MODEL:-}}" == deepseek* ]]; then
    return 0
  fi
  return 1
}

configure_deepseek_claude_provider() {
  local deepseek_model="${ANTHROPIC_MODEL:-${CLAUDE_MODEL:-deepseek-v4-pro[1m]}}"

  export "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" && -n "${DEEPSEEK_API_KEY:-}" ]]; then
    export "ANTHROPIC_AUTH_TOKEN=${DEEPSEEK_API_KEY}"
  elif [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" && -n "${API_KEY:-}" ]]; then
    export "ANTHROPIC_AUTH_TOKEN=${API_KEY}"
  fi

  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
    fail "provide DEEPSEEK_API_KEY or ANTHROPIC_AUTH_TOKEN before running claude with DeepSeek"
  fi

  export "CLAUDE_MODEL=${CLAUDE_MODEL:-${deepseek_model}}"
  export "ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-${deepseek_model}}"
  export "ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL:-${deepseek_model}}"
  export "ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL:-${deepseek_model}}"
  export "ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL:-deepseek-v4-flash}"
  export "CLAUDE_CODE_SUBAGENT_MODEL=${CLAUDE_CODE_SUBAGENT_MODEL:-deepseek-v4-flash}"
  export "CLAUDE_CODE_EFFORT_LEVEL=${CLAUDE_CODE_EFFORT_LEVEL:-max}"
}

has_flag() {
  local short_flag="$1"
  local long_flag="$2"
  shift 2
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "$short_flag" || "$arg" == "$long_flag" ]]; then
      return 0
    fi
  done
  return 1
}

has_value_flag() {
  local short_flag="$1"
  local long_flag="$2"
  shift 2
  local arg
  local expect_value=0
  for arg in "$@"; do
    if [[ "$expect_value" -eq 1 ]]; then
      return 0
    fi
    case "$arg" in
      "$short_flag"|"$long_flag")
        expect_value=1
        ;;
      "${long_flag}"=*)
        return 0
        ;;
      *)
        if [[ -n "${short_flag}" ]] && [[ "$arg" == "${short_flag}"* ]] && [[ "$arg" != "$short_flag" ]]; then
          return 0
        fi
        ;;
    esac
  done
  return 1
}

record_command() {
  local destination="$1"
  shift
  printf '%q ' "$@" > "${destination}"
  printf '\n' >> "${destination}"
}

if [[ $# -eq 0 ]]; then
  fail "expected a non-interactive claude command such as: claude -p \"<task>\""
fi

if [[ "$1" != "claude" ]]; then
  exec "$@"
fi

if has_flag "-h" "--help" "$@"; then
  exec "$@"
fi

if [[ $# -eq 1 ]]; then
  fail "bare 'claude' is disabled in benchmark mode; use 'claude -p ...' so the run stays headless"
fi

if ! has_flag "-p" "--print" "$@"; then
  fail "claude benchmark runs must use -p/--print for a fresh non-interactive session"
fi

if has_flag "-c" "--continue" "$@" || has_value_flag "-r" "--resume" "$@"; then
  fail "claude benchmark runs do not support continue/resume flags; start a fresh session for each stage"
fi

if is_deepseek_claude_provider; then
  configure_deepseek_claude_provider
elif [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  fail "provide CLAUDE_CODE_OAUTH_TOKEN before running claude in benchmark mode"
fi

CLAUDE_MODEL_NAME="${CLAUDE_MODEL:-claude-sonnet-4-6}"
CLAUDE_MAX_TURNS_VALUE="${CLAUDE_MAX_TURNS:-120}"
if [[ ! "${CLAUDE_MAX_TURNS_VALUE}" =~ ^[0-9]+$ ]]; then
  fail "CLAUDE_MAX_TURNS must be an integer >= 0"
fi

RESULTS_ROOT="${AGENT_RESULTS_DIR:-/workspace/.agent-results}"
RUN_ID="${AGENT_RUN_ID:-latest}"
ARTIFACT_DIR="${RESULTS_ROOT}/claude/${RUN_ID}"
FINAL_MESSAGE_PATH="${ARTIFACT_DIR}/final-message.txt"
CONSOLE_LOG_PATH="${ARTIFACT_DIR}/console.log"

mkdir -p "${ARTIFACT_DIR}"
: > "${FINAL_MESSAGE_PATH}"
: > "${CONSOLE_LOG_PATH}"

cmd=("$@")

has_permission_policy=0
if has_flag "--dangerously-skip-permissions" "--dangerously-skip-permissions" "${cmd[@]}"; then
  has_permission_policy=1
elif has_value_flag "" "--permission-mode" "${cmd[@]}"; then
  has_permission_policy=1
elif has_value_flag "" "--permission-prompt-tool" "${cmd[@]}"; then
  has_permission_policy=1
fi

if [[ "${has_permission_policy}" -eq 0 ]]; then
  cmd+=("--dangerously-skip-permissions")
fi

if ! has_value_flag "" "--output-format" "${cmd[@]}"; then
  cmd+=("--output-format" "text")
fi

if ! has_value_flag "" "--max-turns" "${cmd[@]}"; then
  cmd+=("--max-turns" "${CLAUDE_MAX_TURNS_VALUE}")
fi

if ! has_value_flag "" "--model" "${cmd[@]}"; then
  cmd+=("--model" "${CLAUDE_MODEL_NAME}")
fi

record_command "${ARTIFACT_DIR}/command.txt" "${cmd[@]}"

set +e
"${cmd[@]}" \
  > >(tee "${FINAL_MESSAGE_PATH}" | tee -a "${CONSOLE_LOG_PATH}") \
  2> >(tee -a "${CONSOLE_LOG_PATH}" >&2)
exit_code=$?
set -e

printf '%s\n' "${exit_code}" > "${ARTIFACT_DIR}/exit-code.txt"
exit "${exit_code}"
