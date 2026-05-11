from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.harness.common import (
    ensure_agent_repo_dir,
    prepare_agent_workspace,
    write_json_artifact,
)
from benchmark.templates import get_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize one isolated stage workspace without running an agent."
    )
    parser.add_argument("--template", default="project-1")
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--repo-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.results_dir = args.results_dir.resolve()
    template = get_template(args.template)
    stage = template.get_stage(args.stage)
    repo_dir = ensure_agent_repo_dir(
        (args.repo_dir.resolve() if args.repo_dir is not None else (args.results_dir / "repo"))
    )
    args.results_dir.mkdir(parents=True, exist_ok=True)

    workspace_dir, workspace_repo_dir, workspace_task_dir, prompt_path = (
        prepare_agent_workspace(
            template=template,
            stage=stage,
            repo_dir=repo_dir,
            results_dir=args.results_dir,
        )
    )

    metadata = {
        "template": template.slug,
        "stage": stage.number,
        "stage_id": stage.stage_id,
        "repo_dir": str(repo_dir.resolve()),
        "workspace_dir": str(workspace_dir.resolve()),
        "workspace_repo_dir": str(workspace_repo_dir.resolve()),
        "workspace_task_dir": str(workspace_task_dir.resolve()),
        "prompt_path": str(prompt_path.resolve()),
    }
    write_json_artifact(args.results_dir / "prepared-workspace.json", metadata)

    print(workspace_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
