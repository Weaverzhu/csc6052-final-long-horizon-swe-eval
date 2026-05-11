from __future__ import annotations

from evaluation.project_4.common import assert_success, load_json_output, seed_basic_notes


def test_report_tags_returns_sorted_counts(project) -> None:
    seed_basic_notes(project)
    payload = load_json_output(project.run_cli("report", "tags", "--format", "json"))
    assert payload == [
        {"tag": "core", "count": 1},
        {"tag": "research", "count": 2},
    ]


def test_report_graph_returns_sorted_edges(project) -> None:
    seed_basic_notes(project)
    assert_success(project.run_cli("link", "add", "--source", "N-002", "--target", "N-001"))
    assert_success(project.run_cli("link", "add", "--source", "N-001", "--target", "N-002"))

    payload = load_json_output(project.run_cli("report", "graph", "--format", "json"))
    assert payload == [
        {"source": "N-001", "target": "N-002"},
        {"source": "N-002", "target": "N-001"},
    ]
