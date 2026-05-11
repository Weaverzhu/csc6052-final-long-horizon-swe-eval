from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark.harness import run_managed_trajectory as managed_cli
from benchmark.harness.common import write_json_artifact


def test_allocate_run_dir_uses_canonical_layout_and_handles_collisions(tmp_path: Path) -> None:
    now = datetime(2026, 4, 15, 12, 30, 0, tzinfo=timezone.utc)
    first_run_id, first_run_dir, components = managed_cli.allocate_run_dir(
        runs_root=tmp_path,
        framework="mini-swe-agent",
        model="deepseek/deepseek-chat",
        template="project-1",
        now=now,
    )
    first_run_dir.mkdir(parents=True)

    second_run_id, second_run_dir, _ = managed_cli.allocate_run_dir(
        runs_root=tmp_path,
        framework="mini-swe-agent",
        model="deepseek/deepseek-chat",
        template="project-1",
        now=now,
    )

    assert components == {
        "framework": "mini-swe-agent",
        "model": "deepseek__deepseek-chat",
        "template": "project-1",
    }
    assert first_run_id == "20260415T123000Z"
    assert second_run_id == "20260415T123000Z-01"
    assert second_run_dir.parent == first_run_dir.parent


def test_run_managed_trajectory_writes_and_updates_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    runs_root = tmp_path / "runs"

    def fake_run_trajectory(
        *,
        template_slug,
        results_dir,
        command,
        repo_dir,
        start_stage,
        end_stage,
    ):
        manifest = json.loads(
            (results_dir / managed_cli.RUN_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        assert manifest["status"] == "running"
        assert manifest["agent_command"] == [
            "podman",
            "run",
            "-e",
            "OPENAI_API_KEY=<redacted>",
            "demo-image",
        ]
        write_json_artifact(
            results_dir / "trajectory.json",
            {
                "template": template_slug,
                "repo_dir": str(results_dir / "repo"),
                "start_stage": start_stage,
                "end_stage": end_stage,
                "total_agent_cost_usd": 0.75,
                "cost_stage_count": 1,
                "missing_cost_stage_count": 0,
                "cost_complete": True,
                "stages": [
                    {
                        "stage_id": "stage_01",
                        "agent_exit_code": 0,
                        "evaluation_exit_code": 0,
                    }
                ],
            },
        )
        return 0

    monkeypatch.setattr(managed_cli, "run_trajectory", fake_run_trajectory)

    exit_code = managed_cli.run_managed_trajectory(
        runs_root=runs_root,
        framework="mini-swe-agent",
        model="deepseek/deepseek-chat",
        template="project-1",
        command=["--", "podman", "run", "-e", "OPENAI_API_KEY=secret", "demo-image"],
        experiment_id="exp-1",
        agent_id="mini-ds",
        repeat_index=2,
    )

    assert exit_code == 0
    manifest_paths = list(runs_root.glob(f"*/*/*/*/{managed_cli.RUN_MANIFEST_NAME}"))
    assert len(manifest_paths) == 1

    manifest = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
    assert manifest["framework"] == "mini-swe-agent"
    assert manifest["model"] == "deepseek/deepseek-chat"
    assert manifest["template"] == "project-1"
    assert manifest["status"] == "passed"
    assert manifest["exit_code"] == 0
    assert manifest["completed_stage_count"] == 1
    assert manifest["last_stage_id"] == "stage_01"
    assert manifest["total_agent_cost_usd"] == 0.75
    assert manifest["cost_complete"] is True
    assert manifest["experiment_id"] == "exp-1"
    assert manifest["agent_id"] == "mini-ds"
    assert manifest["repeat_index"] == 2


def test_run_managed_trajectory_marks_failures_in_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    runs_root = tmp_path / "runs"

    def fake_run_trajectory(**kwargs):
        raise SystemExit(9)

    monkeypatch.setattr(managed_cli, "run_trajectory", fake_run_trajectory)

    exit_code = managed_cli.run_managed_trajectory(
        runs_root=runs_root,
        framework="codex",
        model="gpt-5.4",
        template="project-1",
        command=["docker", "run", "demo-image"],
    )

    assert exit_code == 9
    manifest_path = next(runs_root.glob(f"*/*/*/*/{managed_cli.RUN_MANIFEST_NAME}"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["exit_code"] == 9


def test_list_command_reports_runs_and_incomplete_states(
    tmp_path: Path, capsys
) -> None:
    runs_root = tmp_path / "runs"

    incomplete_dir = runs_root / "mini-swe-agent" / "deepseek__deepseek-chat" / "project-1" / "20260415T010000Z"
    incomplete_dir.mkdir(parents=True)
    write_json_artifact(
        incomplete_dir / managed_cli.RUN_MANIFEST_NAME,
        {
            "framework": "mini-swe-agent",
            "model": "deepseek/deepseek-chat",
            "template": "project-1",
            "run_id": "20260415T010000Z",
            "start_stage": 1,
            "end_stage": 6,
            "status": "running",
        },
    )

    passed_dir = runs_root / "codex" / "gpt-5.4" / "project-1" / "20260415T020000Z"
    passed_dir.mkdir(parents=True)
    write_json_artifact(
        passed_dir / managed_cli.RUN_MANIFEST_NAME,
        {
            "framework": "codex",
            "model": "gpt-5.4",
            "template": "project-1",
            "run_id": "20260415T020000Z",
            "start_stage": 1,
            "end_stage": 3,
            "status": "passed",
        },
    )
    write_json_artifact(
        passed_dir / "trajectory.json",
        {
            "template": "project-1",
            "repo_dir": str(passed_dir / "repo"),
            "start_stage": 1,
            "end_stage": 3,
            "total_agent_cost_usd": 1.5,
            "cost_stage_count": 1,
            "missing_cost_stage_count": 0,
            "cost_complete": True,
            "stages": [{"stage_id": "stage_03"}],
        },
    )

    exit_code = managed_cli.main(["list", "--runs-root", str(runs_root), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    statuses = {run["run_id"]: run["status"] for run in payload["runs"]}
    assert statuses["20260415T010000Z"] == "incomplete"
    assert statuses["20260415T020000Z"] == "passed"
    costs = {run["run_id"]: run["total_agent_cost_usd"] for run in payload["runs"]}
    assert costs["20260415T020000Z"] == 1.5


def test_parse_args_defaults_to_run_subcommand() -> None:
    args = managed_cli.parse_args(
        [
            "--runs-root",
            "/tmp/runs",
            "--framework",
            "codex",
            "--model",
            "gpt-5.4",
            "--",
            "docker",
            "run",
            "demo-image",
        ]
    )

    assert args.subcommand == "run"
    assert args.command == ["docker", "run", "demo-image"]


def test_render_run_detail_includes_cost_fields() -> None:
    detail = managed_cli.render_run_detail(
        {
            "run_dir": "/tmp/run",
            "framework": "codex",
            "model": "gpt-5.4",
            "template": "project-1",
            "run_id": "20260415T020000Z",
            "status": "passed",
            "start_stage": 1,
            "end_stage": 6,
            "completed_stage_count": 6,
            "total_agent_cost_usd": 2.5,
            "cost_complete": False,
            "cost_stage_count": 5,
            "missing_cost_stage_count": 1,
            "trajectory_path": "/tmp/run/trajectory.json",
            "run_manifest_path": "/tmp/run/run-manifest.json",
        }
    )

    assert "total_agent_cost_usd: 2.5" in detail
    assert "cost_complete: False" in detail
    assert "missing_cost_stage_count: 1" in detail
