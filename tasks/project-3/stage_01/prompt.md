# Project 3 / Stage 01

You are starting from a benchmark-provided starter repository.

Build a CLI course planner in Python 3.11. The repository must expose:

```bash
uv run python -m course_planner <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup, including `pyproject.toml` and the package entry point
- standard library only
- no network access
- keep the implementation in a package such as `course_planner/` or `src/course_planner/`
- keep the CLI entry thin and split the implementation across multiple modules
- a single top-level `main.py` solution does not satisfy this benchmark

## Shared state and output rules

- the application must persist state across separate process invocations using the default file `./course_planner_data.json`
- validation failures must exit with non-zero status and write a short error message to stderr
- read commands must support `--format json`
- JSON output must be deterministic and stable across runs

## Change request

Build a CLI course planner that lets the user register courses and sections, choose sections for a draft schedule, and inspect stored sections.

## Commands that must work

```bash
uv run python -m course_planner course add --code CODE --title TITLE --credits INT
uv run python -m course_planner section add --course CODE --section ID --days DAYS --start HH:MM --end HH:MM
uv run python -m course_planner section list --course CODE --format json
uv run python -m course_planner schedule add --course CODE --section ID
uv run python -m course_planner schedule list --format json
```

## Required behavior

- course codes and section ids are matched exactly as provided
- `credits` must parse as an integer greater than `0`
- `start` and `end` times must be valid 24-hour `HH:MM` values, and `start` must be strictly earlier than `end`
- `days` is a compact meeting-day string such as `MW` or `TR`; two sections share a meeting day if their `days` strings have at least one character in common
- adding a section for an unknown course and scheduling an unknown course or section must fail cleanly
- `section list --format json` returns a JSON array of section objects
- each section object must contain exactly `course`, `section`, `days`, `start`, and `end`
- `section list --format json` must be sorted by `section` ascending
- `schedule list --format json` returns a JSON array of selected section objects
- each schedule object must contain exactly `course`, `section`, `days`, `start`, and `end`
- `schedule list --format json` must be sorted by `course` ascending and then `section` ascending
- repeated write commands from separate processes must persist state in `./course_planner_data.json`
