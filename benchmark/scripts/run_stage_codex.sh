#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
. "${SCRIPT_DIR}/proxy-env.sh"

usage() {
  cat <<'EOF'
Usage:
  run_stage_codex.sh [STAGE_WORKSPACE]

Runs the Codex benchmark image against a stage-local workspace.
If STAGE_WORKSPACE is omitted, the current working directory is used.

Expected workspace layout:
  repo/
  task/prompt.md

Environment:
  CODEX_HOME                             Optional host Codex state dir; defaults to ~/.codex
  CRS_OAI_KEY                            Required and forwarded only for alternate CODEX_HOME
  CODEX_IMAGE                            Optional, defaults to csc6052-codex
  CODEX_PROFILE                          Optional, e.g. thorough
  CODEX_TASK_PROMPT                      Optional override for the codex prompt
EOF
}

fail() {
  printf '%s\n' "$*" >&2
  exit 2
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
if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
  RUNTIME=${CONTAINER_RUNTIME}
elif command -v docker >/dev/null 2>&1; then
  RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
else
  RUNTIME=docker
fi

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -z "${CRS_OAI_KEY:-}" ]]; then
  fail "provide CRS_OAI_KEY when using an alternate CODEX_HOME for codex"
fi

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${CRS_OAI_KEY:-}" ]]; then
  export OPENAI_API_KEY="${CRS_OAI_KEY}"
fi

if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 0 && ! -f "${AUTH_FILE}" ]]; then
  fail "expected default Codex auth file at ${AUTH_FILE}; set CODEX_HOME with CRS_OAI_KEY for an alternate codex setup"
fi

CMD=(
  "${RUNTIME}" run --rm
  -v "${WORKSPACE_ROOT}:/workspace"
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
  CMD+=(-e "OPENAI_API_KEY=${OPENAI_API_KEY}")
fi
if [[ "${HOST_CODEX_HOME_CUSTOM}" -eq 1 && -n "${CRS_OAI_KEY:-}" ]]; then
  CMD+=(-e "CRS_OAI_KEY=${CRS_OAI_KEY}")
fi

while IFS= read -r proxy_arg; do
  [[ -n "${proxy_arg}" ]] || continue
  CMD+=("${proxy_arg}")
done < <(print_container_proxy_args "${RUNTIME}")

CMD+=("${IMAGE}" codex exec)

if [[ -n "${CODEX_PROFILE:-}" ]]; then
  CMD+=(-p "${CODEX_PROFILE}")
fi

CMD+=("${TASK_PROMPT}")

exec "${CMD[@]}"
