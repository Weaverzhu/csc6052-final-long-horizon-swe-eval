#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "codex runtime error: $*" >&2
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

CODEX_HOME_EXPLICIT=0
if [[ -n "${CODEX_HOME:-}" ]]; then
  CODEX_HOME_EXPLICIT=1
fi

if [[ "${CODEX_HOME_EXPLICIT}" -eq 1 && -n "${CRS_OAI_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  export OPENAI_API_KEY="${CRS_OAI_KEY}"
fi

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
      "${short_flag}"*)
        if [[ "$arg" != "$short_flag" ]]; then
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
  fail "expected a non-interactive codex command such as: codex exec --full-auto \"<task>\""
fi

CODEX_STATE_DIR="${CODEX_HOME:-${HOME:-/codex-home}/.codex}"

mkdir -p "${CODEX_STATE_DIR}"

if [[ "${CODEX_HOME_EXPLICIT}" -eq 0 && -f /opt/codex-default/config.toml ]]; then
  cp /opt/codex-default/config.toml "${CODEX_STATE_DIR}/config.toml"
fi

if [[ "${CODEX_HOME_EXPLICIT}" -eq 0 && -n "${CODEX_MODEL:-}" ]]; then
  {
    printf 'model_provider = "%s"\n' "${CODEX_MODEL_PROVIDER:-openai}"
    printf 'model = "%s"\n' "${CODEX_MODEL}"
    printf 'model_reasoning_effort = "%s"\n' "${CODEX_MODEL_REASONING_EFFORT:-high}"
    printf 'plan_mode_reasoning_effort = "%s"\n' "${CODEX_PLAN_MODE_REASONING_EFFORT:-medium}"
    printf 'personality = "%s"\n' "${CODEX_PERSONALITY:-pragmatic}"
    printf 'supports_websockets = false\n'
  } > "${CODEX_STATE_DIR}/config.toml"
fi

if [[ ! -f "${CODEX_STATE_DIR}/auth.json" && -n "${OPENAI_API_KEY:-}" ]]; then
  printf '%s' "${OPENAI_API_KEY}" | codex login --with-api-key >/dev/null
fi

if [[ "$1" != "codex" ]]; then
  exec "$@"
fi

if [[ $# -eq 1 ]]; then
  fail "bare 'codex' is disabled in benchmark mode; use 'codex exec ...' so the run stays headless"
fi

if [[ "$2" != "exec" ]]; then
  exec "$@"
fi

if has_flag "-h" "--help" "$@"; then
  exec "$@"
fi

if [[ ! -f "${CODEX_STATE_DIR}/auth.json" && -z "${OPENAI_API_KEY:-}" ]]; then
  fail "provide /codex-home/.codex/auth.json or OPENAI_API_KEY before running 'codex exec'"
fi

RESULTS_ROOT="${AGENT_RESULTS_DIR:-/workspace/.agent-results}"
RUN_ID="${AGENT_RUN_ID:-latest}"
ARTIFACT_DIR="${RESULTS_ROOT}/codex/${RUN_ID}"
FINAL_MESSAGE_PATH="${ARTIFACT_DIR}/final-message.txt"

mkdir -p "${ARTIFACT_DIR}"
if [[ -f "${CODEX_STATE_DIR}/config.toml" ]]; then
  cp "${CODEX_STATE_DIR}/config.toml" "${ARTIFACT_DIR}/config.toml"
fi

cmd=("$@")

has_execution_policy=0
if has_flag "--dangerously-bypass-approvals-and-sandbox" \
  "--dangerously-bypass-approvals-and-sandbox" "${cmd[@]}"; then
  has_execution_policy=1
elif has_flag "--full-auto" "--full-auto" "${cmd[@]}"; then
  has_execution_policy=1
elif has_value_flag "-s" "--sandbox" "${cmd[@]}"; then
  has_execution_policy=1
elif has_value_flag "-a" "--ask-for-approval" "${cmd[@]}"; then
  has_execution_policy=1
fi

if [[ "${CODEX_ENABLE_INNER_SANDBOX:-0}" == "1" ]]; then
  if [[ "${has_execution_policy}" -eq 0 ]]; then
    cmd+=("--full-auto")
  fi
elif [[ "${has_execution_policy}" -eq 0 ]]; then
  cmd+=("--dangerously-bypass-approvals-and-sandbox")
fi

if ! has_flag "--skip-git-repo-check" "--skip-git-repo-check" "${cmd[@]}"; then
  cmd+=("--skip-git-repo-check")
fi

if ! has_value_flag "-o" "--output-last-message" "${cmd[@]}"; then
  cmd+=("--output-last-message" "${FINAL_MESSAGE_PATH}")
fi

record_command "${ARTIFACT_DIR}/command.txt" "${cmd[@]}"

set +e
"${cmd[@]}" 2>&1 | tee "${ARTIFACT_DIR}/console.log"
exit_code=${PIPESTATUS[0]}
set -e

printf '%s\n' "${exit_code}" > "${ARTIFACT_DIR}/exit-code.txt"
exit "${exit_code}"
