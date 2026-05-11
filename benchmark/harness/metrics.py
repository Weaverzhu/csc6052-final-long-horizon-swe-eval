from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


STAGE_RE = re.compile(r"stage_(\d{2})")


def stage_weight(stage_number: int, total_stages: int) -> float:
    if total_stages <= 0:
        raise ValueError("total_stages must be positive")
    if stage_number <= 0:
        raise ValueError("stage_number must be positive")
    return stage_number / sum(range(1, total_stages + 1))


def _testcase_stage(testcase: ET.Element) -> int | None:
    search_text = " ".join(
        value
        for value in (
            testcase.get("file"),
            testcase.get("classname"),
            testcase.get("name"),
        )
        if value
    )
    match = STAGE_RE.search(search_text)
    if match is None:
        return None
    return int(match.group(1))


def _is_failed_testcase(testcase: ET.Element) -> bool:
    return testcase.find("failure") is not None or testcase.find("error") is not None


def _is_skipped_testcase(testcase: ET.Element) -> bool:
    return testcase.find("skipped") is not None


def _bucket_for_testcase(testcase: ET.Element, *, checkpoint_stage: int) -> str:
    testcase_stage = _testcase_stage(testcase)
    if testcase_stage is not None and testcase_stage < checkpoint_stage:
        return "regression"
    if "regression" in (testcase.get("name") or "").lower():
        return "regression"
    return "current"


def parse_pytest_junit(
    junit_path: Path,
    *,
    checkpoint_stage: int,
) -> dict[str, Any]:
    """Summarize a pytest JUnit XML file for correctness scoring."""
    if not junit_path.exists():
        return {
            "available": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": None,
            "current": _empty_bucket(),
            "regression": _empty_bucket(),
        }

    root = ET.parse(junit_path).getroot()
    testcases = list(root.iter("testcase"))
    buckets = {
        "current": _empty_bucket(),
        "regression": _empty_bucket(),
    }

    for testcase in testcases:
        bucket = buckets[_bucket_for_testcase(testcase, checkpoint_stage=checkpoint_stage)]
        bucket["total"] += 1
        if _is_skipped_testcase(testcase):
            bucket["skipped"] += 1
        elif _is_failed_testcase(testcase):
            bucket["failed"] += 1
        else:
            bucket["passed"] += 1

    summary = _combine_buckets(buckets["current"], buckets["regression"])
    summary["available"] = True
    summary["current"] = _finalize_bucket(buckets["current"])
    summary["regression"] = _finalize_bucket(buckets["regression"])
    return _finalize_bucket(summary)


def _empty_bucket() -> dict[str, Any]:
    return {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "pass_rate": None,
    }


def _combine_buckets(*buckets: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": sum(int(bucket["total"]) for bucket in buckets),
        "passed": sum(int(bucket["passed"]) for bucket in buckets),
        "failed": sum(int(bucket["failed"]) for bucket in buckets),
        "skipped": sum(int(bucket["skipped"]) for bucket in buckets),
    }


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    total = int(bucket["total"])
    bucket["pass_rate"] = None if total == 0 else int(bucket["passed"]) / total
    return bucket


def compute_trajectory_scores(
    stage_results: list[dict[str, Any]],
    *,
    start_stage: int,
    end_stage: int,
    total_stages: int,
) -> dict[str, Any]:
    """Compute weighted single-agent trajectory correctness metrics."""
    stage_by_number = {
        int(stage_result["stage"]): stage_result for stage_result in stage_results
    }
    requested_stage_numbers = list(range(start_stage, end_stage + 1))
    per_stage: list[dict[str, Any]] = []
    weighted_cumulative_correctness = 0.0
    weighted_current_stage_correctness = 0.0
    weighted_regression_stability = 0.0
    strict_trajectory_pass = 1
    regression_introduction_count = 0
    previous_regression_pass_rate: float | None = None

    for stage_number in requested_stage_numbers:
        weight = stage_weight(stage_number, total_stages)
        stage_result = stage_by_number.get(stage_number)
        summary = _dict_or_empty(
            stage_result.get("test_summary") if stage_result is not None else None
        )
        active_pass_rate = _rate_or_zero(summary.get("pass_rate"))
        current_pass_rate = _rate_or_zero(
            (summary.get("current") or {}).get("pass_rate")
        )
        regression_rate = (summary.get("regression") or {}).get("pass_rate")
        regression_pass_rate = _rate_or_zero(regression_rate)

        weighted_cumulative_correctness += weight * active_pass_rate
        weighted_current_stage_correctness += weight * current_pass_rate
        weighted_regression_stability += weight * regression_pass_rate
        if active_pass_rate < 1.0:
            strict_trajectory_pass = 0
        if (
            regression_rate is not None
            and previous_regression_pass_rate is not None
            and previous_regression_pass_rate == 1.0
            and regression_pass_rate < 1.0
        ):
            regression_introduction_count += 1
        if regression_rate is not None:
            previous_regression_pass_rate = regression_pass_rate

        per_stage.append(
            {
                "stage": stage_number,
                "weight": weight,
                "active_pass_rate": active_pass_rate,
                "current_stage_pass_rate": current_pass_rate,
                "regression_pass_rate": regression_rate,
                "attempted": stage_result is not None,
            }
        )

    final_stage_result = stage_by_number.get(end_stage)
    final_summary = _dict_or_empty(
        final_stage_result.get("test_summary")
        if final_stage_result is not None
        else None
    )
    return {
        "weighted_cumulative_correctness": weighted_cumulative_correctness * 100,
        "final_checkpoint_correctness": final_summary.get("pass_rate", 0.0),
        "strict_trajectory_pass": strict_trajectory_pass,
        "weighted_current_stage_correctness": weighted_current_stage_correctness * 100,
        "weighted_regression_stability": weighted_regression_stability * 100,
        "regression_introduction_count": regression_introduction_count,
        "stage_weights": {
            str(stage_number): stage_weight(stage_number, total_stages)
            for stage_number in requested_stage_numbers
        },
        "stage_correctness": per_stage,
    }


def _rate_or_zero(value: object) -> float:
    if value is None:
        return 0.0
    return float(value)


def _dict_or_empty(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
