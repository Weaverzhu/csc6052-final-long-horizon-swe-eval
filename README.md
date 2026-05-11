# Reproduce

Run all commands from the repository root.

## Setup

```bash
uv sync
uv run pytest tests
docker build -t csc6052-project-1-evaluator docker/evaluator
```

For Podman:

```bash
export CONTAINER_RUNTIME=podman
export BENCHMARK_CONTAINER_RUNTIME=podman
```

## Preview Runs

```bash
API_KEY=dry-run-only \
uv run python -m benchmark.harness.run_experiment run --config config.yaml --dry-run
```

## Credentials

Default `config.yaml` needs:

```bash
export API_KEY=<deepseek-api-key>
test -f "$HOME/.codex/auth.json"
```

To reduce cost, edit `config.yaml` to keep fewer agents/projects or set a smaller
`end_stage`.

## Run Experiment

```bash
uv run python -m benchmark.harness.run_experiment run --config config.yaml
```

Outputs:

```text
.agent_runs/<framework>/<model>/<project>/<run_id>/
.agent_outputs/csc6052-final-main-results.md
.agent_outputs/csc6052-final-main-summary.json
```

## Rebuild Summary Only

```bash
uv run python -m benchmark.harness.run_experiment summary --config config.yaml
```

## Evaluate One Submission

```bash
uv run python -m benchmark.harness.evaluate_repo \
  --template project-3 \
  --stage 3 \
  --repo-dir /path/to/submission-repo \
  --results-dir /tmp/project-3-eval-stage-03
```

Do not use the benchmark repository root as `--repo-dir`.
