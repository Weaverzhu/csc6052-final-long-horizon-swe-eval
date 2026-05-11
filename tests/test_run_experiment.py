from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.harness import run_experiment
from benchmark.harness.common import write_json_artifact
from benchmark.harness.run_managed_trajectory import RUN_MANIFEST_NAME


def write_config(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_resolves_env_refs_and_expands_matrix(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "config.yaml",
        """
experiment_id: exp-1
runs_root: runs
output_dir: outputs
default_runs_per_project: 2
output:
  stdout: logs/{agent_id}/stdout.log
  stderr: discard
agents:
  - id: codex-gpt55
    framework: codex
    model: gpt-5.5
    env:
      CODEX_HOME:
        from_env: CODEX_HOME
        default: ~/.codex
projects:
  - slug: project-1
  - slug: project-2
    runs_per_project: 1
    end_stage: 3
""",
    )

    config = run_experiment.load_config(
        config_path,
        environ={},
    )
    matrix = run_experiment.build_run_matrix(config)

    assert config.runs_root == tmp_path / "runs"
    assert config.output_dir == tmp_path / "outputs"
    assert config.stdout == "logs/{agent_id}/stdout.log"
    assert config.stderr == "discard"
    assert config.agents[0].env == {"CODEX_HOME": "~/.codex"}
    assert [(item.project.slug, item.repeat_index) for item in matrix] == [
        ("project-1", 1),
        ("project-1", 2),
        ("project-2", 1),
    ]
    assert matrix[-1].project.end_stage == 3


def test_load_config_env_default_can_be_overridden(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "config.yaml",
        """
experiment_id: exp-1
agents:
  - id: codex-gpt55
    framework: codex
    model: gpt-5.5
    env:
      CODEX_HOME:
        from_env: CODEX_HOME
        default: ~/.codex
projects:
  - project-1
""",
    )

    config = run_experiment.load_config(
        config_path,
        environ={"CODEX_HOME": "/tmp/custom-codex"},
    )

    assert config.agents[0].env == {"CODEX_HOME": "/tmp/custom-codex"}


def test_load_config_rejects_missing_env_ref(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "config.yaml",
        """
experiment_id: exp-1
agents:
  - id: mini-ds
    framework: mini-swe-agent
    model: deepseek-v4-flash
    env:
      API_KEY:
        from_env: DEEPSEEK_API_KEY
projects:
  - project-1
""",
    )

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        run_experiment.load_config(config_path, environ={})


def test_load_config_supports_turning_output_off(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "config.yaml",
        """
experiment_id: exp-1
output: false
agents:
  - id: codex-gpt55
    framework: codex
    model: gpt-5.5
projects:
  - project-1
""",
    )

    config = run_experiment.load_config(config_path, environ={})

    assert config.stdout == "discard"
    assert config.stderr == "discard"


def test_build_run_environment_sets_wrapper_inputs(tmp_path: Path) -> None:
    planned_run = run_experiment.PlannedRun(
        experiment_id="exp-1",
        runs_root=tmp_path / "runs",
        agent=run_experiment.AgentConfig(
            agent_id="claude-sonnet",
            framework="claude",
            model="claude-sonnet-4-6",
            env={"CLAUDE_CODE_OAUTH_TOKEN": "token"},
        ),
        project=run_experiment.ProjectConfig(
            slug="project-3",
            runs_per_project=4,
            start_stage=1,
            end_stage=6,
        ),
        repeat_index=2,
    )

    env = run_experiment.build_run_environment(planned_run, base_env={"PATH": "/bin"})

    assert env["FRAMEWORK"] == "claude"
    assert env["MODEL"] == "claude-sonnet-4-6"
    assert env["TEMPLATE"] == "project-3"
    assert env["EXPERIMENT_ID"] == "exp-1"
    assert env["AGENT_ID"] == "claude-sonnet"
    assert env["REPEAT_INDEX"] == "2"
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "token"


def test_execute_run_redirects_stdout_and_stderr_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planned_run = run_experiment.PlannedRun(
        experiment_id="exp-1",
        runs_root=tmp_path / "runs",
        agent=run_experiment.AgentConfig(
            agent_id="mini-ds",
            framework="mini-swe-agent",
            model="deepseek-v4-flash",
            env={},
        ),
        project=run_experiment.ProjectConfig(
            slug="project-1",
            runs_per_project=1,
            start_stage=1,
            end_stage=6,
        ),
        repeat_index=1,
    )
    config = run_experiment.ExperimentConfig(
        experiment_id="exp-1",
        runs_root=tmp_path / "runs",
        agents=(planned_run.agent,),
        projects=(planned_run.project,),
        fail_fast=False,
        stdout="logs/{agent_id}/{project}/stdout.log",
        stderr="logs/{agent_id}/{project}/stderr.log",
    )

    def fake_run(*args, **kwargs):
        kwargs["stdout"].write("agent stdout\n")
        kwargs["stderr"].write("agent stderr\n")
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(run_experiment.subprocess, "run", fake_run)

    exit_code = run_experiment.execute_run(planned_run, config)

    assert exit_code == 0
    assert (
        tmp_path / "runs" / "logs" / "mini-ds" / "project-1" / "stdout.log"
    ).read_text(encoding="utf-8") == "agent stdout\n"
    assert (
        tmp_path / "runs" / "logs" / "mini-ds" / "project-1" / "stderr.log"
    ).read_text(encoding="utf-8") == "agent stderr\n"


def test_execute_run_discards_output_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planned_run = run_experiment.PlannedRun(
        experiment_id="exp-1",
        runs_root=tmp_path / "runs",
        agent=run_experiment.AgentConfig(
            agent_id="mini-ds",
            framework="mini-swe-agent",
            model="deepseek-v4-flash",
            env={},
        ),
        project=run_experiment.ProjectConfig(
            slug="project-1",
            runs_per_project=1,
            start_stage=1,
            end_stage=6,
        ),
        repeat_index=1,
    )
    config = run_experiment.ExperimentConfig(
        experiment_id="exp-1",
        runs_root=tmp_path / "runs",
        agents=(planned_run.agent,),
        projects=(planned_run.project,),
        fail_fast=False,
        stdout="discard",
        stderr="discard",
    )
    observed: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(run_experiment.subprocess, "run", fake_run)

    exit_code = run_experiment.execute_run(planned_run, config)

    assert exit_code == 0
    assert observed["stdout"] == run_experiment.subprocess.DEVNULL
    assert observed["stderr"] == run_experiment.subprocess.DEVNULL


def test_summarize_by_agent_averages_manifest_records(tmp_path: Path) -> None:
    first = tmp_path / "runs" / "codex" / "gpt-5.5" / "project-1" / "run-a"
    second = tmp_path / "runs" / "codex" / "gpt-5.5" / "project-2" / "run-b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    for run_dir, wcc, status, cost_complete in (
        (first, 100.0, "passed", True),
        (second, 50.0, "failed", False),
    ):
        write_json_artifact(
            run_dir / RUN_MANIFEST_NAME,
            {
                "experiment_id": "exp-1",
                "agent_id": "codex-gpt55",
                "framework": "codex",
                "model": "gpt-5.5",
                "template": run_dir.parent.name,
                "run_id": run_dir.name,
                "start_stage": 1,
                "end_stage": 6,
                "status": status,
                "cost_complete": cost_complete,
            },
        )
        write_json_artifact(
            run_dir / "trajectory.json",
            {
                "weighted_cumulative_correctness": wcc,
                "final_checkpoint_correctness": wcc / 100,
                "strict_trajectory_pass": 1 if status == "passed" else 0,
                "weighted_current_stage_correctness": wcc,
                "weighted_regression_stability": 25.0,
                "regression_introduction_count": 1,
                "total_agent_cost_usd": 2.0,
                "cost_complete": cost_complete,
                "stages": [],
            },
        )

    records = run_experiment.filter_experiment_records(
        run_experiment.collect_run_records(tmp_path / "runs"),
        experiment_id="exp-1",
    )
    summary = run_experiment.summarize_by_agent(records)

    assert len(summary) == 1
    assert summary[0]["agent"] == "codex-gpt55"
    assert summary[0]["runs"] == 2
    assert summary[0]["passed_runs"] == 1
    assert summary[0]["avg_weighted_cumulative_correctness"] == 75.0
    assert summary[0]["strict_pass_rate"] == 0.5
    assert summary[0]["avg_cost_usd"] == 2.0
    assert summary[0]["cost_complete_runs"] == 1
    table = run_experiment.render_summary_table(summary)
    assert "| codex-gpt55 | codex | gpt-5.5 | 2 | 1 | 75.00 |" in table


def test_summary_command_writes_summary_artifact(tmp_path: Path, capsys) -> None:
    config_path = write_config(
        tmp_path / "config.yaml",
        """
experiment_id: exp-1
runs_root: runs
output_dir: outputs
agents:
  - id: codex-gpt55
    framework: codex
    model: gpt-5.5
projects:
  - project-1
""",
    )
    run_dir = tmp_path / "runs" / "codex" / "gpt-5.5" / "project-1" / "run-a"
    run_dir.mkdir(parents=True)
    write_json_artifact(
        run_dir / RUN_MANIFEST_NAME,
        {
            "experiment_id": "exp-1",
            "agent_id": "codex-gpt55",
            "framework": "codex",
            "model": "gpt-5.5",
            "template": "project-1",
            "run_id": "run-a",
            "start_stage": 1,
            "end_stage": 6,
            "status": "passed",
        },
    )

    exit_code = run_experiment.main(["summary", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "codex-gpt55" in captured.out
    summary_payload = json.loads(
        (tmp_path / "outputs" / "exp-1-summary.json").read_text(encoding="utf-8")
    )
    assert summary_payload["experiment_id"] == "exp-1"
    assert summary_payload["run_count"] == 1
    table = (tmp_path / "outputs" / "exp-1-results.md").read_text(encoding="utf-8")
    assert "| codex-gpt55 | codex | gpt-5.5 | 1 | 1 |" in table
