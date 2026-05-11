from __future__ import annotations

from evaluation.project_4.common import (
    assert_failure,
    assert_success,
    load_json_output,
    note_detail,
    seed_basic_notes,
)


def test_note_show_reports_references_and_backlinks(project) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("link", "add", "--source", "N-001", "--target", "N-002"))

    source_payload = load_json_output(project.run_cli("note", "show", "--id", "N-001", "--format", "json"))
    target_payload = load_json_output(project.run_cli("note", "show", "--id", "N-002", "--format", "json"))

    assert source_payload == note_detail(
        id="N-001",
        title="Alpha Spec",
        body="Course project baseline and glossary.",
        tags=["core", "research"],
        references=["N-002"],
        backlinks=[],
    )
    assert target_payload == note_detail(
        id="N-002",
        title="Search Design",
        body="Indexed retrieval for benchmark notes.",
        tags=["research"],
        references=[],
        backlinks=["N-001"],
    )


def test_self_links_and_unknown_targets_fail_cleanly(project) -> None:
    seed_basic_notes(project)
    self_link = project.run_cli("link", "add", "--source", "N-001", "--target", "N-001")
    assert_failure(self_link)

    missing = project.run_cli("link", "add", "--source", "N-001", "--target", "N-404")
    assert_failure(missing)

    missing_source = project.run_cli("link", "add", "--source", "N-404", "--target", "N-001")
    assert_failure(missing_source)


def test_note_show_sorts_multi_link_references_and_backlinks(project) -> None:
    seed_basic_notes(project)
    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-003",
            "--title",
            "Gamma",
            "--body",
            "Third note.",
        )
    )
    assert_success(project.run_cli("link", "add", "--source", "N-001", "--target", "N-003"))
    assert_success(project.run_cli("link", "add", "--source", "N-001", "--target", "N-002"))
    assert_success(project.run_cli("link", "add", "--source", "N-003", "--target", "N-002"))

    source_payload = load_json_output(project.run_cli("note", "show", "--id", "N-001", "--format", "json"))
    target_payload = load_json_output(project.run_cli("note", "show", "--id", "N-002", "--format", "json"))

    assert source_payload["references"] == ["N-002", "N-003"]
    assert target_payload["backlinks"] == ["N-001", "N-003"]
