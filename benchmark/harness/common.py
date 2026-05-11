from __future__ import annotations
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping
from typing import Sequence

from benchmark.harness.cost import summarize_workspace_cost
from benchmark.harness.metrics import parse_pytest_junit
from benchmark.templates import REPO_ROOT, StageSpec, TemplateSpec


CONTAINER_WORKSPACE_DIR = "/workspace"
CONTAINER_REPO_DIR = f"{CONTAINER_WORKSPACE_DIR}/repo"
CONTAINER_TASK_DIR = f"{CONTAINER_WORKSPACE_DIR}/task"
CONTAINER_PROMPT_PATH = f"{CONTAINER_TASK_DIR}/prompt.md"
CONTAINER_RESULTS_DIR = f"{CONTAINER_WORKSPACE_DIR}/.agent-results"
COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    ".agent-results",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "finance_data.json",
    "course_planner_data.json",
    "*.pyc",
)
SENSITIVE_ENV_NAME_RE = re.compile(
    r"(?:^|_)(?:API_KEY|OAI_KEY|KEY|TOKEN|SECRET|PASSWORD)(?:_|$)"
)


@dataclass(frozen=True)
class StageRunResult:
    template: str
    stage: int
    stage_id: str
    workspace_dir: Path
    workspace_repo_dir: Path
    workspace_task_dir: Path
    task_dir: Path
    prompt_path: Path
    results_dir: Path
    repo_dir: Path
    agent_command: list[str]
    agent_cost: dict[str, object]
    agent_exit_code: int
    evaluation_exit_code: int
    test_summary: dict[str, object] | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Path):
                payload[key] = str(value)
            elif isinstance(value, tuple) and value and isinstance(value[0], Path):
                payload[key] = [str(item) for item in value]
        payload["agent_command"] = sanitize_command_for_artifacts(self.agent_command)
        return payload


@dataclass(frozen=True)
class EvaluationRunResult:
    template: str
    stage: int
    stage_id: str
    results_dir: Path
    repo_dir: Path
    evaluation_exit_code: int
    test_summary: dict[str, object]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Path):
                payload[key] = str(value)
        return payload


def materialize_stage_taskbed(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    task_dir: Path,
) -> Path:
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)

    prior_requirements_dir = task_dir / "prior_stage_requirements"
    prior_requirements_dir.mkdir(parents=True, exist_ok=True)
    for candidate in template.stages:
        if candidate.number >= stage.number:
            break
        target_path = (
            prior_requirements_dir / f"stage_{candidate.number:02d}.md"
        )
        shutil.copy2(candidate.prompt_path, target_path)

    prompt_path = task_dir / "prompt.md"
    original_prompt = stage.prompt_path.read_text(encoding="utf-8")
    prompt_preamble = (
        "# Taskbed Notes\n\n"
        "Before making changes, inspect the current repository implementation in "
        "`/workspace/repo` and reconcile it with the staged requirements.\n\n"
        "Run repository commands from `/workspace/repo`. If the staged prompt defines "
        "a CLI contract such as `uv run python -m ...`, visible and hidden checks use "
        "that exact entry point.\n\n"
        "Treat generated runtime artifacts as transient, not part of the final "
        "submission. Clean up files such as `./finance_data.json` or "
        "`./course_planner_data.json` before you submit; evaluation starts from a "
        "clean repository snapshot and ignores those default runtime data files.\n\n"
    )
    if stage.number == 1:
        prompt_preamble += (
            "There is no prior stage for stage 1, so "
            "`/workspace/task/prior_stage_requirements/` is expected to be empty.\n\n"
        )
    else:
        prompt_preamble += (
            "You can access the visible requirements from previous stages under "
            "`/workspace/task/prior_stage_requirements/`. Use them to preserve prior "
            "behavior while implementing the current stage.\n\n"
        )
    prompt_path.write_text(
        prompt_preamble + original_prompt,
        encoding="utf-8",
    )
    return prompt_path


def resolve_repo_dir(repo_dir: Path, *, create: bool) -> Path:
    resolved = repo_dir.expanduser().resolve()
    if resolved == REPO_ROOT:
        raise ValueError(
            "repo-dir points to the benchmark repository root. "
            "Use a separate submission repo, or omit --repo-dir so the harness creates one."
        )
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    elif not resolved.exists():
        raise ValueError(f"repo-dir does not exist: {resolved}")
    return resolved


def ensure_agent_repo_dir(repo_dir: Path) -> Path:
    return resolve_repo_dir(repo_dir, create=True)


def ensure_submission_repo_dir(repo_dir: Path) -> Path:
    return resolve_repo_dir(repo_dir, create=False)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def copy_repo_tree(source_dir: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    if not source_dir.exists():
        destination_dir.mkdir(parents=True, exist_ok=True)
        return
    shutil.copytree(source_dir, destination_dir, ignore=COPY_IGNORE)


def repo_has_user_files(repo_dir: Path) -> bool:
    return any(child.name != ".git" for child in repo_dir.iterdir())


def seed_repo_from_starter(template: TemplateSpec, repo_dir: Path) -> None:
    starter_repo_path = template.starter_repo_path
    if starter_repo_path is None or repo_has_user_files(repo_dir):
        return

    for child in starter_repo_path.iterdir():
        target = repo_dir / child.name
        if child.is_symlink():
            target.symlink_to(child.readlink())
        elif child.is_dir():
            shutil.copytree(child, target, ignore=COPY_IGNORE)
        else:
            shutil.copy2(child, target)


def sync_repo_back(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for child in destination_dir.iterdir():
        if child.name == ".git":
            continue
        remove_path(child)

    for child in source_dir.iterdir():
        if COPY_IGNORE(".", [child.name]):
            continue
        target = destination_dir / child.name
        if child.is_symlink():
            target.symlink_to(child.readlink())
        elif child.is_dir():
            shutil.copytree(child, target, ignore=COPY_IGNORE)
        else:
            shutil.copy2(child, target)


def prepare_agent_workspace(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    repo_dir: Path,
    results_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    seed_repo_from_starter(template, repo_dir)

    workspace_dir = results_dir / "workspace"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    workspace_repo_dir = workspace_dir / "repo"
    workspace_task_dir = workspace_dir / "task"
    copy_repo_tree(repo_dir, workspace_repo_dir)
    prompt_path = materialize_stage_taskbed(
        template=template,
        stage=stage,
        task_dir=workspace_task_dir,
    )
    return workspace_dir, workspace_repo_dir, workspace_task_dir, prompt_path


def build_placeholder_mapping(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    repo_dir: Path,
    workspace_dir: Path,
    workspace_repo_dir: Path,
    workspace_task_dir: Path,
    task_dir: Path,
    prompt_path: Path,
    results_dir: Path,
) -> dict[str, str]:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    return {
        "template": template.slug,
        "stage": str(stage.number),
        "stage_number": str(stage.number),
        "stage_id": stage.stage_id,
        "repo_dir": str(repo_dir),
        "workspace_dir": str(workspace_dir),
        "workspace_repo_dir": str(workspace_repo_dir),
        "workspace_task_dir": str(workspace_task_dir),
        "workspace_prompt_path": str(prompt_path),
        "workspace_results_dir": str(workspace_dir / ".agent-results"),
        "task_dir": str(task_dir),
        "prompt_path": str(prompt_path),
        "prompt_text": prompt_text,
        "results_dir": str(results_dir),
        "container_workspace_dir": CONTAINER_WORKSPACE_DIR,
        "container_repo_dir": CONTAINER_REPO_DIR,
        "container_task_dir": CONTAINER_TASK_DIR,
        "container_prompt_path": CONTAINER_PROMPT_PATH,
        "container_results_dir": CONTAINER_RESULTS_DIR,
    }


def render_command(command: Sequence[str], mapping: dict[str, str]) -> list[str]:
    return [part.format(**mapping) for part in command]


def is_sensitive_env_name(name: str) -> bool:
    return bool(SENSITIVE_ENV_NAME_RE.search(name.strip().upper()))


def redact_command_token(token: str) -> str:
    if "=" not in token:
        if token.startswith("sk-"):
            return "<redacted>"
        return token
    name, _ = token.split("=", 1)
    if is_sensitive_env_name(name):
        return f"{name}=<redacted>"
    return token


def sanitize_command_for_artifacts(command: Sequence[str]) -> list[str]:
    sanitized: list[str] = []
    index = 0
    while index < len(command):
        part = command[index]
        if part in {"-e", "--env"} and index + 1 < len(command):
            sanitized.append(part)
            sanitized.append(redact_command_token(command[index + 1]))
            index += 2
            continue
        if part.startswith("--env="):
            env_spec = part.split("=", 1)[1]
            sanitized.append(f"--env={redact_command_token(env_spec)}")
            index += 1
            continue
        sanitized.append(redact_command_token(part))
        index += 1
    return sanitized


def write_command_artifact(path: Path, command: Sequence[str]) -> None:
    path.write_text(
        shlex.join(sanitize_command_for_artifacts(command)) + "\n",
        encoding="utf-8",
    )


def write_json_artifact(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _stream_pipe(
    *,
    pipe,
    sink,
    chunks: list[str],
) -> None:
    try:
        for line in pipe:
            chunks.append(line)
            sink.write(line)
            sink.flush()
    finally:
        pipe.close()


def run_command_with_live_output(
    *,
    command: Sequence[str],
    cwd: Path,
) -> tuple[int, str, str]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        message = (
            f"failed to execute command: {shlex.join(command)}\n"
            f"{exc.__class__.__name__}: {exc}\n"
        )
        sys.stderr.write(message)
        sys.stderr.flush()
        return 127, "", message
    assert process.stdout is not None
    assert process.stderr is not None

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_thread = threading.Thread(
        target=_stream_pipe,
        kwargs={
            "pipe": process.stdout,
            "sink": sys.stdout,
            "chunks": stdout_chunks,
        },
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_stream_pipe,
        kwargs={
            "pipe": process.stderr,
            "sink": sys.stderr,
            "chunks": stderr_chunks,
        },
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    return_code = process.wait()
    stdout_thread.join()
    stderr_thread.join()
    return return_code, "".join(stdout_chunks), "".join(stderr_chunks)


def resolve_container_runtime() -> str:
    configured_runtime = os.environ.get("BENCHMARK_CONTAINER_RUNTIME")
    if configured_runtime:
        return configured_runtime
    if shutil.which("docker"):
        return "docker"
    if shutil.which("podman"):
        return "podman"
    return "docker"


def build_evaluation_command(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    repo_dir: Path,
    results_dir: Path,
) -> list[str]:
    evaluation_paths = stage.evaluation_paths
    container_runtime = resolve_container_runtime()
    evaluator_image = os.environ.get(
        "BENCHMARK_EVALUATOR_IMAGE",
        "csc6052-project-1-evaluator",
    )
    benchmark_mount = f"{REPO_ROOT}:/benchmark:ro"
    repo_mount = f"{repo_dir}:/submission:ro"
    results_mount = f"{results_dir}:/evaluation-results"
    pytest_args = [
        "python",
        "-m",
        "pytest",
        "--import-mode=importlib",
        "-o",
        "cache_dir=/tmp/pytest-cache",
        "--junitxml=/evaluation-results/pytest-junit.xml",
        "--project-dir",
        "/submission",
        *[f"/benchmark/{path.relative_to(REPO_ROOT)}" for path in evaluation_paths],
    ]
    return [
        container_runtime,
        "run",
        "--rm",
        "-i",
        "-v",
        benchmark_mount,
        "-v",
        repo_mount,
        "-v",
        results_mount,
        evaluator_image,
        *pytest_args,
    ]


def evaluate_repo(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    repo_dir: Path,
    results_dir: Path,
) -> EvaluationRunResult:
    repo_dir = ensure_submission_repo_dir(repo_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    evaluation_command = build_evaluation_command(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )
    write_command_artifact(results_dir / "evaluation-command.txt", evaluation_command)
    evaluation_return_code, evaluation_stdout, evaluation_stderr = (
        run_command_with_live_output(
            command=evaluation_command,
            cwd=REPO_ROOT,
        )
    )
    (results_dir / "evaluation-stdout.txt").write_text(
        evaluation_stdout,
        encoding="utf-8",
    )
    (results_dir / "evaluation-stderr.txt").write_text(
        evaluation_stderr,
        encoding="utf-8",
    )
    (results_dir / "evaluation-exit-code.txt").write_text(
        f"{evaluation_return_code}\n",
        encoding="utf-8",
    )
    test_summary = parse_pytest_junit(
        results_dir / "pytest-junit.xml",
        checkpoint_stage=stage.number,
    )

    result = EvaluationRunResult(
        template=template.slug,
        stage=stage.number,
        stage_id=stage.stage_id,
        results_dir=results_dir,
        repo_dir=repo_dir,
        evaluation_exit_code=evaluation_return_code,
        test_summary=test_summary,
    )
    write_json_artifact(results_dir / "evaluation-result.json", result.to_json())
    return result


def run_stage(
    *,
    template: TemplateSpec,
    stage: StageSpec,
    repo_dir: Path,
    results_dir: Path,
    command: Sequence[str],
) -> StageRunResult:
    repo_dir = ensure_agent_repo_dir(repo_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir, workspace_repo_dir, workspace_task_dir, prompt_path = (
        prepare_agent_workspace(
            template=template,
            stage=stage,
            repo_dir=repo_dir,
            results_dir=results_dir,
        )
    )
    task_dir = workspace_task_dir

    mapping = build_placeholder_mapping(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        workspace_dir=workspace_dir,
        workspace_repo_dir=workspace_repo_dir,
        workspace_task_dir=workspace_task_dir,
        task_dir=task_dir,
        prompt_path=prompt_path,
        results_dir=results_dir,
    )
    rendered_command = render_command(command, mapping)
    sanitized_command = sanitize_command_for_artifacts(rendered_command)
    write_command_artifact(results_dir / "agent-command.txt", rendered_command)

    agent_return_code, agent_stdout, agent_stderr = run_command_with_live_output(
        command=rendered_command,
        cwd=workspace_repo_dir,
    )
    agent_cost = summarize_workspace_cost(workspace_dir)

    (results_dir / "agent-stdout.txt").write_text(
        agent_stdout,
        encoding="utf-8",
    )
    (results_dir / "agent-stderr.txt").write_text(
        agent_stderr,
        encoding="utf-8",
    )
    (results_dir / "agent-exit-code.txt").write_text(
        f"{agent_return_code}\n",
        encoding="utf-8",
    )

    if agent_return_code != 0:
        result = StageRunResult(
            template=template.slug,
            stage=stage.number,
            stage_id=stage.stage_id,
            workspace_dir=workspace_dir,
            workspace_repo_dir=workspace_repo_dir,
            workspace_task_dir=workspace_task_dir,
            task_dir=task_dir,
            prompt_path=prompt_path,
            results_dir=results_dir,
            repo_dir=repo_dir,
            agent_command=sanitized_command,
            agent_cost=agent_cost,
            agent_exit_code=agent_return_code,
            evaluation_exit_code=0,
            test_summary=None,
        )
        write_json_artifact(results_dir / "stage-result.json", result.to_json())
        return result

    sync_repo_back(workspace_repo_dir, repo_dir)

    evaluation_result = evaluate_repo(
        template=template,
        stage=stage,
        repo_dir=repo_dir,
        results_dir=results_dir,
    )

    result = StageRunResult(
        template=template.slug,
        stage=stage.number,
        stage_id=stage.stage_id,
        workspace_dir=workspace_dir,
        workspace_repo_dir=workspace_repo_dir,
        workspace_task_dir=workspace_task_dir,
        task_dir=task_dir,
        prompt_path=prompt_path,
        results_dir=results_dir,
        repo_dir=repo_dir,
        agent_command=sanitized_command,
        agent_cost=agent_cost,
        agent_exit_code=agent_return_code,
        evaluation_exit_code=evaluation_result.evaluation_exit_code,
        test_summary=evaluation_result.test_summary,
    )
    write_json_artifact(results_dir / "stage-result.json", result.to_json())
    return result
