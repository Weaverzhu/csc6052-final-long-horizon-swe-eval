from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/managed/go.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_managed_go_codex_rewrites_host_http_proxy_for_container(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-log.txt"
    uv_args = tmp_path / "uv-args.txt"
    home_dir = tmp_path / "home"
    auth_dir = home_dir / ".codex"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text("{}", encoding="utf-8")

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" >> \"$FAKE_DOCKER_LOG\"",
                "printf '%s\\n' '---' >> \"$FAKE_DOCKER_LOG\"",
                "exit 0",
                "",
            ]
        ),
    )
    write_executable(
        fake_bin / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_UV_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "FRAMEWORK": "codex",
            "MODEL": "gpt-5.4",
            "RUNS_ROOT": str(tmp_path / "runs"),
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_UV_ARGS_FILE": str(uv_args),
            "http_proxy": "http://127.0.0.1:50007",
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert completed.returncode == 0

    uv_lines = uv_args.read_text(encoding="utf-8").splitlines()
    assert uv_lines[:4] == ["run", "python", "-m", "benchmark.harness.run_managed_trajectory"]
    assert "-e" in uv_lines
    assert "http_proxy=http://host.docker.internal:50007" in uv_lines
    assert "https_proxy=http://host.docker.internal:50007" in uv_lines
    assert "OPENAI_API_KEY" not in uv_lines

    docker_calls = docker_log.read_text(encoding="utf-8").split("---\n")
    non_empty_calls = [chunk.strip().splitlines() for chunk in docker_calls if chunk.strip()]
    assert len(non_empty_calls) == 2
    assert non_empty_calls[0][:3] == ["build", "-t", "csc6052-codex"]
    assert non_empty_calls[1][:3] == ["build", "-t", "csc6052-project-1-evaluator"]


def test_managed_go_codex_forwards_crs_key_and_mounts_codex_home(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-log.txt"
    uv_args = tmp_path / "uv-args.txt"
    codex_home = tmp_path / "codex-state"
    codex_home.mkdir()

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" >> \"$FAKE_DOCKER_LOG\"",
                "printf '%s\\n' '---' >> \"$FAKE_DOCKER_LOG\"",
                "exit 0",
                "",
            ]
        ),
    )
    write_executable(
        fake_bin / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_UV_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "FRAMEWORK": "codex",
            "MODEL": "gpt-5.4",
            "RUNS_ROOT": str(tmp_path / "runs"),
            "CODEX_HOME": str(codex_home),
            "CRS_OAI_KEY": "crs-key",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_UV_ARGS_FILE": str(uv_args),
        }
    )
    env.pop("OPENAI_API_KEY", None)

    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert completed.returncode == 0

    uv_lines = uv_args.read_text(encoding="utf-8").splitlines()
    assert "CODEX_HOME=/codex-home/.codex" in uv_lines
    assert f"{codex_home}:/codex-home/.codex" in uv_lines
    assert "OPENAI_API_KEY" in uv_lines
    assert "CRS_OAI_KEY" in uv_lines


def test_managed_go_codex_allows_explicit_default_home_without_crs_key(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-log.txt"
    uv_args = tmp_path / "uv-args.txt"
    home_dir = tmp_path / "home"
    auth_file = home_dir / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text("{}", encoding="utf-8")

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" >> \"$FAKE_DOCKER_LOG\"",
                "printf '%s\\n' '---' >> \"$FAKE_DOCKER_LOG\"",
                "exit 0",
                "",
            ]
        ),
    )
    write_executable(
        fake_bin / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_UV_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "FRAMEWORK": "codex",
            "MODEL": "gpt-5.4",
            "RUNS_ROOT": str(tmp_path / "runs"),
            "CODEX_HOME": "~/.codex",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_UV_ARGS_FILE": str(uv_args),
        }
    )
    env.pop("CRS_OAI_KEY", None)
    env.pop("OPENAI_API_KEY", None)

    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert completed.returncode == 0

    uv_lines = uv_args.read_text(encoding="utf-8").splitlines()
    assert f"{auth_file}:/codex-home/.codex/auth.json:ro" in uv_lines
    assert f"{auth_file.parent}:/codex-home/.codex" not in uv_lines
    assert "CODEX_HOME=/codex-home/.codex" not in uv_lines
    assert "OPENAI_API_KEY" not in uv_lines
    assert "CRS_OAI_KEY" not in uv_lines


def test_managed_go_claude_builds_command_and_forwards_metadata(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-log.txt"
    uv_args = tmp_path / "uv-args.txt"

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" >> \"$FAKE_DOCKER_LOG\"",
                "printf '%s\\n' '---' >> \"$FAKE_DOCKER_LOG\"",
                "exit 0",
                "",
            ]
        ),
    )
    write_executable(
        fake_bin / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_UV_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "FRAMEWORK": "claude",
            "MODEL": "claude-sonnet-4-6",
            "RUNS_ROOT": str(tmp_path / "runs"),
            "CLAUDE_CODE_OAUTH_TOKEN": "token",
            "EXPERIMENT_ID": "exp-1",
            "AGENT_ID": "claude-sonnet",
            "REPEAT_INDEX": "3",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_UV_ARGS_FILE": str(uv_args),
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert completed.returncode == 0

    uv_lines = uv_args.read_text(encoding="utf-8").splitlines()
    assert "--experiment-id" in uv_lines
    assert "exp-1" in uv_lines
    assert "--agent-id" in uv_lines
    assert "claude-sonnet" in uv_lines
    assert "--repeat-index" in uv_lines
    assert "3" in uv_lines
    assert "CLAUDE_CODE_OAUTH_TOKEN" in uv_lines
    assert "CLAUDE_MODEL=claude-sonnet-4-6" in uv_lines
    assert "csc6052-claude" in uv_lines
    assert "claude" in uv_lines

    docker_calls = docker_log.read_text(encoding="utf-8").split("---\n")
    non_empty_calls = [chunk.strip().splitlines() for chunk in docker_calls if chunk.strip()]
    assert len(non_empty_calls) == 2
    assert non_empty_calls[0][:3] == ["build", "-t", "csc6052-claude"]
    assert non_empty_calls[1][:3] == ["build", "-t", "csc6052-project-1-evaluator"]


def test_managed_go_claude_deepseek_skips_oauth_and_proxy(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-log.txt"
    uv_args = tmp_path / "uv-args.txt"

    write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" >> \"$FAKE_DOCKER_LOG\"",
                "printf '%s\\n' '---' >> \"$FAKE_DOCKER_LOG\"",
                "exit 0",
                "",
            ]
        ),
    )
    write_executable(
        fake_bin / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_UV_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "FRAMEWORK": "claude",
            "MODEL": "deepseek-v4-pro[1m]",
            "RUNS_ROOT": str(tmp_path / "runs"),
            "DEEPSEEK_API_KEY": "deepseek-token",
            "CLAUDE_CODE_OAUTH_TOKEN": "subscription-token",
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_UV_ARGS_FILE": str(uv_args),
            "http_proxy": "http://127.0.0.1:50007",
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert completed.returncode == 0

    uv_lines = uv_args.read_text(encoding="utf-8").splitlines()
    assert "CLAUDE_MODEL=deepseek-v4-pro[1m]" in uv_lines
    assert "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic" in uv_lines
    assert "ANTHROPIC_AUTH_TOKEN" in uv_lines
    assert "ANTHROPIC_MODEL=deepseek-v4-pro[1m]" in uv_lines
    assert "ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]" in uv_lines
    assert "ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]" in uv_lines
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash" in uv_lines
    assert "CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash" in uv_lines
    assert "CLAUDE_CODE_EFFORT_LEVEL=max" in uv_lines
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in uv_lines
    assert not any("proxy" in line.lower() for line in uv_lines)

    docker_calls = docker_log.read_text(encoding="utf-8").split("---\n")
    non_empty_calls = [chunk.strip().splitlines() for chunk in docker_calls if chunk.strip()]
    assert len(non_empty_calls) == 2
    assert non_empty_calls[0][:3] == ["build", "-t", "csc6052-claude"]
    assert non_empty_calls[1][:3] == ["build", "-t", "csc6052-project-1-evaluator"]
