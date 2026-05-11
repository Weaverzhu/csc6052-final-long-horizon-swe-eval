# Project 3 / Stage 05

You are continuing from the repository produced in stage 04. Preserve all prior behavior while adding schedule recommendation.

The repository must still expose:

```bash
uv run python -m course_planner <command> [options]
```

## Change request

Suggest a feasible semester plan under credit and conflict constraints.

## Commands that must work at this stage

```bash
uv run python -m course_planner recommend [--completed CODE ...] [--max-credits INT] [--format json] [--data PATH]
```

## Required behavior

- `recommend --format json` returns a JSON object with exactly `schedule`, `total_credits`, and `valid`
- any feasible schedule is acceptable; there is no optimality requirement
- the suggested plan must respect time-conflict rules, prerequisite rules, and the requested credit cap
- courses passed via `--completed` are treated as already satisfied for prerequisite checking and must not appear in the returned `schedule`
- courses not passed via `--completed` may satisfy co-requisites only by appearing together in the returned `schedule`
- `recommend` must return at least one course when a non-empty feasible plan exists under the requested constraints
- `schedule` entries must use the same JSON object shape and ordering as `schedule list --format json`
- `total_credits` must equal the sum of credits for the returned `schedule`
- `total_credits` is not just a cap check; it must exactly match the credits of the returned schedule entries
- `recommend` must not mutate the stored schedule state
- if no feasible schedule exists, return `{"schedule": [], "total_credits": 0, "valid": false}`
