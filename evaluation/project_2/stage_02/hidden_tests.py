from __future__ import annotations

from evaluation.project_2.common import (
    assert_failure,
    expected_basic_stats,
    fixture_text,
    load_json_output,
    expected_paragraph_count,
    expected_sentence_count,
    expected_top_words,
)


def test_all_analyses_include_new_stage_two_metrics(project) -> None:
    text_path = project.root / "sample.txt"
    text = fixture_text("reference_text.txt")
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(project.run_cli("analyze", str(text_path), "--format", "json"))
    expected_basic = expected_basic_stats(text)
    assert payload["word_count"] == expected_basic["word_count"]
    assert payload["character_count"] == expected_basic["character_count"]
    assert payload["line_count"] == expected_basic["line_count"]
    assert round(float(payload["average_word_length"]), 2) == expected_basic["average_word_length"]
    assert payload["sentence_count"] == expected_sentence_count(text)
    assert payload["paragraph_count"] == expected_paragraph_count(text)
    assert payload["top_words"] == expected_top_words(text)


def test_analysis_flags_limit_output_to_requested_metrics(project) -> None:
    text_path = project.root / "sample.txt"
    text_path.write_text(fixture_text("reference_text.txt"), encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "sentence_count",
            "--analysis",
            "paragraph_count",
            "--format",
            "json",
        )
    )
    assert set(payload) == {"sentence_count", "paragraph_count"}


def test_paragraph_count_ignores_whitespace_only_blocks(project) -> None:
    text_path = project.root / "paragraphs.txt"
    text_path.write_text("First paragraph.\n\n   \n\nSecond paragraph.\n\n\t", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "paragraph_count",
            "--format",
            "json",
        )
    )
    assert payload == {"paragraph_count": 2}


def test_unknown_analysis_fails_cleanly(project) -> None:
    text_path = project.root / "sample.txt"
    text_path.write_text(fixture_text("reference_text.txt"), encoding="utf-8")

    result = project.run_cli(
        "analyze",
        str(text_path),
        "--analysis",
        "not_real",
        "--format",
        "json",
    )
    assert_failure(result)
