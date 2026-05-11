from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StageSpec:
    number: int
    prompt_path: Path
    evaluation_path: Path
    evaluation_paths: tuple[Path, ...]

    @property
    def stage_id(self) -> str:
        return f"stage_{self.number:02d}"


@dataclass(frozen=True)
class TemplateSpec:
    slug: str
    display_name: str
    taskbed_root: Path
    evaluation_root: Path
    starter_repo_path: Path | None
    stages: tuple[StageSpec, ...]

    def get_stage(self, number: int) -> StageSpec:
        for stage in self.stages:
            if stage.number == number:
                return stage
        raise ValueError(f"unknown stage for {self.slug}: {number}")

    @property
    def max_stage(self) -> int:
        if not self.stages:
            raise ValueError(f"template {self.slug} has no stages")
        return self.stages[-1].number


def _build_template(
    *,
    slug: str,
    display_name: str,
    task_dir_name: str,
    evaluation_dir_name: str,
    stage_count: int,
    evaluation_stage_numbers_by_stage: dict[int, tuple[int, ...]] | None = None,
) -> TemplateSpec:
    taskbed_root = REPO_ROOT / "tasks" / task_dir_name
    evaluation_root = REPO_ROOT / "evaluation" / evaluation_dir_name
    evaluation_stage_numbers_by_stage = evaluation_stage_numbers_by_stage or {}
    return TemplateSpec(
        slug=slug,
        display_name=display_name,
        taskbed_root=taskbed_root,
        evaluation_root=evaluation_root,
        starter_repo_path=taskbed_root / "starter_repo",
        stages=tuple(
            StageSpec(
                number=number,
                prompt_path=taskbed_root / f"stage_{number:02d}" / "prompt.md",
                evaluation_path=evaluation_root / f"stage_{number:02d}" / "hidden_tests.py",
                evaluation_paths=tuple(
                    evaluation_root / f"stage_{candidate:02d}" / "hidden_tests.py"
                    for candidate in evaluation_stage_numbers_by_stage.get(
                        number,
                        (number,),
                    )
                ),
            )
            for number in range(1, stage_count + 1)
        ),
    )


PROJECT_1 = _build_template(
    slug="project-1",
    display_name="Finance Tracker",
    task_dir_name="project-1",
    evaluation_dir_name="project_1",
    stage_count=6,
)

PROJECT_2 = _build_template(
    slug="project-2",
    display_name="Text Analyzer",
    task_dir_name="project-2",
    evaluation_dir_name="project_2",
    stage_count=6,
)

PROJECT_3 = _build_template(
    slug="project-3",
    display_name="Course Planner",
    task_dir_name="project-3",
    evaluation_dir_name="project_3",
    stage_count=6,
)

PROJECT_4 = _build_template(
    slug="project-4",
    display_name="Knowledge Base Manager",
    task_dir_name="project-4",
    evaluation_dir_name="project_4",
    stage_count=6,
)

PROJECT_5 = _build_template(
    slug="project-5",
    display_name="Configuration Policy Manager",
    task_dir_name="project-5",
    evaluation_dir_name="project_5",
    stage_count=6,
)

TEMPLATES = {
    template.slug: template
    for template in (
        PROJECT_1,
        PROJECT_2,
        PROJECT_3,
        PROJECT_4,
        PROJECT_5,
    )
}


def get_template(slug: str) -> TemplateSpec:
    try:
        return TEMPLATES[slug]
    except KeyError as exc:
        raise ValueError(f"unknown template: {slug}") from exc
