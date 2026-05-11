# Project 3 / Stage 04

You are continuing from the repository produced in stage 03. Preserve all prior behavior while adding prerequisite, co-requisite, and credit rules.

The repository must still expose:

```bash
uv run python -m course_planner <command> [options]
```

## Change request

Support course dependency rules and semester credit bounds.

## Commands that must work at this stage

```bash
uv run python -m course_planner rule set --course CODE [--prereq CODE ...] [--coreq CODE ...] [--data PATH]
uv run python -m course_planner credits set --min INT --max INT [--data PATH]
uv run python -m course_planner validate --format json [--data PATH]
```

## Required behavior

- a prerequisite for a course is satisfied only if the required course is not in the current schedule; current-schedule co-enrollment does not satisfy prerequisites
- a co-requisite for a course is satisfied if the required course is also present in the current schedule
- if several required courses are missing for the same scheduled section and rule type, report one issue containing all missing course codes in `required_courses`
- prerequisite violations must be reported as issue objects with exactly `type`, `course`, `section`, and `required_courses`
- co-requisite violations must be reported as issue objects with exactly `type`, `course`, `section`, and `required_courses`
- credit bound violations must be reported as issue objects with exactly `type`, `actual_credits`, `min_credits`, and `max_credits`
- `required_courses` must be a sorted JSON array of course codes
- issue `type` values must be `prerequisite`, `corequisite`, and `credit_limit`
- `validate --format json` returns `{"valid": true, "issues": []}` when the schedule is valid
- `validate --format json` must not emit placeholder issue objects when the schedule is valid
- dependency-rule issues must be sorted by `type`, then `course`, then `section`, then `required_courses`; `credit_limit` issues come after dependency-rule issues
