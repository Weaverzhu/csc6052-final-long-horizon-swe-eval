from __future__ import annotations

import json

from evaluation.project_4.common import (
    assert_success,
    load_json_output,
    load_state_file,
    note_record,
    seed_basic_notes,
)


def test_index_rebuild_creates_deterministic_index_file(project) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("index", "rebuild"))
    first = project.index_path.read_text(encoding="utf-8")

    assert_success(project.run_cli("index", "rebuild"))
    second = project.index_path.read_text(encoding="utf-8")

    assert first == second
    assert json.loads(first)


def test_search_without_index_returns_empty_results(project) -> None:
    seed_basic_notes(project)
    payload = load_json_output(project.run_cli("note", "search", "--query", "alpha", "--format", "json"))
    assert payload == []


def test_search_stays_stale_until_index_rebuild_after_manual_data_edit(project) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("index", "rebuild"))

    before = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert before == []

    state = load_state_file(project.data_path)
    state["notes"].append(
        note_record(
            id="N-003",
            title="Gamma Update",
            body="Gamma phrase appears only after a manual file edit.",
            tags=["delta"],
        )
    )
    project.data_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    stale = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert stale == []

    assert_success(project.run_cli("index", "rebuild"))
    fresh = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert fresh == [
        note_record(
            id="N-003",
            title="Gamma Update",
            body="Gamma phrase appears only after a manual file edit.",
            tags=["delta"],
        )
    ]


def test_search_stays_stale_until_rebuild_after_note_add(project) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("index", "rebuild"))

    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-003",
            "--title",
            "Gamma Add",
            "--body",
            "Gamma appears after note add.",
        )
    )

    stale = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert stale == []

    assert_success(project.run_cli("index", "rebuild"))
    fresh = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert fresh == [
        note_record(
            id="N-003",
            title="Gamma Add",
            body="Gamma appears after note add.",
            tags=[],
        )
    ]


def test_search_stays_stale_until_rebuild_after_snapshot_import(project, tmp_path) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("index", "rebuild"))

    snapshot_path = tmp_path / "import.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "notes": [
                    note_record(
                        id="N-010",
                        title="Imported",
                        body="Imported gamma text.",
                        tags=["archive"],
                    )
                ],
                "links": [],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert_success(project.run_cli("snapshot", "import", str(snapshot_path)))
    stale = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert stale == []

    assert_success(project.run_cli("index", "rebuild"))
    fresh = load_json_output(project.run_cli("note", "search", "--query", "gamma", "--format", "json"))
    assert fresh == [
        note_record(
            id="N-010",
            title="Imported",
            body="Imported gamma text.",
            tags=["archive"],
        )
    ]
