# Project 1 / Stage 05

You are continuing from the repository produced in stage 04. Preserve the stage 01 to stage 04 business behavior while changing the normal storage backend from JSON to SQLite.

The repository must still expose:

```bash
uv run python -m finance_tracker <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup and package-based layout
- standard library only
- no network access
- no daemon or background server
- commands should finish within 5 seconds for datasets smaller than 1,000 transactions
- keep extending the existing multi-module package; do not collapse the code into one file

## Change request

Replace the JSON backend with SQLite for normal operation, but preserve the stage 01 to stage 04 business behavior. Add a migration command that imports a legacy JSON dataset.

## Commands that must work at this stage

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION [--data PATH]
uv run python -m finance_tracker list [--from DATE] [--to DATE] [--category CATEGORY] [--format json] [--data PATH]
uv run python -m finance_tracker summary [--format json] [--data PATH]
uv run python -m finance_tracker budget set --month YYYY-MM --category CATEGORY --limit AMOUNT [--data PATH]
uv run python -m finance_tracker budget list --month YYYY-MM [--format json] [--data PATH]
uv run python -m finance_tracker budget check --month YYYY-MM [--format json] [--data PATH]
uv run python -m finance_tracker migrate --from-json OLD_JSON_PATH [--data DB_PATH]
```

## Required behavior

- JSON list output must stay sorted by date ascending, then insertion order for ties
- `migrate --from-json` reads a legacy JSON dataset produced by stage 04 semantics
- migration imports both transactions and budgets
- after migration, `list`, `summary`, `budget list`, and `budget check` over the database behave the same as before
- if `--data PATH` is omitted, the default backend file is `./finance_data.db`
- after the backend switch, omitted `--data` on normal commands such as `add`, `list`, `summary`, and `budget ...` must all use `./finance_data.db`
- rerunning migration against the same target database is not supported; it must fail clearly and leave the imported data unchanged
- migrating from a missing legacy JSON file must fail cleanly with a non-zero exit code
- migrating an empty legacy dataset is valid and produces an empty SQLite-backed tracker state
- the resulting `--data` file must be a valid SQLite database
