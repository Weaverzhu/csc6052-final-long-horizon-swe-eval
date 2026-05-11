from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_agent_runtime_images_install_uv() -> None:
    agent_dockerfiles = [
        REPO_ROOT / "docker/agents/mini-swe-agent/Dockerfile",
        REPO_ROOT / "docker/agents/codex/Dockerfile",
        REPO_ROOT / "docker/agents/claude/Dockerfile",
    ]

    for dockerfile in agent_dockerfiles:
        content = dockerfile.read_text(encoding="utf-8")
        assert "pip install" in content
        assert " uv" in content or "uv " in content


def test_claude_runtime_image_uses_non_root_user() -> None:
    dockerfile = REPO_ROOT / "docker/agents/claude/Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "\nUSER node\n" in content
