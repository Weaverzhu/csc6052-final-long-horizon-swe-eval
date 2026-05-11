from __future__ import annotations

from pathlib import Path
import json

from benchmark.harness.run_managed_trajectory import build_run_manifest
from benchmark.harness.run_trajectory import run_trajectory
from benchmark.templates import TEMPLATES, get_template


def test_registry_exposes_all_five_templates() -> None:
    assert set(TEMPLATES) == {
        "project-1",
        "project-2",
        "project-3",
        "project-4",
        "project-5",
    }
    assert get_template("project-2").display_name == "Text Analyzer"
    assert get_template("project-3").display_name == "Course Planner"
    assert get_template("project-4").display_name == "Knowledge Base Manager"
    assert get_template("project-5").display_name == "Configuration Policy Manager"


def test_templates_report_max_stage() -> None:
    assert get_template("project-1").max_stage == 6
    assert get_template("project-2").max_stage == 6
    assert get_template("project-3").max_stage == 6
    assert get_template("project-4").max_stage == 6
    assert get_template("project-5").max_stage == 6


def test_stages_default_to_stage_local_evaluation_paths() -> None:
    stage = get_template("project-1").get_stage(5)
    assert stage.evaluation_paths == (stage.evaluation_path,)


def test_run_trajectory_uses_template_max_stage_when_end_stage_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    captured: list[int] = []

    def fake_run_stage(*, template, stage, repo_dir, results_dir, command):
        from benchmark.harness.common import StageRunResult

        captured.append(stage.number)
        return StageRunResult(
            template=template.slug,
            stage=stage.number,
            stage_id=stage.stage_id,
            workspace_dir=results_dir / "workspace",
            workspace_repo_dir=results_dir / "workspace" / "repo",
            workspace_task_dir=results_dir / "workspace" / "task",
            task_dir=results_dir / "workspace" / "task",
            prompt_path=template.get_stage(stage.number).prompt_path,
            results_dir=results_dir,
            repo_dir=repo_dir,
            agent_command=list(command),
            agent_cost={
                "total_cost_usd": 0.5,
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "observed_cost_artifact_count": 1,
                "is_complete": True,
            },
            agent_exit_code=0,
            evaluation_exit_code=0,
        )

    monkeypatch.setattr("benchmark.harness.run_trajectory.run_stage", fake_run_stage)

    exit_code = run_trajectory(
        template_slug="project-2",
        results_dir=tmp_path / "results",
        command=["demo-agent"],
    )

    assert exit_code == 0
    assert captured == [1, 2, 3, 4, 5, 6]
    trajectory = json.loads((tmp_path / "results" / "trajectory.json").read_text(encoding="utf-8"))
    assert trajectory["total_agent_cost_usd"] == 3.0
    assert trajectory["cost_complete"] is True


def test_build_run_manifest_accepts_dynamic_end_stage() -> None:
    manifest = build_run_manifest(
        runs_root=Path("/tmp/runs"),
        run_dir=Path("/tmp/runs/codex/gpt-5.4/project-2/20260415T000000Z"),
        run_id="20260415T000000Z",
        framework="codex",
        framework_slug="codex",
        model="gpt-5.4",
        model_slug="gpt-5.4",
        template="project-2",
        template_slug="project-2",
        start_stage=1,
        end_stage=get_template("project-2").max_stage,
        repo_dir=None,
        command=["demo-agent"],
    )

    assert manifest["end_stage"] == 6
