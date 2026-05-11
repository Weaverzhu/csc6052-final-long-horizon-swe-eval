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

cd "${REPO_ROOT}"

"${RUNTIME}" build -t csc6052-codex docker/agents/codex
"${RUNTIME}" build -t csc6052-project-1-evaluator docker/evaluator

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

IMAGE="${CODEX_IMAGE:-csc6052-codex}"
MODEL="${CODEX_MODEL:-gpt-5.4}"
MODEL_SLUG="${MODEL//\//__}"
STAGE_NUM="${STAGE_NUM:-1}"
END_STAGE="${END_STAGE:-3}"
RESULT_DIR=".agent_workspaces/codex/${MODEL_SLUG}/${STAGE_NUM}-${END_STAGE}"
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
  echo "CODEX_HOME must point to an existing host directory: ${HOST_CODEX_HOME}" >&2
  exit 2
fi
AUTH_FILE="${HOST_CODEX_HOME}/auth.json"
TASK_PROMPT="${CODEX_TASK_PROMPT:-Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it.}"

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -z "${CRS_OAI_KEY:-}" ]]; then
  echo "provide CRS_OAI_KEY when using an alternate CODEX_HOME for codex" >&2
  exit 2
fi

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${CRS_OAI_KEY:-}" ]]; then
  export OPENAI_API_KEY="${CRS_OAI_KEY}"
fi

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 0 && ! -f "${AUTH_FILE}" ]]; then
  echo "expected default Codex auth file at ${AUTH_FILE}; set CODEX_HOME with CRS_OAI_KEY for an alternate codex setup" >&2
  exit 2
fi

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
  -v {workspace_dir}:/workspace
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

exec "${CMD[@]}"
