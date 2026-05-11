# Project 1 / Stage 04

You are continuing from the repository produced in stage 03. Preserve all transaction, filtering, summary, and configurable-storage behavior while adding budgets.

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

Add per-category monthly budgets and alerting while preserving all transaction and summary behavior.

## Commands that must work at this stage

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION [--data PATH]
uv run python -m finance_tracker list [--from DATE] [--to DATE] [--category CATEGORY] [--format json] [--data PATH]
uv run python -m finance_tracker summary [--format json] [--data PATH]
uv run python -m finance_tracker budget set --month YYYY-MM --category CATEGORY --limit AMOUNT [--data PATH]
uv run python -m finance_tracker budget list --month YYYY-MM [--format json] [--data PATH]
uv run python -m finance_tracker budget check --month YYYY-MM [--format json] [--data PATH]
```

## Required behavior

- JSON list output must stay sorted by date ascending, then insertion order for ties
- budgets are scoped by calendar month and category
- only expense transactions count toward budget usage
- expense usage is computed using the absolute value of negative amounts
- `budget list --format json` returns stored budgets for the requested month
- `budget check --format json` returns one object per budget with fields `month`, `category`, `limit`, `spent`, `usage_ratio`, and `status`
- each `budget check` object must follow the shape `{"month": "YYYY-MM", "category": "...", "limit": "100.00", "spent": "50.00", "usage_ratio": "0.5", "status": "ok"}`
- `status` is `ok` below `0.8`
- `status` is `warning` from `0.8` up to but not including `1.0`
- `status` is `exceeded` at `1.0` and above
- all stage 01 to stage 03 behavior must continue to work
