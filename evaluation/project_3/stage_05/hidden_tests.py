from __future__ import annotations

from evaluation.project_3.common import (
    assert_success,
    load_json_output,
    seed_basic_catalog,
)


def test_recommend_returns_feasible_plan_under_credit_cap(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("rule", "set", "--course", "CS102", "--prereq", "CS101"))
    payload = load_json_output(
        project.run_cli(
            "recommend",
            "--completed",
            "CS101",
            "--max-credits",
            "4",
            "--format",
            "json",
        )
    )

    assert payload["valid"] is True
    assert payload["total_credits"] <= 4
    assert payload["schedule"] == sorted(
        payload["schedule"],
        key=lambda item: (item["course"], item["section"]),
    )
    credits_by_course = {"CS101": 3, "CS102": 3, "MATH201": 4}
    assert payload["total_credits"] == sum(
        credits_by_course[item["course"]] for item in payload["schedule"]
    )
    courses = {item["course"] for item in payload["schedule"]}
    assert "CS102" in courses or "MATH201" in courses
    stored = load_json_output(project.run_cli("schedule", "list", "--format", "json"))
    assert stored == []


def test_recommend_respects_prerequisite_constraints(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("rule", "set", "--course", "CS102", "--prereq", "CS101"))
    payload = load_json_output(project.run_cli("recommend", "--max-credits", "6", "--format", "json"))
    courses = {item["course"] for item in payload["schedule"]}
    assert "CS102" not in courses


def test_recommend_returns_explicit_invalid_empty_plan_when_no_schedule_fits(project) -> None:
    seed_basic_catalog(project)
    payload = load_json_output(project.run_cli("recommend", "--max-credits", "2", "--format", "json"))
    assert payload == {"schedule": [], "total_credits": 0, "valid": False}
