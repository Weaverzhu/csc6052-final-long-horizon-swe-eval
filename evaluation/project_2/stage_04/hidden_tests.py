from __future__ import annotations

from evaluation.project_2.common import (
    expected_keyword_density,
    expected_longest_word,
    expected_unique_word_count,
    fixture_text,
    load_json_output,
)


def test_new_plugins_appear_in_plugin_listing(project) -> None:
    payload = load_json_output(project.run_cli("list-plugins", "--format", "json"))
    assert "unique_word_count" in payload
    assert "longest_word" in payload
    assert "keyword_density" in payload


def test_unique_word_count_plugin_returns_exact_count(project) -> None:
    text_path = project.root / "sample.txt"
    text = fixture_text("reference_text.txt")
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "unique_word_count",
            "--format",
            "json",
        )
    )
    assert payload["unique_word_count"] == expected_unique_word_count(text)


def test_longest_word_plugin_uses_lexicographic_tie_break(project) -> None:
    text_path = project.root / "sample.txt"
    text = "zebra apple"
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(
        project.run_cli("analyze", str(text_path), "--analysis", "longest_word", "--format", "json")
    )
    assert payload["longest_word"] == expected_longest_word(text)


def test_longest_word_returns_empty_result_when_no_words(project) -> None:
    text_path = project.root / "punctuation.txt"
    text_path.write_text("... !!!\n", encoding="utf-8")

    payload = load_json_output(
        project.run_cli("analyze", str(text_path), "--analysis", "longest_word", "--format", "json")
    )
    assert payload["longest_word"] == {"word": "", "length": 0}


def test_keyword_density_plugin_returns_exact_density_mapping(project) -> None:
    text_path = project.root / "density.txt"
    text = "cat cat dog"
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "keyword_density",
            "--format",
            "json",
        )
    )
    assert payload["keyword_density"] == expected_keyword_density(text)
