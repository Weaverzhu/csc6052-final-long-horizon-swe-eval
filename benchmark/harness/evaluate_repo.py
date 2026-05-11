from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.harness.common import evaluate_repo
from benchmark.templates import get_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run hidden evaluation for one stage against an existing submission repo."
    )
    parser.add_argument("--template", default="project-1")
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template = get_template(args.template)
    stage = template.get_stage(args.stage)
    try:
        result = evaluate_repo(
            template=template,
            stage=stage,
            repo_dir=args.repo_dir,
            results_dir=args.results_dir.resolve(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    status = "PASS" if result.evaluation_exit_code == 0 else "FAIL"
    print(
        f"[{status}] {result.stage_id} repo={result.repo_dir} results={result.results_dir}"
    )
    return result.evaluation_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
