from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.harness.common import run_stage
from benchmark.templates import get_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one benchmark stage against an agent backend."
    )
    parser.add_argument("--template", default="project-1")
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--repo-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "Agent command to run after '--'. "
            "Use placeholders like {workspace_dir}, {workspace_repo_dir}, "
            "{container_repo_dir}, {container_prompt_path}, {prompt_text}, and {stage_id}."
        ),
    )
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("provide an agent command after '--'")
    return args


def main() -> int:
    args = parse_args()
    template = get_template(args.template)
    stage = template.get_stage(args.stage)
    repo_dir = args.repo_dir or (args.results_dir / "repo")
    try:
        result = run_stage(
            template=template,
            stage=stage,
            repo_dir=repo_dir,
            results_dir=args.results_dir,
            command=args.command,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if result.agent_exit_code != 0:
        return result.agent_exit_code
    return result.evaluation_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
