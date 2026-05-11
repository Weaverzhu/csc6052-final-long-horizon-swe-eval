from __future__ import annotations

from evaluation.project_2.common import fixture_text, load_json_output, expected_sentence_count


def test_list_plugins_returns_sorted_json_names(project) -> None:
    payload = load_json_output(project.run_cli("list-plugins", "--format", "json"))
    assert payload == sorted(payload)
    assert {
        "word_count",
        "character_count",
        "line_count",
        "average_word_length",
        "sentence_count",
        "paragraph_count",
        "top_words",
    }.issubset(payload)


def test_drop_in_plugin_is_discovered_without_core_edits(project) -> None:
    plugin_dir = project.plugin_dir()
    plugin_path = plugin_dir / "test_custom_plugin.py"
    plugin_path.write_text(
        "PLUGIN_NAME = 'exclamation_count'\n"
        "def analyze(text, results=None):\n"
        "    return text.count('!')\n",
        encoding="utf-8",
    )

    text_path = project.root / "sample.txt"
    text_path.write_text("Hello! Wow!!", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "exclamation_count",
            "--format",
            "json",
        )
    )
    assert payload["exclamation_count"] == 3


def test_unrequested_drop_in_plugin_is_not_executed(project) -> None:
    plugin_dir = project.plugin_dir()
    marker_path = plugin_dir / "unrequested_plugin_marker.txt"
    plugin_path = plugin_dir / "test_marker_plugin.py"
    plugin_path.write_text(
        "from pathlib import Path\n"
        "PLUGIN_NAME = 'marker_analysis'\n"
        "def analyze(text, results=None):\n"
        "    Path(__file__).with_name('unrequested_plugin_marker.txt').write_text('ran')\n"
        "    return 999\n",
        encoding="utf-8",
    )

    text_path = project.root / "sample.txt"
    text_path.write_text("one two three", encoding="utf-8")

    payload = load_json_output(
        project.run_cli(
            "analyze",
            str(text_path),
            "--analysis",
            "word_count",
            "--format",
            "json",
        )
    )
    assert payload == {"word_count": 3}
    assert not marker_path.exists()


def test_stage_two_metrics_still_work_after_plugin_refactor(project) -> None:
    text_path = project.root / "sample.txt"
    text = fixture_text("reference_text.txt")
    text_path.write_text(text, encoding="utf-8")

    payload = load_json_output(
        project.run_cli("analyze", str(text_path), "--analysis", "sentence_count", "--format", "json")
    )
    assert payload["sentence_count"] == expected_sentence_count(text)
