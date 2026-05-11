from __future__ import annotations

from evaluation.project_3.common import assert_success, load_json_output, seed_basic_catalog


def test_validate_reports_prerequisite_and_corequisite_issues(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("rule", "set", "--course", "CS102", "--prereq", "CS101"))
    assert_success(project.run_cli("rule", "set", "--course", "MATH201", "--coreq", "CS101"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS102", "--section", "B"))
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A"))

    payload = load_json_output(project.run_cli("validate", "--format", "json"))
    assert payload["valid"] is False
    assert payload["issues"] == [
        {
            "type": "corequisite",
            "course": "MATH201",
            "section": "A",
            "required_courses": ["CS101"],
        },
        {
            "type": "prerequisite",
            "course": "CS102",
            "section": "B",
            "required_courses": ["CS101"],
        },
    ]


def test_validate_reports_credit_limit_issue(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("credits", "set", "--min", "3", "--max", "3"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A"))

    payload = load_json_output(project.run_cli("validate", "--format", "json"))
    assert payload["valid"] is False
    assert payload["issues"] == [
        {
            "type": "credit_limit",
            "actual_credits": 7,
            "min_credits": 3,
            "max_credits": 3,
        }
    ]


def test_validate_returns_valid_true_with_empty_issues_for_valid_schedule(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))

    payload = load_json_output(project.run_cli("validate", "--format", "json"))
    assert payload == {"valid": True, "issues": []}
