from __future__ import annotations

from evaluation.project_3.common import (
    assert_success,
    load_json_output,
    section_record,
    seed_basic_catalog,
)


def test_validate_reports_time_conflict(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS102", "--section", "A"))

    payload = load_json_output(project.run_cli("validate", "--format", "json"))
    assert payload == {
        "valid": False,
        "issues": [
            {
                "type": "time_conflict",
                "course": "CS101",
                "section": "A",
                "other_course": "CS102",
                "other_section": "A",
            }
        ],
    }


def test_timetable_returns_selected_meetings(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A"))

    payload = load_json_output(project.run_cli("timetable", "--format", "json"))
    assert payload == [
        section_record(
            course="MATH201",
            section="A",
            days="TR",
            start="09:00",
            end="10:15",
        )
    ]


def test_timetable_sorts_multiple_entries(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS102", "--section", "B"))
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))

    payload = load_json_output(project.run_cli("timetable", "--format", "json"))
    assert payload == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
            start="09:00",
            end="10:15",
        ),
        section_record(
            course="MATH201",
            section="A",
            days="TR",
            start="09:00",
            end="10:15",
        ),
        section_record(
            course="CS102",
            section="B",
            days="TR",
            start="11:00",
            end="12:15",
        ),
    ]


def test_validate_allows_back_to_back_classes(project) -> None:
    assert_success(project.run_cli("course", "add", "--code", "CS201", "--title", "A", "--credits", "3"))
    assert_success(project.run_cli("course", "add", "--code", "CS202", "--title", "B", "--credits", "3"))
    assert_success(
        project.run_cli(
            "section",
            "add",
            "--course",
            "CS201",
            "--section",
            "A",
            "--days",
            "MW",
            "--start",
            "09:00",
            "--end",
            "10:00",
        )
    )
    assert_success(
        project.run_cli(
            "section",
            "add",
            "--course",
            "CS202",
            "--section",
            "A",
            "--days",
            "M",
            "--start",
            "10:00",
            "--end",
            "11:00",
        )
    )
    assert_success(project.run_cli("schedule", "add", "--course", "CS201", "--section", "A"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS202", "--section", "A"))

    payload = load_json_output(project.run_cli("validate", "--format", "json"))
    assert payload == {"valid": True, "issues": []}
