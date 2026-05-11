from __future__ import annotations

from evaluation.project_2.common import (
    assert_success,
    expected_markdown_output,
    expected_text_output,
    fixture_text,
    load_json_output,
)


def test_json_format_still_returns_machine_readable_output(project) -> None:
    text_path = project.root / "sample.txt"
    text_path.write_text(fixture_text("reference_text.txt"), encoding="utf-8")

    payload = load_json_output(project.run_cli("analyze", str(text_path), "--format", "json"))
    assert "word_count" in payload


def test_text_format_returns_human_readable_output(project) -> None:
    text_path = project.root / "sample.txt"
    text_path.write_text(fixture_text("reference_text.txt"), encoding="utf-8")

    json_payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "word_count",
            "--analysis",
            "top_words",
            "--format",
            "json",
        )
    )
    result = project.run_cli(
        "analyze",
        str(text_path),
        "--analysis",
        "word_count",
        "--analysis",
        "top_words",
        "--format",
        "text",
    )
    assert_success(result)
    assert result.stdout == expected_text_output(json_payload)


def test_markdown_format_returns_table(project) -> None:
    text_path = project.root / "sample.txt"
    text_path.write_text(fixture_text("reference_text.txt"), encoding="utf-8")

    json_payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "word_count",
            "--analysis",
            "top_words",
            "--format",
            "json",
        )
    )
    result = project.run_cli(
        "analyze",
        str(text_path),
        "--analysis",
        "word_count",
        "--analysis",
        "top_words",
        "--format",
        "markdown",
    )
    assert_success(result)
    assert result.stdout == expected_markdown_output(json_payload)


def test_text_and_markdown_formats_preserve_nested_analysis_results(project) -> None:
    text_path = project.root / "density.txt"
    text_path.write_text("cat cat dog", encoding="utf-8")

    json_payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "keyword_density",
            "--analysis",
            "top_words",
            "--format",
            "json",
        )
    )

    text_result = project.run_cli(
        "analyze",
        str(text_path),
        "--analysis",
        "keyword_density",
        "--analysis",
        "top_words",
        "--format",
        "text",
    )
    assert_success(text_result)
    assert text_result.stdout == expected_text_output(json_payload)

    markdown_result = project.run_cli(
        "analyze",
        str(text_path),
        "--analysis",
        "keyword_density",
        "--analysis",
        "top_words",
        "--format",
        "markdown",
    )
    assert_success(markdown_result)
    assert markdown_result.stdout == expected_markdown_output(json_payload)
