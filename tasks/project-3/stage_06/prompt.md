# Project 3 / Stage 06

You are continuing from the repository produced in stage 05. Preserve all prior behavior while adding what-if revision commands.

The repository must still expose:

```bash
uv run python -m course_planner <command> [options]
```

## Change request

Let the user ask whether a drop or swap would keep the schedule valid, returning the hypothetical schedule state as structured data.

## Commands that must work at this stage

```bash
uv run python -m course_planner whatif drop --course CODE [--format json] [--data PATH]
uv run python -m course_planner whatif swap --course CODE --section ID [--format json] [--data PATH]
```

## Required behavior

- `whatif drop --course CODE` removes the currently selected section for that course from the hypothetical schedule only
- `whatif swap --course CODE --section ID` replaces the currently selected section for that course with the named section in the hypothetical schedule only
- what-if commands must not silently mutate stored schedule state
- JSON output must contain exactly `valid`, `issues`, and `schedule`
- `schedule` must use the same JSON object shape and ordering as `schedule list --format json`
- `schedule` must describe the hypothetical schedule after applying the requested drop or swap
- `issues` must use the same structured issue objects returned by `validate --format json`
- if the course is not currently scheduled, or `whatif swap` names a section that does not exist for that course, the command must fail cleanly with a non-zero exit code
- those invalid what-if commands must still write a short stderr message instead of succeeding with an unchanged schedule payload
