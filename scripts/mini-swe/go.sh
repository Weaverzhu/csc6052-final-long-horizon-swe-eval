#!/bin/bash
set -euo pipefail

podman build -t csc6052-mini-swe-agent docker/agents/mini-swe-agent
podman build -t csc6052-project-1-evaluator docker/evaluator

MODEL="${MODEL:-deepseek/deepseek-chat}"
MODEL_SLUG="${MODEL//\//__}"
API_BASE="${API_BASE:-https://api.deepseek.com}"
STAGE_NUM="${STAGE_NUM:-1}"
END_STAGE="${END_STAGE:-3}"
STEP_LIMIT="${MSWEA_MINI_STEP_LIMIT:-120}"
RESULT_DIR=".agent_workspaces/${MODEL_SLUG}/${STAGE_NUM}-${END_STAGE}"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  if [[ -n "${API_KEY:-}" ]]; then
    export DEEPSEEK_API_KEY="${API_KEY}"
  else
    echo "set DEEPSEEK_API_KEY or API_KEY before running this script" >&2
    exit 2
  fi
fi

rm -rf "${RESULT_DIR}"
mkdir -p "${RESULT_DIR}"

export PYTHONPATH="$(pwd)"
export MSWEA_MINI_STEP_LIMIT="${STEP_LIMIT}"

uv run python -m benchmark.harness.run_trajectory \
  --results-dir "${RESULT_DIR}" \
  --start-stage "${STAGE_NUM}" \
  --end-stage "${END_STAGE}" \
  -- \
  podman run --rm -i \
    -v {workspace_dir}:/workspace \
    -e MSWEA_MODEL_NAME="${MODEL}" \
    -e DEEPSEEK_API_KEY \
    -e OPENAI_API_BASE="${API_BASE}" \
    -e MSWEA_MODEL_BACKEND="openai-compat" \
    -e MSWEA_MINI_STEP_LIMIT \
    csc6052-mini-swe-agent \
    mini -t "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it."
