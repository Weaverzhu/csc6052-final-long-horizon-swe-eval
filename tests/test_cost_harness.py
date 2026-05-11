from __future__ import annotations

import json
from pathlib import Path

from benchmark.harness.cost import (
    aggregate_trajectory_costs,
    summarize_cost_json,
    summarize_workspace_cost,
)


def test_summarize_cost_json_prefers_top_level_summary(tmp_path: Path) -> None:
    artifact_path = tmp_path / "trajectory.traj.json"
    artifact_path.write_text(
        json.dumps(
            {
                "provider": "openrouter",
                "model": "demo-model",
                "usage": {"prompt_tokens": 111, "completion_tokens": 22},
                "summary": {
                    "total_cost_usd": 0.125,
                    "input_tokens": 120,
                    "output_tokens": 30,
                },
                "turns": [
                    {"cost_usd": 0.06, "prompt_tokens": 50, "completion_tokens": 10},
                    {"cost_usd": 0.065, "prompt_tokens": 70, "completion_tokens": 20},
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_cost_json(artifact_path)

    assert summary["is_complete"] is True
    assert summary["total_cost_usd"] == 0.125
    assert summary["input_tokens"] == 120
    assert summary["output_tokens"] == 30
    assert summary["selected_path"] == "$.summary"


def test_summarize_cost_json_marks_token_only_artifact_incomplete(tmp_path: Path) -> None:
    artifact_path = tmp_path / "trajectory.traj.json"
    artifact_path.write_text(
        json.dumps({"usage": {"prompt_tokens": 15, "completion_tokens": 5}}),
        encoding="utf-8",
    )

    summary = summarize_cost_json(artifact_path)

    assert summary["is_complete"] is False
    assert summary["total_cost_usd"] == 0.0
    assert summary["input_tokens"] == 15
    assert summary["output_tokens"] == 5
    assert "no total cost" in summary["missing_reason"]


def test_summarize_workspace_cost_aggregates_artifacts(tmp_path: Path) -> None:
    artifact_dir = tmp_path / ".agent-results" / "mini" / "latest"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "trajectory.traj.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total_cost_usd": 0.25,
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_workspace_cost(tmp_path)

    assert summary["artifact_count"] == 1
    assert summary["observed_cost_artifact_count"] == 1
    assert summary["missing_cost_artifact_count"] == 0
    assert summary["is_complete"] is True
    assert summary["total_cost_usd"] == 0.25
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 50
    assert summary["total_tokens"] == 150
    assert summary["artifacts"][0]["backend"] == "mini"


def test_aggregate_trajectory_costs_tracks_partial_coverage() -> None:
    aggregated = aggregate_trajectory_costs(
        [
            {
                "stage_id": "stage_01",
                "agent_cost": {
                    "total_cost_usd": 0.25,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "observed_cost_artifact_count": 1,
                    "is_complete": True,
                },
            },
            {
                "stage_id": "stage_02",
                "agent_cost": {
                    "total_cost_usd": 0.0,
                    "input_tokens": 50,
                    "output_tokens": None,
                    "total_tokens": None,
                    "observed_cost_artifact_count": 0,
                    "is_complete": False,
                },
            },
        ]
    )

    assert aggregated["total_agent_cost_usd"] == 0.25
    assert aggregated["cost_stage_count"] == 1
    assert aggregated["missing_cost_stage_count"] == 1
    assert aggregated["cost_complete"] is False
    assert aggregated["input_tokens"] == 150
    assert aggregated["output_tokens"] is None
    assert aggregated["total_tokens"] is None
