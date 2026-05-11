from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from benchmark.harness.cost import aggregate_trajectory_costs
from benchmark.harness.common import run_stage, write_json_artifact
from benchmark.harness.metrics import compute_trajectory_scores
from benchmark.templates import get_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one full staged trajectory against an agent backend."
    )
    parser.add_argument("--template", default="project-1")
    parser.add_argument("--repo-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--start-stage", type=int, default=1)
    parser.add_argument("--end-stage", type=int, default=None)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "Agent command to run after '--'. "
            "The harness invokes it once per stage with placeholders rendered."
        ),
    )
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("provide an agent command after '--'")
    return args


def run_trajectory(
    *,
    template_slug: str,
    results_dir: Path,
    command: Sequence[str],
    repo_dir: Path | None = None,
    start_stage: int = 1,
    end_stage: int | None = None,
) -> int:
    template = get_template(template_slug)
    if end_stage is None:
        end_stage = template.max_stage
    results_root = results_dir.resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    repo_dir = (repo_dir or (results_root / "repo")).resolve()

    stage_results: list[dict[str, object]] = []
    exit_code = 0

    for stage_number in range(start_stage, end_stage + 1):
        stage = template.get_stage(stage_number)
        stage_results_dir = results_root / stage.stage_id
        try:
            result = run_stage(
                template=template,
                stage=stage,
                repo_dir=repo_dir,
                results_dir=stage_results_dir,
                command=command,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        stage_results.append(result.to_json())
        if result.agent_exit_code != 0:
            exit_code = result.agent_exit_code
            break
        if result.evaluation_exit_code != 0:
            exit_code = result.evaluation_exit_code
            break

    payload = {
        "template": template.slug,
        "repo_dir": str(repo_dir),
        "start_stage": start_stage,
        "end_stage": end_stage,
        "stages": stage_results,
    }
    payload.update(
        compute_trajectory_scores(
            stage_results,
            start_stage=start_stage,
            end_stage=end_stage,
            total_stages=template.max_stage,
        )
    )
    payload.update(aggregate_trajectory_costs(stage_results))
    write_json_artifact(results_root / "trajectory.json", payload)
    return exit_code


def main() -> int:
    args = parse_args()
    return run_trajectory(
        template_slug=args.template,
        results_dir=args.results_dir,
        command=args.command,
        repo_dir=args.repo_dir,
        start_stage=args.start_stage,
        end_stage=args.end_stage,
    )


if __name__ == "__main__":
    raise SystemExit(main())
