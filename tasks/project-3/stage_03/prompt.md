# Project 3 / Stage 03

You are continuing from the repository produced in stage 02. Preserve prior behavior while formalizing persistence and import/export.

The repository must still expose:

```bash
uv run python -m course_planner <command> [options]
```

## Change request

Make the storage location configurable and add import/export commands.

## Commands that must work at this stage

```bash
uv run python -m course_planner course add --code CODE --title TITLE --credits INT [--data PATH]
uv run python -m course_planner section add --course CODE --section ID --days DAYS --start HH:MM --end HH:MM [--data PATH]
uv run python -m course_planner section list --course CODE --format json [--data PATH]
uv run python -m course_planner schedule add --course CODE --section ID [--data PATH]
uv run python -m course_planner schedule list --format json [--data PATH]
uv run python -m course_planner validate --format json [--data PATH]
uv run python -m course_planner timetable --format json [--data PATH]
uv run python -m course_planner export --output PATH [--data PATH]
uv run python -m course_planner import --input PATH [--data PATH]
```

## Required behavior

- if `--data PATH` is omitted, commands continue using `./course_planner_data.json`
- different data paths must stay isolated
- `export` writes a JSON object with exactly `courses`, `sections`, and `schedule`
- `courses`, `sections`, and `schedule` must each be JSON arrays
- `import` replaces the target planner state with the contents of that snapshot
- importing into a planner that already has courses, sections, or scheduled entries must overwrite that target state rather than merge with it
- after `import`, `schedule list --format json` must return the same schedule entries exported from the source planner
