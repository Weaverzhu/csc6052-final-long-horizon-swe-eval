from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "docker/agents/claude/entrypoint.sh"
STAGE_WRAPPER = REPO_ROOT / "benchmark/scripts/run_stage_claude.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def base_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "no_proxy", "NO_PROXY"):
        env.pop(key, None)
    return env


def test_claude_entrypoint_adds_headless_defaults_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-claude-args.txt"
    env_path = tmp_path / "fake-claude-env.txt"

    write_executable(
        fake_bin / "claude",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_CLAUDE_ARGS_FILE\"",
                "printf 'http_proxy=%s\\nHTTP_PROXY=%s\\nhttps_proxy=%s\\nHTTPS_PROXY=%s\\n' "
                "\"${http_proxy:-}\" \"${HTTP_PROXY:-}\" \"${https_proxy:-}\" \"${HTTPS_PROXY:-}\" "
                "> \"$FAKE_CLAUDE_ENV_FILE\"",
                "printf 'final response\\n'",
                "printf 'debug stderr\\n' >&2",
                "exit 0",
                "",
            ]
        ),
    )

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    results_dir = tmp_path / "results"

    env = base_env()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "AGENT_RESULTS_DIR": str(results_dir),
            "AGENT_RUN_ID": "entrypoint-test",
            "CLAUDE_CODE_OAUTH_TOKEN": "dummy-token",
            "CLAUDE_MODEL": "claude-sonnet-4-6",
            "CLAUDE_MAX_TURNS": "9",
            "FAKE_CLAUDE_ARGS_FILE": str(args_path),
            "FAKE_CLAUDE_ENV_FILE": str(env_path),
            "http_proxy": "http://proxy.internal:8080",
        }
    )

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "claude", "-p", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "-p",
        "solve the task",
        "--dangerously-skip-permissions",
        "--output-format",
        "text",
        "--max-turns",
        "9",
        "--model",
        "claude-sonnet-4-6",
    ]
    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "http_proxy=http://proxy.internal:8080",
        "HTTP_PROXY=http://proxy.internal:8080",
        "https_proxy=http://proxy.internal:8080",
        "HTTPS_PROXY=http://proxy.internal:8080",
    ]

    artifact_dir = results_dir / "claude" / "entrypoint-test"
    assert (artifact_dir / "final-message.txt").read_text(encoding="utf-8") == "final response\n"
    console_log = (artifact_dir / "console.log").read_text(encoding="utf-8")
    assert "final response" in console_log
    assert "debug stderr" in console_log
    assert (artifact_dir / "exit-code.txt").read_text(encoding="utf-8") == "0\n"


def test_claude_entrypoint_requires_noninteractive_auth(tmp_path: Path) -> None:
    env = base_env()
    env["HOME"] = str(tmp_path / "home")

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "claude", "-p", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 2
    assert "provide CLAUDE_CODE_OAUTH_TOKEN" in completed.stderr


def test_claude_entrypoint_supports_deepseek_without_oauth(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-claude-args.txt"
    env_path = tmp_path / "fake-claude-env.txt"

    write_executable(
        fake_bin / "claude",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_CLAUDE_ARGS_FILE\"",
                "printf 'ANTHROPIC_BASE_URL=%s\\nANTHROPIC_AUTH_TOKEN=%s\\nANTHROPIC_MODEL=%s\\nANTHROPIC_DEFAULT_OPUS_MODEL=%s\\nANTHROPIC_DEFAULT_SONNET_MODEL=%s\\nANTHROPIC_DEFAULT_HAIKU_MODEL=%s\\nCLAUDE_CODE_SUBAGENT_MODEL=%s\\nCLAUDE_CODE_EFFORT_LEVEL=%s\\n' "
                "\"${ANTHROPIC_BASE_URL:-}\" \"${ANTHROPIC_AUTH_TOKEN:-}\" \"${ANTHROPIC_MODEL:-}\" "
                "\"${ANTHROPIC_DEFAULT_OPUS_MODEL:-}\" \"${ANTHROPIC_DEFAULT_SONNET_MODEL:-}\" "
                "\"${ANTHROPIC_DEFAULT_HAIKU_MODEL:-}\" \"${CLAUDE_CODE_SUBAGENT_MODEL:-}\" "
                "\"${CLAUDE_CODE_EFFORT_LEVEL:-}\" > \"$FAKE_CLAUDE_ENV_FILE\"",
                "printf 'final response\\n'",
                "exit 0",
                "",
            ]
        ),
    )

    env = base_env()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "AGENT_RESULTS_DIR": str(tmp_path / "results"),
            "CLAUDE_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "deepseek-token",
            "CLAUDE_MODEL": "deepseek-v4-pro[1m]",
            "FAKE_CLAUDE_ARGS_FILE": str(args_path),
            "FAKE_CLAUDE_ENV_FILE": str(env_path),
        }
    )

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "claude", "-p", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert args_path.read_text(encoding="utf-8").splitlines()[-2:] == [
        "--model",
        "deepseek-v4-pro[1m]",
    ]
    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN=deepseek-token",
        "ANTHROPIC_MODEL=deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash",
        "CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash",
        "CLAUDE_CODE_EFFORT_LEVEL=max",
    ]


def test_run_stage_claude_wrapper_rejects_benchmark_root() -> None:
    completed = subprocess.run(
        ["bash", str(STAGE_WRAPPER)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert completed.returncode == 2
    assert "refusing to mount the benchmark repository root" in completed.stderr


def test_run_stage_claude_wrapper_forwards_proxy_env_vars(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-docker-args.txt"

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_DOCKER_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = base_env()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CLAUDE_CODE_OAUTH_TOKEN": "dummy-token",
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
            "http_proxy": "http://127.0.0.1:8080",
        }
    )

    completed = subprocess.run(
        ["bash", str(STAGE_WRAPPER), str(workspace_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "run",
        "--rm",
        "-v",
        f"{workspace_root}:/workspace",
        "-e",
        "CLAUDE_MODEL=claude-sonnet-4-6",
        "-e",
        "CLAUDE_MAX_TURNS=120",
        "-e",
        "CLAUDE_CODE_OAUTH_TOKEN=dummy-token",
        "-e",
        "http_proxy=http://host.docker.internal:8080",
        "-e",
        "https_proxy=http://host.docker.internal:8080",
        "csc6052-claude",
        "claude",
        "-p",
        "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.",
    ]


def test_run_stage_claude_wrapper_uses_deepseek_without_oauth_or_proxy(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-docker-args.txt"

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_DOCKER_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = base_env()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CLAUDE_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "deepseek-token",
            "CLAUDE_CODE_OAUTH_TOKEN": "subscription-token",
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
            "http_proxy": "http://127.0.0.1:8080",
        }
    )

    completed = subprocess.run(
        ["bash", str(STAGE_WRAPPER), str(workspace_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    docker_args = args_path.read_text(encoding="utf-8").splitlines()
    assert docker_args == [
        "run",
        "--rm",
        "-v",
        f"{workspace_root}:/workspace",
        "-e",
        "CLAUDE_MODEL=deepseek-v4-pro[1m]",
        "-e",
        "CLAUDE_MAX_TURNS=120",
        "-e",
        "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic",
        "-e",
        "ANTHROPIC_AUTH_TOKEN",
        "-e",
        "ANTHROPIC_MODEL=deepseek-v4-pro[1m]",
        "-e",
        "ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]",
        "-e",
        "ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]",
        "-e",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash",
        "-e",
        "CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash",
        "-e",
        "CLAUDE_CODE_EFFORT_LEVEL=max",
        "csc6052-claude",
        "claude",
        "-p",
        "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.",
    ]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in docker_args
    assert not any("proxy" in arg.lower() for arg in docker_args)
