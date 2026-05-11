from __future__ import annotations

from evaluation.project_2.common import load_json_output


def test_analyze_dir_returns_per_file_results_and_aggregate(project) -> None:
    batch_dir = project.root / "batch"
    batch_dir.mkdir()
    (batch_dir / "a.txt").write_text("one two", encoding="utf-8")
    (batch_dir / "b.txt").write_text("three", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze-dir",
            str(batch_dir),
            "--analysis",
            "word_count",
            "--format",
            "json",
        )
    )
    assert payload == {
        "files": [
            {"path": "a.txt", "results": {"word_count": 2}},
            {"path": "b.txt", "results": {"word_count": 1}},
        ],
        "aggregate": {"word_count": 3},
    }


def test_analyze_dir_empty_directory_returns_empty_files_and_aggregate(project) -> None:
    batch_dir = project.root / "empty-batch"
    batch_dir.mkdir()

    payload = load_json_output(
        project.run_cli(
            "analyze-dir",
            str(batch_dir),
            "--analysis",
            "word_count",
            "--format",
            "json",
        )
    )
    assert payload == {"files": [], "aggregate": {}}


def test_batch_analysis_can_use_stage_four_numeric_plugin_results(project) -> None:
    batch_dir = project.root / "batch"
    batch_dir.mkdir()
    (batch_dir / "a.txt").write_text("alpha beta alpha", encoding="utf-8")
    (batch_dir / "b.txt").write_text("beta gamma", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze-dir",
            str(batch_dir),
            "--analysis",
            "unique_word_count",
            "--format",
            "json",
        )
    )
    assert payload == {
        "files": [
            {"path": "a.txt", "results": {"unique_word_count": 2}},
            {"path": "b.txt", "results": {"unique_word_count": 2}},
        ],
        "aggregate": {"unique_word_count": 4},
    }


def test_analyze_dir_is_recursive_and_aggregates_only_numeric_results(project) -> None:
    batch_dir = project.root / "batch"
    nested_dir = batch_dir / "nested"
    nested_dir.mkdir(parents=True)
    (batch_dir / "a.txt").write_text("alpha beta", encoding="utf-8")
    (nested_dir / "b.txt").write_text("beta beta", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze-dir",
            str(batch_dir),
            "--analysis",
            "word_count",
            "--analysis",
            "top_words",
            "--format",
            "json",
        )
    )
    assert payload == {
        "files": [
            {
                "path": "a.txt",
                "results": {
                    "word_count": 2,
                    "top_words": [
                        {"word": "alpha", "count": 1},
                        {"word": "beta", "count": 1},
                    ],
                },
            },
            {
                "path": "nested/b.txt",
                "results": {
                    "word_count": 2,
                    "top_words": [{"word": "beta", "count": 2}],
                },
            },
        ],
        "aggregate": {"word_count": 4},
    }
