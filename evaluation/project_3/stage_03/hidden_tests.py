from __future__ import annotations

import json

from evaluation.project_3.common import (
    assert_success,
    load_json_output,
    section_record,
    seed_basic_catalog,
)


def test_custom_data_paths_are_isolated(project) -> None:
    first = "a.json"
    second = "b.json"
    seed_basic_catalog(project, data_path=first)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A", "--data", first))
    seed_basic_catalog(project, data_path=second)
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A", "--data", second))

    first_payload = load_json_output(project.run_cli("schedule", "list", "--format", "json", "--data", first))
    second_payload = load_json_output(project.run_cli("schedule", "list", "--format", "json", "--data", second))
    assert [item["course"] for item in first_payload] == ["CS101"]
    assert [item["course"] for item in second_payload] == ["MATH201"]


def test_default_data_path_still_works_without_data_flag(project) -> None:
    seed_basic_catalog(project)
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
    assert (project.root / "course_planner_data.json").exists()


def test_export_and_import_restore_state(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    export_path = project.root / "snapshot.json"

    assert_success(project.run_cli("export", "--output", str(export_path)))
    document = json.loads(export_path.read_text(encoding="utf-8"))
    assert set(document) == {"courses", "sections", "schedule"}
    assert isinstance(document["courses"], list)
    assert isinstance(document["sections"], list)
    assert isinstance(document["schedule"], list)

    restored = "restored.json"
    assert_success(project.run_cli("import", "--input", str(export_path), "--data", restored))
    payload = load_json_output(project.run_cli("schedule", "list", "--format", "json", "--data", restored))
    assert payload == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
            start="09:00",
            end="10:15",
        )
    ]


def test_import_replaces_existing_target_state_instead_of_merging(project) -> None:
    seed_basic_catalog(project)
    assert_success(project.run_cli("schedule", "add", "--course", "CS101", "--section", "A"))
    export_path = project.root / "snapshot-replace.json"
    assert_success(project.run_cli("export", "--output", str(export_path)))

    target_data = "target.json"
    seed_basic_catalog(project, data_path=target_data)
    assert_success(project.run_cli("schedule", "add", "--course", "MATH201", "--section", "A", "--data", target_data))

    assert_success(project.run_cli("import", "--input", str(export_path), "--data", target_data))
    payload = load_json_output(project.run_cli("schedule", "list", "--format", "json", "--data", target_data))
    assert payload == [
        section_record(
            course="CS101",
            section="A",
            days="MW",
            start="09:00",
            end="10:15",
        )
    ]
