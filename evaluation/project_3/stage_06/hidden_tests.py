from __future__ import annotations

from evaluation.project_3.common import (
    assert_failure,
    assert_success,
    load_json_output,
    section_record,
    seed_basic_catalog,
)


def test_whatif_drop_reports_validity_without_mutating_schedule(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))

    payload = load_json_output(
        project.run_cli("whatif", "drop", "--course", "CS101", "--format", "json")
    )
    assert payload == {"valid": True, "issues": [], "schedule": []}

    schedule = load_json_output(project.run_cli("schedule", "list", "--format", "json"))
    assert schedule == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
            start="09:00",
            end="10:15",
        )
    ]


def test_whatif_swap_reports_invalid_conflict_without_mutating_schedule(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    assert_success(project.run_cli("schedule", "add", "--course", "CS102", "--section", "B"))

    payload = load_json_output(
        project.run_cli(
            "whatif",
            "swap",
            "--course",
            "CS102",
            "--section",
            "A",
            "--format",
            "json",
        )
    )
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
        "schedule": [
            section_record(
                course="CS101",
                section="A",
                days="MW",
                start="09:00",
                end="10:15",
            ),
            section_record(
                course="CS102",
                section="A",
                days="MW",
                start="09:30",
                end="10:45",
            ),
        ],
    }

    schedule = load_json_output(project.run_cli("schedule", "list", "--format", "json"))
    assert schedule == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
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


def test_whatif_drop_fails_cleanly_for_unscheduled_course(project) -> None:
    seed_basic_catalog(project)
    result = project.run_cli("whatif", "drop", "--course", "CS101", "--format", "json")
    assert_failure(result)


def test_whatif_swap_fails_cleanly_for_unknown_section(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    result = project.run_cli(
        "whatif",
        "swap",
        "--course",
        "CS101",
        "--section",
        "Z",
        "--format",
        "json",
    )
    assert_failure(result)
