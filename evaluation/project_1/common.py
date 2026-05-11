from __future__ import annotations

import csv
import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

PACKAGE_CANDIDATES = (
    Path("finance_tracker"),
    Path("src/finance_tracker"),
)


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

    def assert_submission_contract(self) -> None:
        package_dir = self.package_root()
        assert package_dir is not None, (
            "submission must define a package at finance_tracker/ or src/finance_tracker/"
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
            "submission must keep CLI wiring thin and place business logic in separate modules"
        )

        entry_path = package_dir / "__main__.py"
        assert entry_path.exists(), (
            "submission package must preserve a CLI entry via __main__.py"
        )

    def run_cli(self, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
        self.assert_submission_contract()
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        try:
            return subprocess.run(
                ["uv", "run", "python", "-m", "finance_tracker", *args],
                capture_output=True,
                cwd=self.root,
                env=env,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise AssertionError("uv must be available in the evaluation runtime") from exc


def coerce_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


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


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
