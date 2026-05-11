# Project 1 / Stage 02

You are continuing from the repository produced in stage 01. Preserve all prior behavior while extending the same codebase.

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

## Shared rules that remain in force

- transaction fields are `date`, `amount`, `category`, and `description`
- `date` format is `YYYY-MM-DD`
- `amount` parses as a finite decimal number, with positive for income and negative for expense; `NaN`, `Infinity`, and `-Infinity` are invalid
- zero amount is invalid
- validation failures must exit non-zero and write a short error to stderr
- read commands must support `--format json`
- JSON list output must stay sorted by date ascending, then insertion order for ties
- default persistence remains `./finance_data.json`

## Change request

Extend the tracker so users can filter transaction listings and request per-month summaries without breaking stage 01 behavior.

## Commands that must work at this stage

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION
uv run python -m finance_tracker list [--from DATE] [--to DATE] [--category CATEGORY] [--format json]
uv run python -m finance_tracker summary [--format json]
```

## Required behavior

- `--from` and `--to` apply an inclusive date range filter
- invalid filter dates must fail cleanly with a non-zero exit code and a short stderr message
- when multiple filters are provided, a transaction must satisfy all filters to be included
- category filtering is case-insensitive
- `summary --format json` returns one object per calendar month present in the data
- each summary object contains `month`, `income_total`, `expense_total`, `net_total`, and `transaction_count`
- monetary JSON fields such as `amount`, `income_total`, `expense_total`, and `net_total` may be JSON numbers or decimal strings, but they must parse back to the same finite decimal values
- `expense_total` is reported as a positive magnitude, not a negative signed sum
- summary objects must be sorted by `month` ascending
- all stage 01 behavior must continue to work
