from __future__ import annotations

from pathlib import Path

from benchmark.harness.metrics import compute_trajectory_scores, parse_pytest_junit


def test_parse_pytest_junit_summarizes_current_and_regression_tests(tmp_path: Path) -> None:
    junit_path = tmp_path / "pytest-junit.xml"
    junit_path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4" failures="1" errors="0" skipped="1">
    <testcase classname="evaluation.project_1.stage_03.hidden_tests" name="test_new_feature" />
    <testcase classname="evaluation.project_1.stage_03.hidden_tests" name="test_stage_02_regression_summary">
      <failure message="failed">assert 1 == 2</failure>
    </testcase>
    <testcase classname="evaluation.project_1.stage_01.hidden_tests" name="test_old_behavior" />
    <testcase classname="evaluation.project_1.stage_03.hidden_tests" name="test_optional">
      <skipped message="skip" />
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    summary = parse_pytest_junit(junit_path, checkpoint_stage=3)

    assert summary["available"] is True
    assert summary["total"] == 4
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["skipped"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["current"]["total"] == 2
    assert summary["current"]["pass_rate"] == 0.5
    assert summary["regression"]["total"] == 2
    assert summary["regression"]["pass_rate"] == 0.5


def test_compute_trajectory_scores_weights_later_stages_more() -> None:
    stage_results = [
        {
            "stage": 1,
            "test_summary": {
                "pass_rate": 1.0,
                "current": {"pass_rate": 1.0},
                "regression": {"pass_rate": None},
            },
        },
        {
            "stage": 2,
            "test_summary": {
                "pass_rate": 0.5,
                "current": {"pass_rate": 1.0},
                "regression": {"pass_rate": 0.0},
            },
        },
        {
            "stage": 3,
            "test_summary": {
                "pass_rate": 1.0,
                "current": {"pass_rate": 1.0},
                "regression": {"pass_rate": 1.0},
            },
        },
    ]

    scores = compute_trajectory_scores(
        stage_results,
        start_stage=1,
        end_stage=3,
        total_stages=3,
    )

    assert scores["stage_weights"] == {"1": 1 / 6, "2": 2 / 6, "3": 3 / 6}
    assert scores["weighted_cumulative_correctness"] == 83.33333333333333
    assert scores["final_checkpoint_correctness"] == 1.0
    assert scores["strict_trajectory_pass"] == 0
    assert scores["weighted_current_stage_correctness"] == 100.0
    assert scores["weighted_regression_stability"] == 50.0


def test_compute_trajectory_scores_treats_unattempted_late_stages_as_zero() -> None:
    scores = compute_trajectory_scores(
        [
            {
                "stage": 1,
                "test_summary": {
                    "pass_rate": 1.0,
                    "current": {"pass_rate": 1.0},
                    "regression": {"pass_rate": None},
                },
            }
        ],
        start_stage=1,
        end_stage=3,
        total_stages=3,
    )

    assert scores["weighted_cumulative_correctness"] == 100 * (1 / 6)
    assert scores["final_checkpoint_correctness"] == 0.0
    assert scores["strict_trajectory_pass"] == 0
    assert scores["stage_correctness"][2]["attempted"] is False
