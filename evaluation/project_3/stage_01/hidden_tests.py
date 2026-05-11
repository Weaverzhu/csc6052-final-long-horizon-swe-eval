from __future__ import annotations

from evaluation.project_3.common import (
    assert_failure,
    assert_success,
    load_json_output,
    section_record,
)


def test_submission_uses_uv_managed_package_layout(project) -> None:
    project.assert_submission_contract()


def test_add_course_section_and_schedule_persists_across_processes(project) -> None:
    assert_success(
        project.run_cli(
            "course",
            "add",
            "--code",
            "CS101",
            "--title",
            "Intro Programming",
            "--credits",
            "3",
        )
    )
    assert_success(
        project.run_cli(
            "section",
            "add",
            "--course",
            "CS101",
            "--section",
            "A",
            "--days",
            "MW",
            "--start",
            "09:00",
            "--end",
            "10:15",
        )
    )
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))

    payload = load_json_output(project.run_cli("schedule", "list", "--format", "json"))
    assert payload == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
            start="09:00",
            end="10:15",
        )
    ]


def test_section_list_returns_available_sections(project) -> None:
    assert_success(
        project.run_cli(
            "course",
            "add",
            "--code",
            "MATH201",
            "--title",
            "Linear Algebra",
            "--credits",
            "4",
        )
    )
    assert_success(
        project.run_cli(
            "section",
            "add",
            "--course",
            "MATH201",
            "--section",
            "B",
            "--days",
            "TR",
            "--start",
            "11:00",
            "--end",
            "12:15",
        )
    )

    payload = load_json_output(
        project.run_cli("section", "list", "--course", "MATH201", "--format", "json")
    )
    assert payload == [
        section_record(
            course="MATH201",
            section="B",
            days="TR",
            start="11:00",
            end="12:15",
        )
    ]


def test_invalid_time_fails_cleanly(project) -> None:
    result = project.run_cli(
        "section",
        "add",
        "--course",
        "CS404",
        "--section",
        "A",
        "--days",
        "MW",
        "--start",
        "25:00",
        "--end",
        "26:00",
    )
    assert_failure(result)
