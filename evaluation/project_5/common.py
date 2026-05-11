from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_CANDIDATES = (
    Path("config_manager"),
    Path("src/config_manager"),
)
DEFAULT_DATA_PATH = "config_manager_data.json"


@dataclass
class AgentProject:
    root: Path

    @property
    def pyproject_path(self) -> Path:
        return self.root / "pyproject.toml"

    @property
    def data_path(self) -> Path:
        return self.root / DEFAULT_DATA_PATH

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
            "submission must define a package at config_manager/ or src/config_manager/"
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
            "submission must keep CLI wiring thin and place config logic in separate modules"
        )

        entry_path = package_dir / "__main__.py"
        assert entry_path.exists(), "submission package must preserve a CLI entry via __main__.py"

    def run_cli(self, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
        self.assert_submission_contract()
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        try:
            return subprocess.run(
                ["uv", "run", "python", "-m", "config_manager", *args],
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


def profile_record(*, name: str, schema_version: int, sections: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "schema_version": schema_version,
        "sections": sections,
    }


def issue_record(*, path: str, code: str, value: Any) -> dict[str, Any]:
    return {
        "path": path,
        "code": code,
        "value": value,
    }


def set_base(
    project: AgentProject,
    *,
    profile: str,
    section: str,
    key: str,
    value: str,
) -> None:
    assert_success(
        project.run_cli(
            "setting",
            "set",
            "--profile",
            profile,
            "--section",
            section,
            "--key",
            key,
            "--value",
            value,
        )
    )


def set_override(
    project: AgentProject,
    *,
    profile: str,
    target: str,
    section: str,
    key: str,
    value: str,
) -> None:
    assert_success(
        project.run_cli(
            "override",
            "set",
            "--profile",
            profile,
            "--target",
            target,
            "--section",
            section,
            "--key",
            key,
            "--value",
            value,
        )
    )


def seed_valid_v1_profile(project: AgentProject, *, profile: str = "alpha") -> None:
    set_base(project, profile=profile, section="database", key="port", value="5432")
    set_base(project, profile=profile, section="service", key="debug", value="false")
    set_base(project, profile=profile, section="service", key="timeout", value="30")


def load_state_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
