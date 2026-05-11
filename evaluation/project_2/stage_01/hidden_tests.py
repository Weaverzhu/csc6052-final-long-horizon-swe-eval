from __future__ import annotations

from evaluation.project_2.common import (
    assert_failure,
    fixture_text,
    load_json_output,
    expected_basic_stats,
)


def test_submission_uses_uv_managed_package_layout(project) -> None:
    project.assert_submission_contract()


def test_analyze_reference_text_returns_expected_basic_stats(project) -> None:
    text_path = project.root / "sample.txt"
    text = fixture_text("reference_text.txt")
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(project.run_cli("analyze", str(text_path), "--format", "json"))
    expected = expected_basic_stats(text)
    assert payload["word_count"] == expected["word_count"]
    assert payload["character_count"] == expected["character_count"]
    assert payload["line_count"] == expected["line_count"]
    assert round(float(payload["average_word_length"]), 2) == expected["average_word_length"]


def test_missing_file_fails_cleanly(project) -> None:
    result = project.run_cli("analyze", "does-not-exist.txt", "--format", "json")
    assert_failure(result)


def test_empty_file_returns_zero_counts(project) -> None:
    text_path = project.root / "empty.txt"
    text_path.write_text("", encoding="utf-8")

    payload = load_json_output(project.run_cli("analyze", str(text_path), "--format", "json"))
    assert payload["word_count"] == 0
    assert payload["character_count"] == 0
    assert payload["line_count"] == 0
    assert float(payload["average_word_length"]) == 0.0
