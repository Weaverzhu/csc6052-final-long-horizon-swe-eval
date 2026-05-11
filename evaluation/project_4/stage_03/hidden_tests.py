from __future__ import annotations

import json

from evaluation.project_4.common import assert_success, load_json_output, note_record, seed_basic_notes


def test_snapshot_export_uses_fixed_top_level_shape(project, tmp_path) -> None:
    seed_basic_notes(project)
    export_path = tmp_path / "snapshot.json"

    assert_success(project.run_cli("snapshot", "export", str(export_path)))
    payload = json.loads(export_path.read_text(encoding="utf-8"))

    assert set(payload) == {"notes", "links"}
    assert payload["links"] == []
    assert payload["notes"] == [
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


def test_snapshot_import_replaces_existing_state(project, tmp_path) -> None:
    seed_basic_notes(project)
    export_path = tmp_path / "snapshot.json"
    assert_success(project.run_cli("snapshot", "export", str(export_path)))

    assert_success(
        project.run_cli(
            "note",
            "add",
            "--id",
            "N-999",
            "--title",
            "Temporary",
            "--body",
            "Should be removed by import.",
        )
    )
    assert_success(project.run_cli("snapshot", "import", str(export_path)))

    payload = load_json_output(project.run_cli("note", "list", "--format", "json"))
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


def test_snapshot_import_and_export_preserve_non_empty_links(project, tmp_path) -> None:
    snapshot_path = tmp_path / "linked-snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "notes": [
                    note_record(
                        id="N-002",
                        title="Search Design",
                        body="Indexed retrieval for benchmark notes.",
                        tags=["research"],
                    ),
                    note_record(
                        id="N-001",
                        title="Alpha Spec",
                        body="Course project baseline and glossary.",
                        tags=["core", "research"],
                    ),
                ],
                "links": [
                    {"source": "N-002", "target": "N-001"},
                    {"source": "N-001", "target": "N-002"},
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert_success(project.run_cli("snapshot", "import", str(snapshot_path)))
    export_path = tmp_path / "roundtrip.json"
    assert_success(project.run_cli("snapshot", "export", str(export_path)))

    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["links"] == [
        {"source": "N-001", "target": "N-002"},
        {"source": "N-002", "target": "N-001"},
    ]
