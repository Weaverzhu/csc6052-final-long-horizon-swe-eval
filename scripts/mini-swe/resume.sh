export MODEL="deepseek/deepseek-chat"
export API_BASE="https://api.deepseek.com"

export PYTHONPATH="$(pwd)"
export MSWEA_MINI_STEP_LIMIT="${MSWEA_MINI_STEP_LIMIT:-120}"

START_STAGE=2
END_STAGE=5

previous_repo_dir=.agent_workspaces/deepseek__deepseek-chat/1-3/repo
result_dir=.agent_workspaces/deepseek__deepseek-chat/${START_STAGE}-${END_STAGE}-resume

uv run python -m benchmark.harness.run_trajectory \
    --repo-dir $previous_repo_dir \
    --results-dir $result_dir \
    --start-stage 2 \
    --end-stage 5 \
    -- \
podman run --rm -i \
    -v {workspace_dir}:/workspace \
    -e MSWEA_MODEL_NAME="${MODEL}" \
    -e DEEPSEEK_API_KEY=$API_KEY \
    -e OPENAI_API_BASE="${API_BASE}" \
    -e MSWEA_MODEL_BACKEND="openai-compat" \
    -e MSWEA_MINI_STEP_LIMIT \
    csc6052-mini-swe-agent \
    mini -t "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it."
