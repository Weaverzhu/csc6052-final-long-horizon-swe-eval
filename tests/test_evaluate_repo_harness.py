from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from benchmark.harness import evaluate_repo as evaluate_repo_cli
from benchmark.harness.common import (
    build_evaluation_command,
    copy_repo_tree,
    evaluate_repo,
    prepare_agent_workspace,
    run_stage,
    sanitize_command_for_artifacts,
    sync_repo_back,
)
from benchmark.templates import REPO_ROOT, StageSpec, TemplateSpec, get_template
from evaluation.project_1.conftest import _copy_submission_tree


def test_build_evaluation_command_defaults_to_current_stage_only() -> None:
    template = get_template("project-1")
    stage = template.get_stage(3)

    command = build_evaluation_command(
        template=template,
        stage=stage,
        repo_dir=Path("/tmp/submission"),
        results_dir=Path("/tmp/results"),
    )

    command_text = " ".join(command)
    assert "/benchmark/evaluation/project_1/stage_03/hidden_tests.py" in command_text
    assert "/benchmark/evaluation/project_1/stage_01/hidden_tests.py" not in command_text
    assert "/benchmark/evaluation/project_1/stage_02/hidden_tests.py" not in command_text
    assert "/benchmark/evaluation/project_1/stage_04/hidden_tests.py" not in command_text


def test_sanitize_command_redacts_crs_oai_key() -> None:
    assert sanitize_command_for_artifacts(
        ["docker", "run", "-e", "CRS_OAI_KEY=secret-value", "image"]
    ) == ["docker", "run", "-e", "CRS_OAI_KEY=<redacted>", "image"]


def test_build_evaluation_command_respects_explicit_regression_mapping() -> None:
    evaluation_root = REPO_ROOT / "evaluation" / "project_1"
    stage_01_path = evaluation_root / "stage_01" / "hidden_tests.py"
    stage_03_path = evaluation_root / "stage_03" / "hidden_tests.py"
    stage = StageSpec(
        number=3,
        prompt_path=REPO_ROOT / "tasks" / "project-1" / "stage_03" / "prompt.md",
        evaluation_path=stage_03_path,
        evaluation_paths=(stage_01_path, stage_03_path),
    )
    template = TemplateSpec(
        slug="project-1-custom",
        display_name="Project 1 Custom",
        taskbed_root=REPO_ROOT / "tasks" / "project-1",
        evaluation_root=evaluation_root,
        starter_repo_path=REPO_ROOT / "tasks" / "project-1" / "starter_repo",
        stages=(stage,),
    )

    command = build_evaluation_command(
        template=template,
        stage=stage,
        repo_dir=Path("/tmp/submission"),
        results_dir=Path("/tmp/results"),
    )

    command_text = " ".join(command)
    assert "/benchmark/evaluation/project_1/stage_01/hidden_tests.py" in command_text
    assert "/benchmark/evaluation/project_1/stage_03/hidden_tests.py" in command_text
    assert "/benchmark/evaluation/project_1/stage_02/hidden_tests.py" not in command_text


def test_run_command_with_live_output_closes_stdin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from benchmark.harness.common import run_command_with_live_output

    captured: dict[str, object] = {}

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("ok stdout\n")
            self.stderr = io.StringIO("ok stderr\n")

        def wait(self) -> int:
            return 0

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("benchmark.harness.common.subprocess.Popen", fake_popen)

    exit_code, stdout, stderr = run_command_with_live_output(
        command=["demo-command", "--flag"],
        cwd=tmp_path,
    )

    captured_output = capsys.readouterr()
    assert exit_code == 0
    assert stdout == "ok stdout\n"
    assert stderr == "ok stderr\n"
    assert captured_output.out == "ok stdout\n"
    assert captured_output.err == "ok stderr\n"
    assert captured["args"] == (["demo-command", "--flag"],)
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL


def test_evaluate_repo_writes_artifacts_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = get_template("project-1")
    stage = template.get_stage(2)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    captured: dict[str, object] = {}

    def fake_run_command_with_live_output(*, command, cwd):
        captured["command"] = command
        captured["cwd"] = cwd
        return 0, "ok stdout\n", "ok stderr\n"

    monkeypatch.setattr(
        "benchmark.harness.common.run_command_with_live_output",
        fake_run_command_with_live_output,
    )

    result = evaluate_repo(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    assert result.evaluation_exit_code == 0
    assert captured["cwd"] == REPO_ROOT
    assert (results_dir / "evaluation-command.txt").exists()
    assert (results_dir / "evaluation-stdout.txt").read_text(encoding="utf-8") == "ok stdout\n"
    assert (results_dir / "evaluation-stderr.txt").read_text(encoding="utf-8") == "ok stderr\n"
    assert (results_dir / "evaluation-exit-code.txt").read_text(encoding="utf-8") == "0\n"

    metadata = json.loads((results_dir / "evaluation-result.json").read_text(encoding="utf-8"))
    assert metadata["template"] == "project-1"
    assert metadata["stage"] == 2
    assert metadata["stage_id"] == "stage_02"
    assert metadata["repo_dir"] == str(repo_dir.resolve())
    assert metadata["results_dir"] == str(results_dir)
    assert metadata["evaluation_exit_code"] == 0
    assert metadata["test_summary"]["available"] is False


def test_evaluate_repo_cli_returns_evaluation_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    def fake_evaluate_repo(*, template, stage, repo_dir, results_dir):
        from benchmark.harness.common import EvaluationRunResult

        return EvaluationRunResult(
            template=template.slug,
            stage=stage.number,
            stage_id=stage.stage_id,
            results_dir=results_dir,
            repo_dir=repo_dir.resolve(),
            evaluation_exit_code=7,
            test_summary={
                "available": False,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "pass_rate": None,
            },
        )

    monkeypatch.setattr(evaluate_repo_cli, "evaluate_repo", fake_evaluate_repo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_repo.py",
            "--stage",
            "3",
            "--repo-dir",
            str(repo_dir),
            "--results-dir",
            str(results_dir),
        ],
    )

    exit_code = evaluate_repo_cli.main()
    captured = capsys.readouterr()

    assert exit_code == 7
    assert "[FAIL] stage_03" in captured.out


def test_evaluate_repo_rejects_benchmark_root(tmp_path: Path) -> None:
    template = get_template("project-1")
    stage = template.get_stage(1)

    with pytest.raises(ValueError, match="benchmark repository root"):
        evaluate_repo(
            template=template,
            stage=stage,
            repo_dir=REPO_ROOT,
            results_dir=tmp_path / "results",
        )


def test_run_stage_exits_early_when_agent_run_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = get_template("project-1")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    results_dir = tmp_path / "results"

    def fake_run_command_with_live_output(*, command, cwd):
        return 9, "", "agent failed\n"

    def fail_evaluate_repo(**kwargs):
        raise AssertionError("evaluate_repo should not run after an agent failure")

    monkeypatch.setattr(
        "benchmark.harness.common.run_command_with_live_output",
        fake_run_command_with_live_output,
    )
    monkeypatch.setattr("benchmark.harness.common.evaluate_repo", fail_evaluate_repo)

    result = run_stage(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
        command=["/bin/sh", "-lc", "exit 9"],
    )

    assert result.agent_exit_code == 9
    assert result.evaluation_exit_code == 0
    assert not (results_dir / "evaluation-command.txt").exists()
    assert (results_dir / "agent-exit-code.txt").read_text(encoding="utf-8") == "9\n"


def test_run_stage_redacts_sensitive_env_vars_in_artifacts_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = get_template("project-1")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    results_dir = tmp_path / "results"
    captured: dict[str, object] = {}

    def fake_run_command_with_live_output(*, command, cwd):
        captured["command"] = command
        return 9, "", "agent failed\n"

    def fail_evaluate_repo(**kwargs):
        raise AssertionError("evaluate_repo should not run after an agent failure")

    monkeypatch.setattr(
        "benchmark.harness.common.run_command_with_live_output",
        fake_run_command_with_live_output,
    )
    monkeypatch.setattr("benchmark.harness.common.evaluate_repo", fail_evaluate_repo)

    result = run_stage(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
        command=[
            "podman",
            "run",
            "--rm",
            "-e",
            "OPENAI_API_KEY=dummy-secret-value",
            "-e",
            "OPENAI_API_BASE=https://api.openai.com/v1",
            "demo-image",
        ],
    )

    assert result.agent_exit_code == 9
    assert captured["command"] == [
        "podman",
        "run",
        "--rm",
        "-e",
        "OPENAI_API_KEY=dummy-secret-value",
        "-e",
        "OPENAI_API_BASE=https://api.openai.com/v1",
        "demo-image",
    ]

    command_artifact = (results_dir / "agent-command.txt").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=<redacted>" in command_artifact
    assert "dummy-secret-value" not in command_artifact
    assert "OPENAI_API_BASE=https://api.openai.com/v1" in command_artifact

    metadata = json.loads((results_dir / "stage-result.json").read_text(encoding="utf-8"))
    assert metadata["agent_command"] == [
        "podman",
        "run",
        "--rm",
        "-e",
        "OPENAI_API_KEY=<redacted>",
        "-e",
        "OPENAI_API_BASE=https://api.openai.com/v1",
        "demo-image",
    ]


def test_prepare_agent_workspace_seeds_empty_repo_with_starter_repo(tmp_path: Path) -> None:
    template = get_template("project-1")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    _, workspace_repo_dir, _, _ = prepare_agent_workspace(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    assert (repo_dir / "pyproject.toml").exists()
    assert (repo_dir / "finance_tracker" / "__main__.py").exists()
    assert (workspace_repo_dir / "pyproject.toml").exists()
    assert (workspace_repo_dir / "finance_tracker" / "__main__.py").exists()


def test_prepare_agent_workspace_seeds_project_2_starter_repo(tmp_path: Path) -> None:
    template = get_template("project-2")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    _, workspace_repo_dir, _, _ = prepare_agent_workspace(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    assert (repo_dir / "pyproject.toml").exists()
    assert (repo_dir / "text_analyzer" / "__main__.py").exists()
    assert (workspace_repo_dir / "text_analyzer" / "__main__.py").exists()


def test_prepare_agent_workspace_seeds_project_3_starter_repo(tmp_path: Path) -> None:
    template = get_template("project-3")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    _, workspace_repo_dir, _, _ = prepare_agent_workspace(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    assert (repo_dir / "pyproject.toml").exists()
    assert (repo_dir / "course_planner" / "__main__.py").exists()
    assert (workspace_repo_dir / "course_planner" / "__main__.py").exists()


def test_prepare_agent_workspace_stage_01_prompt_clarifies_no_prior_stage(
    tmp_path: Path,
) -> None:
    template = get_template("project-1")
    stage = template.get_stage(1)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    _, _, workspace_task_dir, prompt_path = prepare_agent_workspace(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    assert list((workspace_task_dir / "prior_stage_requirements").iterdir()) == []
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "There is no prior stage for stage 1" in prompt_text
    assert "visible and hidden checks use that exact entry point" in prompt_text


def test_prepare_agent_workspace_later_stage_copies_prior_requirements(
    tmp_path: Path,
) -> None:
    template = get_template("project-1")
    stage = template.get_stage(3)
    repo_dir = tmp_path / "submission"
    repo_dir.mkdir()
    results_dir = tmp_path / "results"

    _, _, workspace_task_dir, prompt_path = prepare_agent_workspace(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    prior_files = sorted(path.name for path in (workspace_task_dir / "prior_stage_requirements").iterdir())
    assert prior_files == ["stage_01.md", "stage_02.md"]
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "Use them to preserve prior behavior" in prompt_text


def test_copy_repo_tree_ignores_runtime_finance_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (source_dir / "finance_data.json").write_text("[]\n", encoding="utf-8")

    copy_repo_tree(source_dir, destination_dir)

    assert (destination_dir / "pyproject.toml").exists()
    assert not (destination_dir / "finance_data.json").exists()


def test_sync_repo_back_ignores_runtime_finance_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    destination_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (source_dir / "finance_data.json").write_text("[]\n", encoding="utf-8")

    sync_repo_back(source_dir, destination_dir)

    assert (destination_dir / "pyproject.toml").exists()
    assert not (destination_dir / "finance_data.json").exists()


def test_copy_repo_tree_ignores_runtime_course_planner_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (source_dir / "course_planner_data.json").write_text("{}\n", encoding="utf-8")

    copy_repo_tree(source_dir, destination_dir)

    assert (destination_dir / "pyproject.toml").exists()
    assert not (destination_dir / "course_planner_data.json").exists()


def test_sync_repo_back_ignores_runtime_course_planner_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    destination_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (source_dir / "course_planner_data.json").write_text("{}\n", encoding="utf-8")

    sync_repo_back(source_dir, destination_dir)

    assert (destination_dir / "pyproject.toml").exists()
    assert not (destination_dir / "course_planner_data.json").exists()


def test_project_fixture_copy_ignores_runtime_finance_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (source_dir / "finance_data.json").write_text("[]\n", encoding="utf-8")

    _copy_submission_tree(source_dir, destination_dir)

    assert (destination_dir / "pyproject.toml").exists()
    assert not (destination_dir / "finance_data.json").exists()
