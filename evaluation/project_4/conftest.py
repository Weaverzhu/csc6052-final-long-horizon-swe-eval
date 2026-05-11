from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from evaluation.project_4.common import AgentProject


def _copy_submission_tree(source_root: Path, worktree: Path) -> None:
    shutil.copytree(
        source_root,
        worktree,
        ignore=shutil.ignore_patterns(
            ".git",
            ".agent-results",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            "knowledge_base_data.json",
            "knowledge_base_index.json",
            "*.pyc",
        ),
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--project-dir",
        action="store",
        default=None,
        help="Path to the agent-generated project repository to evaluate.",
    )


def _resolve_project_dir(config: pytest.Config) -> Path:
    configured = config.getoption("--project-dir")
    env_value = (
        configured
        or os.environ.get("AGENT_PROJECT_ROOT")
        or os.environ.get("PROJECT_DIR")
        or os.environ.get("SUBMISSION_DIR")
    )
    if not env_value:
        raise pytest.UsageError(
            "Provide --project-dir or set AGENT_PROJECT_ROOT to the agent submission."
        )

    project_dir = Path(env_value).expanduser().resolve()
    if not project_dir.exists():
        raise pytest.UsageError(f"project directory does not exist: {project_dir}")
    return project_dir


@pytest.fixture
def project(tmp_path: Path, pytestconfig: pytest.Config) -> AgentProject:
    source_root = _resolve_project_dir(pytestconfig)
    worktree = tmp_path / "submission"
    _copy_submission_tree(source_root, worktree)
    return AgentProject(worktree)
