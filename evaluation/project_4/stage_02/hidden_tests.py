from __future__ import annotations

from evaluation.project_4.common import load_json_output, note_record, seed_basic_notes


def test_search_matches_title_and_body_case_insensitively(project) -> None:
    seed_basic_notes(project)
    payload = load_json_output(project.run_cli("note", "search", "--query", "BENCHMARK", "--format", "json"))
    assert payload == [
        note_record(
            id="N-002",
            title="Search Design",
            body="Indexed retrieval for benchmark notes.",
            tags=["research"],
        )
    ]


def test_search_matches_title_substrings_too(project) -> None:
    seed_basic_notes(project)
    payload = load_json_output(project.run_cli("note", "search", "--query", "alpha", "--format", "json"))
    assert payload == [
        note_record(
            id="N-001",
            title="Alpha Spec",
            body="Course project baseline and glossary.",
            tags=["core", "research"],
        )
    ]


def test_list_filter_by_tag_reuses_note_shape_and_sorting(project) -> None:
    seed_basic_notes(project)
    payload = load_json_output(project.run_cli("note", "list", "--tag", "research", "--format", "json"))
    assert payload == [
        note_record(
            id="N-001",
            title="Alpha Spec",
            body="Course project baseline and glossary.",
            tags=["core", "research"],
        ),
        note_record(
            id="N-002",
            title="Search Design",
            body="Indexed retrieval for benchmark notes.",
            tags=["research"],
        ),
    ]
