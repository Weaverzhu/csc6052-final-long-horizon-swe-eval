from __future__ import annotations

from evaluation.project_4.common import (
    assert_failure,
    assert_success,
    load_json_output,
    note_record,
)


def test_submission_uses_uv_managed_package_layout(project) -> None:
    project.assert_submission_contract()


def test_note_add_tag_and_list_are_persistent_and_sorted(project) -> None:
    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-002",
            "--title",
            "Benchmark Notes",
            "--body",
            "Long-horizon benchmark design.",
        )
    )
    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-001",
            "--title",
            "Alpha Entry",
            "--body",
            "Starter note.",
        )
    )
    assert_success(project.run_cli("note", "tag", "--id", "N-002", "--tag", "research"))
    assert_success(project.run_cli("note", "tag", "--id", "N-002", "--tag", "benchmark"))
    assert_success(project.run_cli("note", "tag", "--id", "N-002", "--tag", "research"))

    payload = load_json_output(project.run_cli("note", "list", "--format", "json"))
    assert payload == [
        note_record(
            id="N-001",
            title="Alpha Entry",
            body="Starter note.",
            tags=[],
        ),
        note_record(
            id="N-002",
            title="Benchmark Notes",
            body="Long-horizon benchmark design.",
            tags=["benchmark", "research"],
        ),
    ]


def test_duplicate_note_id_and_unknown_tag_target_fail_cleanly(project) -> None:
    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-001",
            "--title",
            "Alpha Entry",
            "--body",
            "Starter note.",
        )
    )

    duplicate = project.run_cli(
        "note",
        "add",
        "--id",
        "N-001",
        "--title",
        "Duplicate",
        "--body",
        "Should fail.",
    )
    assert_failure(duplicate)

    missing = project.run_cli("note", "tag", "--id", "N-404", "--tag", "missing")
    assert_failure(missing)
