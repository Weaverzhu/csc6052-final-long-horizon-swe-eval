from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "docker/agents/mini-swe-agent/entrypoint.sh"
STAGE_WRAPPER = REPO_ROOT / "benchmark/scripts/run_stage_mini.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_mini_entrypoint_normalizes_proxy_env_and_writes_bootstrap_env(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-mini-args.txt"
    env_path = tmp_path / "fake-mini-env.txt"
    prompt_config_path = tmp_path / "benchmark-mini-prompt.yaml"
    prompt_config_path.write_text("system_template: default\n", encoding="utf-8")

    write_executable(
        fake_bin / "mini",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_MINI_ARGS_FILE\"",
                "printf 'http_proxy=%s\\nHTTP_PROXY=%s\\nhttps_proxy=%s\\nHTTPS_PROXY=%s\\n' "
                "\"${http_proxy:-}\" \"${HTTP_PROXY:-}\" \"${https_proxy:-}\" \"${HTTPS_PROXY:-}\" "
                "> \"$FAKE_MINI_ENV_FILE\"",
                "printf 'mini stdout\\n'",
                "printf 'mini stderr\\n' >&2",
                "exit 0",
                "",
            ]
        ),
    )

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    results_dir = tmp_path / "results"

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "AGENT_RESULTS_DIR": str(results_dir),
            "AGENT_RUN_ID": "entrypoint-test",
            "MSWEA_MODEL_NAME": "google/gemma-4-26b-a4b-it:free",
            "OPENAI_API_KEY": "dummy-key",
            "FAKE_MINI_ARGS_FILE": str(args_path),
            "FAKE_MINI_ENV_FILE": str(env_path),
            "BENCHMARK_MINI_PROMPT_CONFIG_PATH": str(prompt_config_path),
            "http_proxy": "http://proxy.internal:8080",
        }
    )

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "mini", "-t", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "-t",
        "solve the task",
        "-m",
        "google/gemma-4-26b-a4b-it:free",
        "-y",
        "--exit-immediately",
        "-o",
        f"{results_dir}/mini/entrypoint-test/trajectory.traj.json",
        "-c",
        f"{results_dir}/mini/entrypoint-test/benchmark-mini-prompt.yaml",
    ]
    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "http_proxy=http://proxy.internal:8080",
        "HTTP_PROXY=http://proxy.internal:8080",
        "https_proxy=http://proxy.internal:8080",
        "HTTPS_PROXY=http://proxy.internal:8080",
    ]

    artifact_dir = results_dir / "mini" / "entrypoint-test"
    assert "mini stdout" in (artifact_dir / "console.log").read_text(encoding="utf-8")
    assert "mini stderr" in (artifact_dir / "console.log").read_text(encoding="utf-8")
    assert (artifact_dir / "exit-code.txt").read_text(encoding="utf-8") == "0\n"
    assert "http_proxy=http://proxy.internal:8080" in (
        artifact_dir / "global.env"
    ).read_text(encoding="utf-8")


def test_mini_entrypoint_prefixes_bare_openai_compatible_model(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "fake-mini-args.txt"
    prompt_config_path = tmp_path / "benchmark-mini-prompt.yaml"
    prompt_config_path.write_text("system_template: default\n", encoding="utf-8")

    write_executable(
        fake_bin / "mini",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$@\" > \"$FAKE_MINI_ARGS_FILE\"",
                "exit 0",
                "",
            ]
        ),
    )

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    results_dir = tmp_path / "results"

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home_dir),
            "AGENT_RESULTS_DIR": str(results_dir),
            "AGENT_RUN_ID": "entrypoint-openai-compat-test",
            "MSWEA_MODEL_NAME": "deepseek-v4-flash",
            "MSWEA_MODEL_BACKEND": "openai-compat",
            "OPENAI_API_KEY": "dummy-key",
            "OPENAI_API_BASE": "https://api.deepseek.com",
            "FAKE_MINI_ARGS_FILE": str(args_path),
            "BENCHMARK_MINI_PROMPT_CONFIG_PATH": str(prompt_config_path),
        }
    )
    env.pop("DEEPSEEK_API_KEY", None)

    completed = subprocess.run(
        ["bash", str(ENTRYPOINT), "mini", "-t", "solve the task"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0

    mini_args = args_path.read_text(encoding="utf-8").splitlines()
    assert "-m" in mini_args
    assert mini_args[mini_args.index("-m") + 1] == "openai/deepseek-v4-flash"

    global_env = (
        results_dir / "mini" / "entrypoint-openai-compat-test" / "global.env"
    ).read_text(encoding="utf-8")
    assert "MSWEA_MODEL_NAME=openai/deepseek-v4-flash" in global_env
    assert "MSWEA_MODEL_BACKEND=openai-compat" in global_env


def test_run_stage_mini_wrapper_forwards_proxy_env_vars(tmp_path: Path) -> None:
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

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "OPENAI_API_KEY": "dummy-key",
            "FAKE_DOCKER_ARGS_FILE": str(args_path),
            "http_proxy": "http://proxy.internal:8080",
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
        "-it",
        "-v",
        f"{workspace_root}:/workspace",
        "-e",
        "MSWEA_MODEL_NAME=google/gemma-4-26b-a4b-it:free",
        "-e",
        "OPENAI_API_KEY=dummy-key",
        "-e",
        "OPENAI_API_BASE=https://openrouter.ai/api/v1",
        "-e",
        "MSWEA_MODEL_BACKEND=",
        "-e",
        "http_proxy=http://proxy.internal:8080",
        "-e",
        "HTTP_PROXY=http://proxy.internal:8080",
        "-e",
        "https_proxy=http://proxy.internal:8080",
        "-e",
        "HTTPS_PROXY=http://proxy.internal:8080",
        "csc6052-mini-swe-agent",
        "mini",
        "-t",
        "Read /workspace/task/prompt.md, inspect /workspace/repo, and modify /workspace/repo to satisfy the staged requirements while preserving prior behavior.",
    ]
