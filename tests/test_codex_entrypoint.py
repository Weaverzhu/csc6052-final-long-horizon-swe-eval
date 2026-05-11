from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "docker/agents/codex/entrypoint.sh"
STAGE_WRAPPER = REPO_ROOT / "benchmark/scripts/run_stage_codex.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_codex_entrypoint_disables_inner_sandbox_by_default(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-codex-args.txt"
    env_path = tmp_path / "fake-codex-env.txt"

    write_executable(
        fake_bin / "codex",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_CODEX_ARGS_FILE\"",
                "printf 'http_proxy=%s\\nHTTP_PROXY=%s\\nhttps_proxy=%s\\nHTTPS_PROXY=%s\\n' "
                "\"${http_proxy:-}\" \"${HTTP_PROXY:-}\" \"${https_proxy:-}\" \"${HTTPS_PROXY:-}\" "
                "> \"$FAKE_CODEX_ENV_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    home_dir = tmp_path / "home"
    state_dir = home_dir / ".codex"
    state_dir.mkdir(parents=True)
    (state_dir / "auth.json").write_text("{}", encoding="utf-8")

    results_dir = tmp_path / "results"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "AGENT_RESULTS_DIR": str(results_dir),
            "AGENT_RUN_ID": "entrypoint-test",
            "CODEX_MODEL": "gpt-5.4",
            "FAKE_CODEX_ARGS_FILE": str(args_path),
            "FAKE_CODEX_ENV_FILE": str(env_path),
            "http_proxy": "http://proxy.internal:8080",
        }
    )

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "codex", "exec", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "exec",
        "solve the task",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--output-last-message",
        f"{results_dir}/codex/entrypoint-test/final-message.txt",
    ]
    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "http_proxy=http://proxy.internal:8080",
        "HTTP_PROXY=http://proxy.internal:8080",
        "https_proxy=http://proxy.internal:8080",
        "HTTPS_PROXY=http://proxy.internal:8080",
    ]

    command_text = (
        results_dir / "codex" / "entrypoint-test" / "command.txt"
    ).read_text(encoding="utf-8")
    assert "--dangerously-bypass-approvals-and-sandbox" in command_text
    assert "--full-auto" not in command_text


def test_codex_entrypoint_maps_crs_key_and_uses_codex_home(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-codex-args.txt"
    env_path = tmp_path / "fake-codex-env.txt"
    state_dir = tmp_path / "codex-state"
    state_dir.mkdir()
    custom_config = 'model_provider = "crs"\n'
    (state_dir / "config.toml").write_text(custom_config, encoding="utf-8")

    write_executable(
        fake_bin / "codex",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [[ \"$1\" == \"login\" && \"$2\" == \"--with-api-key\" ]]; then",
                "  read -r api_key",
                "  mkdir -p \"$CODEX_HOME\"",
                "  printf '{\"api_key\":\"%s\"}\\n' \"$api_key\" > \"$CODEX_HOME/auth.json\"",
                "  exit 0",
                "fi",
                "printf '%s\\n' \"$@\" > \"$FAKE_CODEX_ARGS_FILE\"",
                "printf 'OPENAI_API_KEY=%s\\nCRS_OAI_KEY=%s\\nCODEX_HOME=%s\\n' "
                "\"${OPENAI_API_KEY:-}\" \"${CRS_OAI_KEY:-}\" \"${CODEX_HOME:-}\" "
                "> \"$FAKE_CODEX_ENV_FILE\"",
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
            "CODEX_HOME": str(state_dir),
            "CRS_OAI_KEY": "crs-key",
            "CODEX_MODEL": "gpt-5.4",
            "AGENT_RESULTS_DIR": str(tmp_path / "results"),
            "AGENT_RUN_ID": "crs-test",
            "FAKE_CODEX_ARGS_FILE": str(args_path),
            "FAKE_CODEX_ENV_FILE": str(env_path),
        }
    )
    env.pop("OPENAI_API_KEY", None)
    for proxy_name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        env.pop(proxy_name, None)

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "codex", "exec", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert (state_dir / "auth.json").read_text(encoding="utf-8") == (
        '{"api_key":"crs-key"}\n'
    )
    assert (state_dir / "config.toml").read_text(encoding="utf-8") == custom_config
    artifact_config = (
        tmp_path / "results" / "codex" / "crs-test" / "config.toml"
    )
    assert artifact_config.read_text(encoding="utf-8") == custom_config
    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "OPENAI_API_KEY=crs-key",
        "CRS_OAI_KEY=crs-key",
        f"CODEX_HOME={state_dir}",
    ]
    assert args_path.read_text(encoding="utf-8").splitlines()[:2] == [
        "exec",
        "solve the task",
    ]


def test_run_stage_codex_wrapper_forwards_proxy_env_vars(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    codex_state_dir = home_dir / ".codex"
    codex_state_dir.mkdir(parents=True)
    auth_file = codex_state_dir / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")

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

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
            "http_proxy": "http://127.0.0.1:8080",
        }
    )
    env.pop("CODEX_HOME", None)
    env.pop("OPENAI_API_KEY", None)

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
        "-v",
        f"{auth_file}:/codex-home/.codex/auth.json:ro",
        "-e",
        "http_proxy=http://host.docker.internal:8080",
        "-e",
        "https_proxy=http://host.docker.internal:8080",
        "csc6052-codex",
        "codex",
        "exec",
        "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it.",
    ]


def test_run_stage_codex_wrapper_forwards_crs_key_and_mounts_codex_home(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")
    codex_home = tmp_path / "codex-state"
    codex_home.mkdir()

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

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "CODEX_HOME": str(codex_home),
            "CRS_OAI_KEY": "crs-key",
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
        }
    )
    env.pop("OPENAI_API_KEY", None)
    for proxy_name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        env.pop(proxy_name, None)

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
        "-v",
        f"{codex_home}:/codex-home/.codex",
        "-e",
        "CODEX_HOME=/codex-home/.codex",
        "-e",
        "OPENAI_API_KEY=crs-key",
        "-e",
        "CRS_OAI_KEY=crs-key",
        "csc6052-codex",
        "codex",
        "exec",
        "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it.",
    ]


def test_run_stage_codex_wrapper_allows_explicit_default_home_without_crs_key(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    auth_file = home_dir / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text("{}", encoding="utf-8")

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

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "CODEX_HOME": "~/.codex",
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
        }
    )
    env.pop("CRS_OAI_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    for proxy_name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        env.pop(proxy_name, None)

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
        "-v",
        f"{auth_file}:/codex-home/.codex/auth.json:ro",
        "csc6052-codex",
        "codex",
        "exec",
        "Read /workspace/task/prompt.md and modify /workspace/repo to satisfy it.",
    ]


def test_run_stage_codex_wrapper_requires_crs_key_with_codex_home(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo").mkdir(parents=True)
    (workspace_root / "task").mkdir()
    (workspace_root / "task" / "prompt.md").write_text("solve it\n", encoding="utf-8")
    codex_home = tmp_path / "codex-state"
    codex_home.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "CODEX_HOME": str(codex_home),
        }
    )
    env.pop("CRS_OAI_KEY", None)
    env.pop("OPENAI_API_KEY", None)

    completed = subprocess.run(
        ["bash", str(STAGE_WRAPPER), str(workspace_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 2
    assert "provide CRS_OAI_KEY when using an alternate CODEX_HOME" in completed.stderr
