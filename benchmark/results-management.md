# Managed Run Root

Use the managed runner when you want one shared root that keeps all benchmark runs across different agent frameworks and models in a single canonical layout.

The manager allocates a fresh run directory for every invocation, preserves previous runs, writes a `run-manifest.json`, then delegates to the normal trajectory runner.

## Canonical Layout

```text
<runs-root>/
  <framework>/
    <model>/
      <template>/
        <run_id>/
          run-manifest.json
          trajectory.json
          repo/
          stage_01/
          stage_02/
          ...
```

Notes:

- `framework`, `model`, and `template` are directory-safe slugs derived from the user-provided values.
- The manifest preserves the original raw `framework` and `model` strings, so you do not lose names such as `deepseek/deepseek-chat`.
- `run_id` is a UTC timestamp slug. If two runs land in the same second, the manager appends a numeric suffix.

## Config-Driven Experiment Runner

Use the repo-root [`config.yaml`](/Users/weaverzhu/Documents/workspace/CSC6052-final/config.yaml) to run the full multi-agent experiment. It stores environment variable references such as `from_env: DEEPSEEK_API_KEY`; actual API keys remain in your shell environment.

Run the default serial experiment:

```bash
uv run python -m benchmark.harness.run_experiment run --config config.yaml
```

Preview all planned agent/project/repeat combinations without spending API calls:

```bash
uv run python -m benchmark.harness.run_experiment run --config config.yaml --dry-run
```

Regenerate the averaged performance table and summary JSON from existing run manifests:

```bash
uv run python -m benchmark.harness.run_experiment summary --config config.yaml
```

The runner launches managed trajectories one at a time for cost control, displays `tqdm` progress, and writes result artifacts under `output_dir`:

- `<output-dir>/<experiment_id>-results.md`: the averaged agent performance table
- `<output-dir>/<experiment_id>-summary.json`: the machine-readable summary

If `output_dir` is omitted, it defaults to `runs_root`. To keep progress readable, turn off subprocess terminal output in `config.yaml`:

```yaml
output: false
```

You can also route streams independently:

```yaml
output:
  stdout: logs/{agent_id}/{project}/repeat-{repeat_index}/stdout.log
  stderr: logs/{agent_id}/{project}/repeat-{repeat_index}/stderr.log
```

`output: false` discards both streams. `stdout` and `stderr` accept `inherit`/`terminal`, `discard`/`null`, `false`, or a path template. Relative paths are written under `runs_root`; supported placeholders are `{experiment_id}`, `{agent_id}`, `{framework}`, `{model}`, `{project}`, and `{repeat_index}`.

## Shell Wrapper

If you want a shell entrypoint similar to `scripts/codex/go.sh`, use [`scripts/managed/go.sh`](/Users/weaverzhu/Documents/workspace/CSC6052-final/scripts/managed/go.sh).

It keeps the shell side minimal:

- validates framework-specific auth inputs for Codex, mini-SWE-agent, and Claude
- builds the selected agent image plus the evaluator image
- delegates directory allocation and manifest writing to `run_managed_trajectory.py`

Codex example:

```bash
FRAMEWORK=codex \
MODEL=gpt-5.4 \
RUNS_ROOT="$PWD/.agent_runs" \
scripts/managed/go.sh
```

mini-SWE-agent with DeepSeek:

```bash
FRAMEWORK=mini-swe-agent \
MODEL=deepseek/deepseek-chat \
RUNS_ROOT="$PWD/.agent_runs" \
API_KEY="$DEEPSEEK_API_KEY" \
API_BASE="https://api.deepseek.com" \
MODEL_BACKEND=openai-compat \
scripts/managed/go.sh
```

Useful environment knobs:

- `FRAMEWORK`: `codex`, `mini-swe-agent`, or `claude`
- `MODEL`: raw model string stored in the manifest
- `RUNS_ROOT`: shared root, defaults to `"$PWD/.agent_runs"`
- `TEMPLATE`: benchmark template, defaults to `project-1`
- `STAGE_NUM` and `END_STAGE`: stage range, default `1..3`
- `REPO_DIR`: optional repo snapshot to continue from
- Codex defaults to `~/.codex/auth.json`; an explicit `CODEX_HOME=~/.codex` follows that default path without `CRS_OAI_KEY`. Alternate host `CODEX_HOME` directories are mounted as full state directories so their `config.toml` is used, and `CRS_OAI_KEY` is required.

## Launch A Managed Run

Codex example:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  --runs-root .agent_runs \
  --framework codex \
  --model gpt-5.4 \
  --template project-1 \
  --start-stage 1 \
  --end-stage 3 \
  -- \
  docker run --rm \
    -v {workspace_dir}:/workspace \
    -v "$HOME/.codex/auth.json:/codex-home/.codex/auth.json:ro" \
    csc6052-codex \
    codex exec "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it."
```

Claude example:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  --runs-root .agent_runs \
  --framework claude \
  --model claude-sonnet-4-6 \
  --template project-1 \
  --start-stage 1 \
  --end-stage 3 \
  -- \
  docker run --rm \
    -v {workspace_dir}:/workspace \
    -e CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" \
    -e CLAUDE_MODEL="claude-sonnet-4-6" \
    csc6052-claude \
    claude -p "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior."
```

Claude Code through DeepSeek's official Anthropic-compatible API is configured as a Claude framework agent with a DeepSeek provider:

```yaml
agents:
  - id: claude-deepseek-v4-pro
    framework: claude
    model: deepseek-v4-pro[1m]
    env:
      CLAUDE_PROVIDER: deepseek
      DEEPSEEK_API_KEY:
        from_env: DEEPSEEK_API_KEY
```

For this provider, the managed wrapper maps the key to `ANTHROPIC_AUTH_TOKEN`, sets `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and skips automatic proxy forwarding. The Anthropic subscription path still uses `CLAUDE_CODE_OAUTH_TOKEN`.

mini-SWE-agent example:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  --runs-root .agent_runs \
  --framework mini-swe-agent \
  --model deepseek/deepseek-chat \
  --template project-1 \
  --start-stage 1 \
  --end-stage 6 \
  -- \
  podman run --rm -i \
    -v {workspace_dir}:/workspace \
    -e MSWEA_MODEL_NAME="deepseek/deepseek-chat" \
    -e DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
    -e OPENAI_API_BASE="https://api.deepseek.com" \
    -e MSWEA_MODEL_BACKEND="openai-compat" \
    csc6052-mini-swe-agent \
    mini -t "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior."
```

## Resume From A Prior Repo

If you want to continue a trajectory from an existing repo snapshot, pass `--repo-dir` exactly as you would to `run_trajectory.py`. The manager still allocates a fresh canonical run directory for the new attempt.

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  --runs-root .agent_runs \
  --framework mini-swe-agent \
  --model deepseek/deepseek-chat \
  --template project-1 \
  --repo-dir .agent_runs/mini-swe-agent/deepseek__deepseek-chat/project-1/20260415T010000Z/repo \
  --start-stage 4 \
  --end-stage 6 \
  -- \
  podman run --rm -i \
    -v {workspace_dir}:/workspace \
    -e MSWEA_MODEL_NAME="deepseek/deepseek-chat" \
    -e DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
    -e OPENAI_API_BASE="https://api.deepseek.com" \
    -e MSWEA_MODEL_BACKEND="openai-compat" \
    csc6052-mini-swe-agent \
    mini -t "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior."
```

## List And Inspect Runs

List all managed runs:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  list \
  --runs-root .agent_runs
```

Machine-readable listing:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  list \
  --runs-root .agent_runs \
  --json
```

Show one run:

```bash
uv run python -m benchmark.harness.run_managed_trajectory \
  show \
  --run-dir .agent_runs/codex/gpt-5.4/project-1/20260415T020000Z
```

The detail view focuses on trajectory-level information:

- framework, model, template, and run id
- overall status and stage range
- completed stage count and last completed stage
- aggregated agent cost, token totals when available, and whether the total is complete or partial
- repo path, `trajectory.json`, and `run-manifest.json`

## Manifest Contract

Each managed run root contains `run-manifest.json` owned by the manager. It records:

- raw framework/model/template identifiers
- slugged path components
- allocated run directory and shared runs root
- stage range and optional `repo_dir`
- sanitized agent command
- manager status and final exit code
- derived trajectory summary fields such as completed stage count
- aggregated cost fields copied from `trajectory.json`, including `total_agent_cost_usd`, token totals when available, and coverage flags like `cost_complete`
- optional experiment metadata: `experiment_id`, `agent_id`, and `repeat_index`

The existing harness files such as `trajectory.json`, `stage_0N/stage-result.json`, and evaluator logs remain unchanged apart from the new benchmark-owned cost summary fields.
