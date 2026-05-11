#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "mini-swe-agent runtime error: $*" >&2
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

normalize_openrouter_model_name() {
  local model_name="$1"
  printf '%s\n' "${model_name#openrouter/}"
}

normalize_openai_compatible_model_name() {
  local model_name="$1"
  case "${model_name}" in
    */*)
      printf '%s\n' "${model_name}"
      ;;
    *)
      printf '%s\n' "openai/${model_name}"
      ;;
  esac
}

normalize_model_backend() {
  local backend="${1:-}"
  case "${backend}" in
    "" )
      printf '%s\n' ""
      ;;
    openrouter|OpenRouter|OPENROUTER)
      printf '%s\n' "openrouter"
      ;;
    openai|openai-compat|openai_compat|litellm|OpenAI|OPENAI)
      printf '%s\n' "openai-compat"
      ;;
    *)
      fail "unsupported MSWEA_MODEL_BACKEND='${backend}'; use 'openrouter' or 'openai-compat'"
      ;;
  esac
}

record_command() {
  local destination="$1"
  shift
  printf '%q ' "$@" > "${destination}"
  printf '\n' >> "${destination}"
}

if [[ $# -eq 0 ]]; then
  fail "expected a non-interactive mini command such as: mini -t \"<task>\" -m \"google/gemma-4-26b-a4b-it:free\""
fi

if [[ "$1" != "mini" ]]; then
  exec "$@"
fi

if has_flag "-h" "--help" "$@"; then
  exec "$@"
fi

if [[ $# -eq 1 ]]; then
  fail "bare 'mini' is disabled in benchmark mode; pass -t/--task so the container never prompts for input"
fi

if ! has_value_flag "-t" "--task" "$@"; then
  fail "mini evaluation runs must pass -t/--task explicitly"
fi

if [[ -z "${MSWEA_MODEL_NAME:-}" ]]; then
  fail "set MSWEA_MODEL_NAME before running mini in benchmark mode"
fi

requested_model_name="${MSWEA_MODEL_NAME}"

resolved_backend="$(normalize_model_backend "${MSWEA_MODEL_BACKEND:-}")"
if [[ -z "${resolved_backend}" ]]; then
  if [[ -n "${OPENAI_API_BASE:-}" ]] && [[ "${OPENAI_API_BASE}" != *"openrouter.ai"* ]]; then
    resolved_backend="openai-compat"
  else
    resolved_backend="openrouter"
  fi
fi
export MSWEA_MODEL_BACKEND="${resolved_backend}"

BENCHMARK_MINI_PROMPT_CONFIG_PATH="${BENCHMARK_MINI_PROMPT_CONFIG_PATH:-/opt/mini-swe-agent/benchmark-mini-prompt.yaml}"
if [[ ! -f "${BENCHMARK_MINI_PROMPT_CONFIG_PATH}" ]]; then
  fail "benchmark mini prompt config not found at ${BENCHMARK_MINI_PROMPT_CONFIG_PATH}"
fi
BENCHMARK_MINI_STEP_LIMIT="${MSWEA_MINI_STEP_LIMIT:-120}"
if [[ ! "${BENCHMARK_MINI_STEP_LIMIT}" =~ ^[0-9]+$ ]]; then
  fail "MSWEA_MINI_STEP_LIMIT must be an integer >= 0"
fi

case "${MSWEA_MODEL_BACKEND}" in
  openrouter)
    if [[ -n "${OPENAI_API_BASE:-}" ]] && [[ "${OPENAI_API_BASE}" != *"openrouter.ai"* ]]; then
      fail "OPENAI_API_BASE must point to openrouter.ai when MSWEA_MODEL_BACKEND=openrouter"
    fi
    if [[ -n "${OPENAI_API_KEY:-}" && -z "${OPENROUTER_API_KEY:-}" ]]; then
      export OPENROUTER_API_KEY="${OPENAI_API_KEY}"
    fi
    if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
      fail "set OPENROUTER_API_KEY or OPENAI_API_KEY for OpenRouter"
    fi
    export MSWEA_MODEL_NAME="$(normalize_openrouter_model_name "${requested_model_name}")"
    requested_model_name="${MSWEA_MODEL_NAME}"
    ;;
  openai-compat)
    if [[ -z "${OPENAI_API_BASE:-}" ]]; then
      fail "set OPENAI_API_BASE for an OpenAI-compatible provider"
    fi
    if [[ -n "${DEEPSEEK_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
      export OPENAI_API_KEY="${DEEPSEEK_API_KEY}"
    fi
    if [[ -n "${OPENAI_API_KEY:-}" && -z "${DEEPSEEK_API_KEY:-}" && "${OPENAI_API_BASE}" == *"api.deepseek.com"* ]]; then
      export DEEPSEEK_API_KEY="${OPENAI_API_KEY}"
    fi
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      fail "set OPENAI_API_KEY or DEEPSEEK_API_KEY for an OpenAI-compatible provider"
    fi
    export MSWEA_MODEL_NAME="$(normalize_openai_compatible_model_name "${requested_model_name}")"
    requested_model_name="${MSWEA_MODEL_NAME}"
    if [[ -z "${MSWEA_COST_TRACKING:-}" ]]; then
      export MSWEA_COST_TRACKING="ignore_errors"
    fi
    ;;
esac

if [[ "${requested_model_name}" == *":free" ]] && [[ -z "${MSWEA_COST_TRACKING:-}" ]]; then
  export MSWEA_COST_TRACKING="ignore_errors"
fi

MINI_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME:-/root}/.config}/mini-swe-agent"
MINI_GLOBAL_ENV="${MINI_CONFIG_HOME}/.env"
RESULTS_ROOT="${AGENT_RESULTS_DIR:-/workspace/.agent-results}"
RUN_ID="${AGENT_RUN_ID:-latest}"
ARTIFACT_DIR="${RESULTS_ROOT}/mini/${RUN_ID}"
TRAJECTORY_PATH="${ARTIFACT_DIR}/trajectory.traj.json"
BENCHMARK_MINI_RUNTIME_CONFIG_PATH="${ARTIFACT_DIR}/benchmark-mini-prompt.yaml"

mkdir -p "${MINI_CONFIG_HOME}" "${ARTIFACT_DIR}"
cp "${BENCHMARK_MINI_PROMPT_CONFIG_PATH}" "${BENCHMARK_MINI_RUNTIME_CONFIG_PATH}"
printf '\n  step_limit: %s\n' "${BENCHMARK_MINI_STEP_LIMIT}" >> "${BENCHMARK_MINI_RUNTIME_CONFIG_PATH}"

cat > "${MINI_GLOBAL_ENV}" <<EOF
MSWEA_CONFIGURED=true
MSWEA_MODEL_NAME=${MSWEA_MODEL_NAME:-}
MSWEA_MODEL_BACKEND=${MSWEA_MODEL_BACKEND:-}
OPENAI_API_BASE=${OPENAI_API_BASE:-}
MSWEA_COST_TRACKING=${MSWEA_COST_TRACKING:-}
http_proxy=${http_proxy:-}
HTTP_PROXY=${HTTP_PROXY:-}
https_proxy=${https_proxy:-}
HTTPS_PROXY=${HTTPS_PROXY:-}
no_proxy=${no_proxy:-}
NO_PROXY=${NO_PROXY:-}
EOF

cp "${MINI_GLOBAL_ENV}" "${ARTIFACT_DIR}/global.env"
export MSWEA_CONFIGURED=true
unset MSWEA_MINI_CONFIG_PATH

cmd=("$@")

for ((i = 0; i < ${#cmd[@]}; i++)); do
  case "${cmd[$i]}" in
    -m|--model)
      has_model_flag=1
      break
      ;;
    --model=*)
      has_model_flag=1
      break
      ;;
  esac
done

if [[ "${has_model_flag:-0}" -eq 0 ]]; then
  cmd+=("-m" "${requested_model_name}")
fi

if ! has_flag "-y" "--yolo" "${cmd[@]}"; then
  cmd+=("-y")
fi

if ! has_flag "--exit-immediately" "--exit-immediately" "${cmd[@]}"; then
  cmd+=("--exit-immediately")
fi

if ! has_value_flag "-o" "--output" "${cmd[@]}"; then
  cmd+=("-o" "${TRAJECTORY_PATH}")
fi

cmd+=("-c" "${BENCHMARK_MINI_RUNTIME_CONFIG_PATH}")

record_command "${ARTIFACT_DIR}/command.txt" "${cmd[@]}"

set +e
"${cmd[@]}" 2>&1 | tee "${ARTIFACT_DIR}/console.log"
exit_code=${PIPESTATUS[0]}
set -e

printf '%s\n' "${exit_code}" > "${ARTIFACT_DIR}/exit-code.txt"
exit "${exit_code}"
