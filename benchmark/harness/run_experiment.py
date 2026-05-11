from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO, Sequence

import yaml
from tqdm import tqdm

from benchmark.harness.common import write_json_artifact
from benchmark.harness.run_managed_trajectory import collect_run_records
from benchmark.templates import REPO_ROOT, TEMPLATES, get_template


SUPPORTED_FRAMEWORKS = {"codex", "mini-swe-agent", "claude"}
DEFAULT_PROJECTS = tuple(TEMPLATES)
MANAGED_WRAPPER = REPO_ROOT / "scripts" / "managed" / "go.sh"


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    framework: str
    model: str
    env: dict[str, str]


@dataclass(frozen=True)
class ProjectConfig:
    slug: str
    runs_per_project: int
    start_stage: int
    end_stage: int


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    runs_root: Path
    agents: tuple[AgentConfig, ...]
    projects: tuple[ProjectConfig, ...]
    fail_fast: bool
    output_dir: Path | None = None
    stdout: str = "inherit"
    stderr: str = "inherit"


@dataclass(frozen=True)
class PlannedRun:
    experiment_id: str
    runs_root: Path
    agent: AgentConfig
    project: ProjectConfig
    repeat_index: int

    @property
    def label(self) -> str:
        return (
            f"agent={self.agent.agent_id} "
            f"project={self.project.slug} "
            f"repeat={self.repeat_index}/{self.project.runs_per_project}"
        )


def load_config(path: Path, *, environ: dict[str, str] | None = None) -> ExperimentConfig:
    environ = environ if environ is not None else dict(os.environ)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"config file does not exist: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse YAML config: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")

    experiment_id = _required_str(raw, "experiment_id")
    runs_root = Path(str(raw.get("runs_root", ".agent_runs"))).expanduser()
    if not runs_root.is_absolute():
        runs_root = (path.parent / runs_root).resolve()
    output_dir = Path(str(raw.get("output_dir", runs_root))).expanduser()
    if not output_dir.is_absolute():
        output_dir = (path.parent / output_dir).resolve()

    default_runs = _positive_int(raw.get("default_runs_per_project", 1), "default_runs_per_project")
    default_start_stage = _positive_int(raw.get("start_stage", 1), "start_stage")
    default_end_stage = raw.get("end_stage", None)
    agents = _parse_agents(raw.get("agents"), environ=environ)
    projects = _parse_projects(
        raw.get("projects"),
        default_runs=default_runs,
        default_start_stage=default_start_stage,
        default_end_stage=default_end_stage,
    )
    fail_fast = bool(raw.get("fail_fast", False))
    stdout, stderr = _parse_output_config(raw.get("output", {}))
    return ExperimentConfig(
        experiment_id=experiment_id,
        runs_root=runs_root,
        agents=tuple(agents),
        projects=tuple(projects),
        fail_fast=fail_fast,
        output_dir=output_dir,
        stdout=stdout,
        stderr=stderr,
    )


def _required_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _optional_positive_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, name)


def _parse_agents(value: Any, *, environ: dict[str, str]) -> list[AgentConfig]:
    if not isinstance(value, list) or not value:
        raise ValueError("agents must be a non-empty list")

    agents: list[AgentConfig] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"agents[{index}] must be a mapping")
        agent_id = _required_str(item, "id")
        if agent_id in seen_ids:
            raise ValueError(f"duplicate agent id: {agent_id}")
        seen_ids.add(agent_id)

        framework = _required_str(item, "framework")
        framework = _normalize_framework(framework)
        model = _required_str(item, "model")
        env = _resolve_env_mapping(item.get("env", {}), environ=environ, context=agent_id)
        agents.append(
            AgentConfig(
                agent_id=agent_id,
                framework=framework,
                model=model,
                env=env,
            )
        )
    return agents


def _normalize_framework(value: str) -> str:
    aliases = {
        "mini": "mini-swe-agent",
        "mini-swe": "mini-swe-agent",
        "claude-code": "claude",
    }
    normalized = aliases.get(value, value)
    if normalized not in SUPPORTED_FRAMEWORKS:
        raise ValueError(
            f"unsupported framework '{value}'; use one of {sorted(SUPPORTED_FRAMEWORKS)}"
        )
    return normalized


def _resolve_env_mapping(value: Any, *, environ: dict[str, str], context: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"env for {context} must be a mapping")

    resolved: dict[str, str] = {}
    for name, raw_value in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"env names for {context} must be non-empty strings")
        if isinstance(raw_value, dict):
            source_name = raw_value.get("from_env")
            if not isinstance(source_name, str) or not source_name:
                raise ValueError(f"env {name} for {context} has invalid from_env")
            if source_name in environ and environ[source_name] != "":
                resolved[name] = environ[source_name]
            elif "default" in raw_value:
                default_value = raw_value["default"]
                if default_value is None:
                    continue
                if not isinstance(default_value, (str, int, float, bool)):
                    raise ValueError(f"env {name} for {context} has invalid default")
                resolved[name] = str(default_value)
            else:
                raise ValueError(
                    f"env {name} for {context} references missing variable {source_name}"
                )
        elif isinstance(raw_value, (str, int, float, bool)):
            resolved[name] = str(raw_value)
        elif raw_value is None:
            continue
        else:
            raise ValueError(f"env {name} for {context} must be scalar or from_env")
    return resolved


def _parse_output_config(value: Any) -> tuple[str, str]:
    if value is None:
        return "inherit", "inherit"
    if value is False:
        return "discard", "discard"
    if value is True:
        return "inherit", "inherit"
    if not isinstance(value, dict):
        raise ValueError("output must be a mapping or boolean")

    stdout = _parse_output_target(value.get("stdout", "inherit"), "output.stdout")
    stderr = _parse_output_target(value.get("stderr", "inherit"), "output.stderr")
    return stdout, stderr


def _parse_output_target(value: Any, name: str) -> str:
    if value is False:
        return "discard"
    if value is True:
        return "inherit"
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _parse_projects(
    value: Any,
    *,
    default_runs: int,
    default_start_stage: int,
    default_end_stage: Any,
) -> list[ProjectConfig]:
    project_items = list(DEFAULT_PROJECTS) if value is None else value
    if not isinstance(project_items, list) or not project_items:
        raise ValueError("projects must be a non-empty list")

    projects: list[ProjectConfig] = []
    seen_slugs: set[str] = set()
    for index, item in enumerate(project_items, start=1):
        if isinstance(item, str):
            slug = item
            runs_per_project = default_runs
            start_stage = default_start_stage
            end_stage = _optional_positive_int(default_end_stage, "end_stage")
        elif isinstance(item, dict):
            slug = _required_str(item, "slug")
            runs_per_project = _positive_int(
                item.get("runs_per_project", default_runs),
                f"projects[{index}].runs_per_project",
            )
            start_stage = _positive_int(
                item.get("start_stage", default_start_stage),
                f"projects[{index}].start_stage",
            )
            end_stage = _optional_positive_int(
                item.get("end_stage", default_end_stage),
                f"projects[{index}].end_stage",
            )
        else:
            raise ValueError(f"projects[{index}] must be a slug string or mapping")

        if slug in seen_slugs:
            raise ValueError(f"duplicate project slug: {slug}")
        seen_slugs.add(slug)

        template = get_template(slug)
        resolved_end_stage = end_stage if end_stage is not None else template.max_stage
        if start_stage > resolved_end_stage:
            raise ValueError(f"{slug} start_stage cannot exceed end_stage")
        if resolved_end_stage > template.max_stage:
            raise ValueError(f"{slug} end_stage exceeds max stage {template.max_stage}")
        projects.append(
            ProjectConfig(
                slug=slug,
                runs_per_project=runs_per_project,
                start_stage=start_stage,
                end_stage=resolved_end_stage,
            )
        )
    return projects


def build_run_matrix(config: ExperimentConfig) -> list[PlannedRun]:
    return [
        PlannedRun(
            experiment_id=config.experiment_id,
            runs_root=config.runs_root,
            agent=agent,
            project=project,
            repeat_index=repeat_index,
        )
        for agent in config.agents
        for project in config.projects
        for repeat_index in range(1, project.runs_per_project + 1)
    ]


def build_run_environment(planned_run: PlannedRun, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)
    env.update(planned_run.agent.env)
    env.update(
        {
            "FRAMEWORK": planned_run.agent.framework,
            "MODEL": planned_run.agent.model,
            "RUNS_ROOT": str(planned_run.runs_root),
            "TEMPLATE": planned_run.project.slug,
            "STAGE_NUM": str(planned_run.project.start_stage),
            "END_STAGE": str(planned_run.project.end_stage),
            "EXPERIMENT_ID": planned_run.experiment_id,
            "AGENT_ID": planned_run.agent.agent_id,
            "REPEAT_INDEX": str(planned_run.repeat_index),
        }
    )
    return env


def execute_run(planned_run: PlannedRun, config: ExperimentConfig) -> int:
    with ExitStack() as stack:
        stdout = _open_output_target(planned_run, config.stdout, stack)
        stderr = stdout if config.stderr == config.stdout else _open_output_target(
            planned_run, config.stderr, stack
        )
        completed = subprocess.run(
            ["bash", str(MANAGED_WRAPPER)],
            cwd=REPO_ROOT,
            env=build_run_environment(planned_run),
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
        return completed.returncode


def _open_output_target(
    planned_run: PlannedRun,
    target: str,
    stack: ExitStack,
) -> int | IO[str] | None:
    normalized = target.lower()
    if normalized in {"inherit", "terminal"}:
        return None
    if normalized in {"discard", "null"}:
        return subprocess.DEVNULL

    path = _render_output_path(planned_run, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    return stack.enter_context(path.open("w", encoding="utf-8"))


def _render_output_path(planned_run: PlannedRun, target: str) -> Path:
    rendered = target.format(
        experiment_id=planned_run.experiment_id,
        agent_id=planned_run.agent.agent_id,
        framework=planned_run.agent.framework,
        model=planned_run.agent.model,
        project=planned_run.project.slug,
        repeat_index=planned_run.repeat_index,
    )
    path = Path(rendered).expanduser()
    if not path.is_absolute():
        path = planned_run.runs_root / path
    return path


def run_experiment(config: ExperimentConfig, *, dry_run: bool = False) -> int:
    matrix = build_run_matrix(config)
    if dry_run:
        for planned_run in matrix:
            print(planned_run.label)
        return 0

    exit_code = 0
    with tqdm(total=len(matrix), desc=config.experiment_id, unit="run") as progress:
        for planned_run in matrix:
            progress.set_postfix_str(planned_run.label)
            run_exit_code = execute_run(planned_run, config)
            if run_exit_code != 0:
                exit_code = run_exit_code
                if config.fail_fast:
                    progress.update(1)
                    break
            progress.update(1)
    records = filter_experiment_records(
        collect_run_records(config.runs_root),
        experiment_id=config.experiment_id,
    )
    summaries = summarize_by_agent(records)
    print(render_summary_table(summaries), end="")
    write_summary_artifacts(config, records, summaries)
    return exit_code


def filter_experiment_records(
    records: list[dict[str, Any]],
    *,
    experiment_id: str | None,
) -> list[dict[str, Any]]:
    if experiment_id is None:
        return records
    return [record for record in records if record.get("experiment_id") == experiment_id]


def summarize_by_agent(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        agent_id = str(record.get("agent_id") or record.get("framework") or "unknown")
        grouped.setdefault(agent_id, []).append(record)

    summaries: list[dict[str, Any]] = []
    for agent_id, group in sorted(grouped.items()):
        summaries.append(
            {
                "agent": agent_id,
                "framework": _consistent_text(group, "framework"),
                "model": _consistent_text(group, "model"),
                "runs": len(group),
                "passed_runs": sum(1 for record in group if record.get("status") == "passed"),
                "avg_weighted_cumulative_correctness": _avg(group, "weighted_cumulative_correctness"),
                "avg_final_checkpoint_correctness": _avg(group, "final_checkpoint_correctness"),
                "strict_pass_rate": _avg(group, "strict_trajectory_pass"),
                "avg_current_stage_correctness": _avg(group, "weighted_current_stage_correctness"),
                "avg_regression_stability": _avg(group, "weighted_regression_stability"),
                "avg_regression_introductions": _avg(group, "regression_introduction_count"),
                "avg_cost_usd": _avg(group, "total_agent_cost_usd"),
                "cost_complete_runs": sum(1 for record in group if record.get("cost_complete")),
            }
        )
    return summaries


def _consistent_text(records: list[dict[str, Any]], key: str) -> str:
    values = sorted({str(record.get(key, "")) for record in records if record.get(key)})
    return values[0] if len(values) == 1 else ",".join(values)


def _avg(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(float(record.get(key) or 0.0) for record in records) / len(records)


def render_summary_table(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return "(no experiment runs found)\n"
    headers = [
        "agent",
        "framework",
        "model",
        "runs",
        "passed_runs",
        "avg_wcc",
        "avg_final",
        "strict_pass_rate",
        "avg_current",
        "avg_regression",
        "avg_regressions",
        "avg_cost_usd",
        "cost_complete_runs",
    ]
    rows = [headers]
    for summary in summaries:
        rows.append(
            [
                str(summary["agent"]),
                str(summary["framework"]),
                str(summary["model"]),
                str(summary["runs"]),
                str(summary["passed_runs"]),
                f"{summary['avg_weighted_cumulative_correctness']:.2f}",
                f"{summary['avg_final_checkpoint_correctness']:.2f}",
                f"{summary['strict_pass_rate']:.2f}",
                f"{summary['avg_current_stage_correctness']:.2f}",
                f"{summary['avg_regression_stability']:.2f}",
                f"{summary['avg_regression_introductions']:.2f}",
                f"{summary['avg_cost_usd']:.4f}",
                str(summary["cost_complete_runs"]),
            ]
        )

    separator = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def write_summary_artifacts(
    config: ExperimentConfig,
    records: list[dict[str, Any]],
    summaries: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    output_dir = config.output_dir or config.runs_root
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{config.experiment_id}-summary.json"
    table_path = output_dir / f"{config.experiment_id}-results.md"
    summaries = summaries if summaries is not None else summarize_by_agent(records)
    payload = {
        "experiment_id": config.experiment_id,
        "runs_root": str(config.runs_root),
        "output_dir": str(output_dir),
        "run_count": len(records),
        "agents": summaries,
    }
    write_json_artifact(summary_path, payload)
    table_path.write_text(render_summary_table(summaries), encoding="utf-8")
    return summary_path, table_path


def write_summary_artifact(config: ExperimentConfig, records: list[dict[str, Any]]) -> Path:
    summary_path, _table_path = write_summary_artifacts(config, records)
    return summary_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or summarize a config-driven multi-agent benchmark experiment."
    )
    parser.add_argument("subcommand", choices=("run", "summary"))
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="For summary, include all runs under runs_root instead of filtering by experiment_id.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if args.subcommand == "run":
        return run_experiment(config, dry_run=args.dry_run)

    experiment_id = None if args.all_runs else config.experiment_id
    records = filter_experiment_records(
        collect_run_records(config.runs_root),
        experiment_id=experiment_id,
    )
    summaries = summarize_by_agent(records)
    print(render_summary_table(summaries), end="")
    write_summary_artifacts(config, records, summaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
