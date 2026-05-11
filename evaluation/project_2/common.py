from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any


PACKAGE_CANDIDATES = (
    Path("text_analyzer"),
    Path("src/text_analyzer"),
)
WORD_RE = re.compile(r"[A-Za-z0-9']+")
SENTENCE_RE = re.compile(r"[.!?]+")


@dataclass
class AgentProject:
    root: Path

    @property
    def pyproject_path(self) -> Path:
        return self.root / "pyproject.toml"

    def load_pyproject(self) -> dict[str, Any]:
        assert self.pyproject_path.exists(), "submission must preserve the starter pyproject.toml"
        with self.pyproject_path.open("rb") as handle:
            return tomllib.load(handle)

    def package_root(self) -> Path | None:
        for candidate in PACKAGE_CANDIDATES:
            package_dir = self.root / candidate
            if (package_dir / "__init__.py").exists():
                return package_dir
        return None

    def package_python_files(self) -> list[Path]:
        package_dir = self.package_root()
        if package_dir is None:
            return []
        return sorted(
            path
            for path in package_dir.rglob("*.py")
            if "__pycache__" not in path.parts
        )

    def plugin_dir(self) -> Path:
        package_dir = self.package_root()
        assert package_dir is not None, "submission package is missing"
        candidates = [path for path in package_dir.rglob("plugins") if path.is_dir()]
        assert candidates, "submission must define a plugins directory inside the package"
        return candidates[0]

    def assert_submission_contract(self) -> None:
        package_dir = self.package_root()
        assert package_dir is not None, (
            "submission must define a package at text_analyzer/ or src/text_analyzer/"
        )

        pyproject = self.load_pyproject()
        project = pyproject.get("project", {})
        assert project.get("name"), "pyproject.toml must define [project].name"

        package_files = self.package_python_files()
        assert len(package_files) >= 3, (
            "submission must contain multiple Python modules, not a single-file solution"
        )
        implementation_modules = [
            path
            for path in package_files
            if path.name not in {"__init__.py", "__main__.py"}
        ]
        assert implementation_modules, (
            "submission must keep CLI wiring thin and place analysis logic in separate modules"
        )

        entry_path = package_dir / "__main__.py"
        assert entry_path.exists(), "submission package must preserve a CLI entry via __main__.py"

    def run_cli(self, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
        self.assert_submission_contract()
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        try:
            return subprocess.run(
                ["uv", "run", "python", "-m", "text_analyzer", *args],
                capture_output=True,
                cwd=self.root,
                env=env,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise AssertionError("uv must be available in the evaluation runtime") from exc


def assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"command failed with code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def assert_failure(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, "command unexpectedly succeeded"
    assert result.stderr.strip(), "expected a short error message on stderr"
    assert "Traceback" not in result.stderr


def load_json_output(result: subprocess.CompletedProcess[str]) -> Any:
    assert_success(result)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not valid JSON:\n{result.stdout}") from exc


def fixture_text(name: str) -> str:
    return files("evaluation.project_2.fixtures").joinpath(name).read_text(encoding="utf-8")


def expected_basic_stats(text: str) -> dict[str, Any]:
    words = WORD_RE.findall(text)
    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    average = round(sum(len(word) for word in words) / len(words), 2) if words else 0.0
    return {
        "word_count": len(words),
        "character_count": len(text),
        "line_count": len(non_empty_lines),
        "average_word_length": average,
    }


def expected_sentence_count(text: str) -> int:
    return len(SENTENCE_RE.findall(text))


def expected_paragraph_count(text: str) -> int:
    return len([paragraph for paragraph in text.split("\n\n") if paragraph.strip()])


def expected_top_words(text: str, limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for word in WORD_RE.findall(text.lower()):
        counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"word": word, "count": count} for word, count in ordered[:limit]]


def normalized_words(text: str) -> list[str]:
    return [word.lower() for word in WORD_RE.findall(text)]


def expected_unique_word_count(text: str) -> int:
    return len(set(normalized_words(text)))


def expected_longest_word(text: str) -> dict[str, Any]:
    words = normalized_words(text)
    if not words:
        return {"word": "", "length": 0}
    max_length = max(len(word) for word in words)
    candidates = sorted(word for word in set(words) if len(word) == max_length)
    return {"word": candidates[0], "length": max_length}


def expected_keyword_density(text: str) -> dict[str, float]:
    words = normalized_words(text)
    if not words:
        return {}
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return {
        word: round(count / len(words), 4)
        for word, count in sorted(counts.items())
    }


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def expected_text_output(payload: dict[str, Any]) -> str:
    lines = [f"{name}: {compact_json(payload[name])}" for name in sorted(payload)]
    return "\n".join(lines) + "\n"


def expected_markdown_output(payload: dict[str, Any]) -> str:
    rows = ["| analysis | value |", "| --- | --- |"]
    rows.extend(f"| {name} | {compact_json(payload[name])} |" for name in sorted(payload))
    return "\n".join(rows) + "\n"
