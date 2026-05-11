from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Sequence

from benchmark.harness.common import (
    sanitize_command_for_artifacts,
    write_json_artifact,
)
from benchmark.harness.run_trajectory import run_trajectory
from benchmark.templates import get_template


RUN_MANIFEST_NAME = "run-manifest.json"
SUBCOMMANDS = {"run", "list", "show"}
SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify_path_component(value: str) -> str:
    slug = SAFE_COMPONENT_RE.sub("__", value.strip())
    slug = slug.strip(".")
    if not slug:
        raise ValueError("path components must contain at least one non-separator character")
    return slug


def utc_timestamp_slug(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def allocate_run_dir(
    *,
    runs_root: Path,
    framework: str,
    model: str,
    template: str,
    now: datetime | None = None,
) -> tuple[str, Path, dict[str, str]]:
    path_components = {
        "framework": slugify_path_component(framework),
        "model": slugify_path_component(model),
        "template": slugify_path_component(template),
    }
    base_dir = (
        runs_root
        / path_components["framework"]
        / path_components["model"]
        / path_components["template"]
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    base_run_id = utc_timestamp_slug(now)
    run_id = base_run_id
    suffix = 1
    while (base_dir / run_id).exists():
        run_id = f"{base_run_id}-{suffix:02d}"
        suffix += 1
    return run_id, base_dir / run_id, path_components


def normalize_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    if not normalized:
        raise ValueError("provide an agent command after '--'")
    return normalized


def build_run_manifest(
    *,
    runs_root: Path,
    run_dir: Path,
    run_id: str,
    framework: str,
    framework_slug: str,
    model: str,
    model_slug: str,
    template: str,
    template_slug: str,
    start_stage: int,
    end_stage: int,
    repo_dir: Path | None,
    command: Sequence[str],
    created_at: datetime | None = None,
    status: str = "running",
    exit_code: int | None = None,
    error_message: str | None = None,
    experiment_id: str | None = None,
    agent_id: str | None = None,
    repeat_index: int | None = None,
) -> dict[str, object]:
    created_at_value = (created_at or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    )
    manifest: dict[str, object] = {
        "runs_root": str(runs_root.resolve()),
        "run_dir": str(run_dir.resolve()),
        "run_id": run_id,
        "framework": framework,
        "framework_slug": framework_slug,
        "model": model,
        "model_slug": model_slug,
        "template": template,
        "template_slug": template_slug,
        "start_stage": start_stage,
        "end_stage": end_stage,
        "repo_dir": str(repo_dir.resolve()) if repo_dir is not None else None,
        "created_at": created_at_value.isoformat(),
        "status": status,
        "exit_code": exit_code,
        "trajectory_path": str((run_dir / "trajectory.json").resolve()),
        "run_manifest_path": str((run_dir / RUN_MANIFEST_NAME).resolve()),
        "agent_command": sanitize_command_for_artifacts(command),
        "agent_command_text": shlex.join(sanitize_command_for_artifacts(command)),
    }
    if error_message is not None:
        manifest["error_message"] = error_message
    if experiment_id is not None:
        manifest["experiment_id"] = experiment_id
    if agent_id is not None:
        manifest["agent_id"] = agent_id
    if repeat_index is not None:
        manifest["repeat_index"] = repeat_index
    return manifest


def update_run_manifest_from_trajectory(run_dir: Path, manifest: dict[str, object]) -> None:
    trajectory_path = run_dir / "trajectory.json"
    if not trajectory_path.exists():
        return
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    stages = trajectory.get("stages", [])
    manifest["completed_stage_count"] = len(stages)
    if stages:
        manifest["last_stage_id"] = stages[-1].get("stage_id")
    for field in (
        "total_agent_cost_usd",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_stage_count",
        "missing_cost_stage_count",
        "cost_complete",
        "weighted_cumulative_correctness",
        "final_checkpoint_correctness",
        "strict_trajectory_pass",
        "weighted_current_stage_correctness",
        "weighted_regression_stability",
        "regression_introduction_count",
    ):
        if field in trajectory:
            manifest[field] = trajectory[field]


def run_managed_trajectory(
    *,
    runs_root: Path,
    framework: str,
    model: str,
    template: str,
    command: Sequence[str],
    repo_dir: Path | None = None,
    start_stage: int = 1,
    end_stage: int | None = None,
    experiment_id: str | None = None,
    agent_id: str | None = None,
    repeat_index: int | None = None,
) -> int:
    normalized_command = normalize_command(command)
    runs_root = runs_root.resolve()
    template_spec = get_template(template)
    if end_stage is None:
        end_stage = template_spec.max_stage
    run_id, run_dir, path_components = allocate_run_dir(
        runs_root=runs_root,
        framework=framework,
        model=model,
        template=template,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_run_manifest(
        runs_root=runs_root,
        run_dir=run_dir,
        run_id=run_id,
        framework=framework,
        framework_slug=path_components["framework"],
        model=model,
        model_slug=path_components["model"],
        template=template,
        template_slug=path_components["template"],
        start_stage=start_stage,
        end_stage=end_stage,
        repo_dir=repo_dir,
        command=normalized_command,
        experiment_id=experiment_id,
        agent_id=agent_id,
        repeat_index=repeat_index,
    )
    write_json_artifact(run_dir / RUN_MANIFEST_NAME, manifest)

    try:
        exit_code = run_trajectory(
            template_slug=template,
            results_dir=run_dir,
            command=normalized_command,
            repo_dir=repo_dir,
            start_stage=start_stage,
            end_stage=end_stage,
        )
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
        manifest["status"] = "failed"
        manifest["exit_code"] = exit_code
        if exc.code is not None and not isinstance(exc.code, int):
            manifest["error_message"] = str(exc.code)
        update_run_manifest_from_trajectory(run_dir, manifest)
        write_json_artifact(run_dir / RUN_MANIFEST_NAME, manifest)
        return exit_code
    except Exception as exc:
        manifest["status"] = "error"
        manifest["exit_code"] = 1
        manifest["error_message"] = f"{exc.__class__.__name__}: {exc}"
        update_run_manifest_from_trajectory(run_dir, manifest)
        write_json_artifact(run_dir / RUN_MANIFEST_NAME, manifest)
        raise

    manifest["status"] = "passed" if exit_code == 0 else "failed"
    manifest["exit_code"] = exit_code
    update_run_manifest_from_trajectory(run_dir, manifest)
    write_json_artifact(run_dir / RUN_MANIFEST_NAME, manifest)
    return exit_code


def find_run_manifests(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    manifests = sorted(runs_root.glob(f"*/*/*/*/{RUN_MANIFEST_NAME}"))
    return manifests


def load_run_record_from_manifest(manifest_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_dir = manifest_path.parent.resolve()
    trajectory_path = run_dir / "trajectory.json"
    data["run_dir"] = str(run_dir)
    data["run_manifest_path"] = str(manifest_path.resolve())
    data["trajectory_path"] = str(trajectory_path.resolve())
    data["has_trajectory"] = trajectory_path.exists()

    if trajectory_path.exists():
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
        stages = trajectory.get("stages", [])
        data["completed_stage_count"] = len(stages)
        if stages:
            data["last_stage_id"] = stages[-1].get("stage_id")
        for field in (
            "total_agent_cost_usd",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_stage_count",
            "missing_cost_stage_count",
            "cost_complete",
            "weighted_cumulative_correctness",
            "final_checkpoint_correctness",
            "strict_trajectory_pass",
            "weighted_current_stage_correctness",
            "weighted_regression_stability",
            "regression_introduction_count",
        ):
            if field in trajectory:
                data[field] = trajectory[field]
    else:
        data.setdefault("completed_stage_count", 0)
        if data.get("status") == "running":
            data["status"] = "incomplete"

    data.setdefault("total_agent_cost_usd", 0.0)
    data.setdefault("input_tokens", None)
    data.setdefault("output_tokens", None)
    data.setdefault("total_tokens", None)
    data.setdefault("cost_stage_count", 0)
    data.setdefault("missing_cost_stage_count", data.get("completed_stage_count", 0))
    data.setdefault("cost_complete", False)
    data.setdefault("weighted_cumulative_correctness", 0.0)
    data.setdefault("final_checkpoint_correctness", 0.0)
    data.setdefault("strict_trajectory_pass", 0)

    return data


def collect_run_records(runs_root: Path) -> list[dict[str, Any]]:
    records = [load_run_record_from_manifest(path) for path in find_run_manifests(runs_root)]
    return sorted(
        records,
        key=lambda item: (
            item.get("framework", ""),
            item.get("model", ""),
            item.get("template", ""),
            item.get("run_id", ""),
        ),
    )


def format_rows(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    return "\n".join(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )


def render_run_list(records: list[dict[str, Any]], runs_root: Path) -> str:
    header = [
        "framework",
        "model",
        "template",
        "run_id",
        "status",
        "stages",
        "wcc",
        "cost_usd",
        "path",
    ]
    rows = [header]
    for record in records:
        rows.append(
            [
                str(record.get("framework", "")),
                str(record.get("model", "")),
                str(record.get("template", "")),
                str(record.get("run_id", "")),
                str(record.get("status", "")),
                f"{record.get('start_stage', '?')}-{record.get('end_stage', '?')}",
                format_score_summary(record),
                format_cost_summary(record),
                str(record.get("run_dir", "")),
            ]
        )
    body = format_rows(rows) if rows else ""
    if not records:
        body = "(no managed runs found)"
    return f"Managed runs under {runs_root.resolve()}\n{body}\n"


def render_run_detail(record: dict[str, Any]) -> str:
    lines = [
        f"run_dir: {record.get('run_dir', '')}",
        f"framework: {record.get('framework', '')}",
        f"model: {record.get('model', '')}",
        f"template: {record.get('template', '')}",
        f"run_id: {record.get('run_id', '')}",
        f"status: {record.get('status', '')}",
        f"stages: {record.get('start_stage', '?')}-{record.get('end_stage', '?')}",
        f"completed_stage_count: {record.get('completed_stage_count', 0)}",
        f"weighted_cumulative_correctness: {record.get('weighted_cumulative_correctness', 0.0)}",
        f"final_checkpoint_correctness: {record.get('final_checkpoint_correctness', 0.0)}",
        f"strict_trajectory_pass: {record.get('strict_trajectory_pass', 0)}",
        f"weighted_current_stage_correctness: {record.get('weighted_current_stage_correctness', 0.0)}",
        f"weighted_regression_stability: {record.get('weighted_regression_stability', 0.0)}",
        f"regression_introduction_count: {record.get('regression_introduction_count', 0)}",
        f"total_agent_cost_usd: {record.get('total_agent_cost_usd', 0.0)}",
        f"cost_complete: {record.get('cost_complete', False)}",
        f"cost_stage_count: {record.get('cost_stage_count', 0)}",
        f"missing_cost_stage_count: {record.get('missing_cost_stage_count', 0)}",
        f"repo_dir: {record.get('repo_dir', '')}",
        f"trajectory_path: {record.get('trajectory_path', '')}",
        f"run_manifest_path: {record.get('run_manifest_path', '')}",
    ]
    if record.get("input_tokens") is not None:
        lines.append(f"input_tokens: {record['input_tokens']}")
    if record.get("output_tokens") is not None:
        lines.append(f"output_tokens: {record['output_tokens']}")
    if record.get("total_tokens") is not None:
        lines.append(f"total_tokens: {record['total_tokens']}")
    last_stage_id = record.get("last_stage_id")
    if last_stage_id:
        lines.append(f"last_stage_id: {last_stage_id}")
    error_message = record.get("error_message")
    if error_message:
        lines.append(f"error_message: {error_message}")
    return "\n".join(lines) + "\n"


def format_cost_summary(record: dict[str, Any]) -> str:
    total = float(record.get("total_agent_cost_usd", 0.0) or 0.0)
    suffix = "" if record.get("cost_complete") else " (partial)"
    return f"{total:.4f}{suffix}"


def format_score_summary(record: dict[str, Any]) -> str:
    score = float(record.get("weighted_cumulative_correctness", 0.0) or 0.0)
    return f"{score:.2f}"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0] not in SUBCOMMANDS and argv[0] not in {"-h", "--help"}:
        argv.insert(0, "run")

    parser = argparse.ArgumentParser(
        description="Manage a shared run root across frameworks, models, and templates."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Allocate a canonical managed run directory and launch a trajectory.",
    )
    run_parser.add_argument("--runs-root", type=Path, required=True)
    run_parser.add_argument("--framework", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--template", default="project-1")
    run_parser.add_argument("--repo-dir", type=Path, default=None)
    run_parser.add_argument("--start-stage", type=int, default=1)
    run_parser.add_argument("--end-stage", type=int, default=None)
    run_parser.add_argument("--experiment-id", default=None)
    run_parser.add_argument("--agent-id", default=None)
    run_parser.add_argument("--repeat-index", type=int, default=None)
    run_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Agent command to run after '--'.",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List managed runs under a shared run root.",
    )
    list_parser.add_argument("--runs-root", type=Path, required=True)
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser(
        "show",
        help="Show details for one managed run directory.",
    )
    show_parser.add_argument("--run-dir", type=Path, required=True)
    show_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.subcommand == "run":
        args.command = normalize_command(args.command)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.subcommand == "run":
        return run_managed_trajectory(
            runs_root=args.runs_root,
            framework=args.framework,
            model=args.model,
            template=args.template,
            command=args.command,
            repo_dir=args.repo_dir,
            start_stage=args.start_stage,
            end_stage=args.end_stage,
            experiment_id=args.experiment_id,
            agent_id=args.agent_id,
            repeat_index=args.repeat_index,
        )

    if args.subcommand == "list":
        records = collect_run_records(args.runs_root.resolve())
        if args.json:
            print(json.dumps({"runs_root": str(args.runs_root.resolve()), "runs": records}, indent=2))
        else:
            print(render_run_list(records, args.runs_root), end="")
        return 0

    record = load_run_record_from_manifest(args.run_dir.resolve() / RUN_MANIFEST_NAME)
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(render_run_detail(record), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
