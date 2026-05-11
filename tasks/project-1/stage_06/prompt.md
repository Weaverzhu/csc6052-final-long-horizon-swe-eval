# Project 1 / Stage 06

You are continuing from the repository produced in stage 05. Preserve all earlier CLI behavior while extending the SQLite-backed version with export and reporting features.

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

Add export and reporting features on top of the SQLite-backed version without disturbing any earlier commands.

## Commands that must work at this stage

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION [--data PATH]
uv run python -m finance_tracker list [--from DATE] [--to DATE] [--category CATEGORY] [--format json] [--data PATH]
uv run python -m finance_tracker summary [--format json] [--data PATH]
uv run python -m finance_tracker budget set --month YYYY-MM --category CATEGORY --limit AMOUNT [--data PATH]
uv run python -m finance_tracker budget list --month YYYY-MM [--format json] [--data PATH]
uv run python -m finance_tracker budget check --month YYYY-MM [--format json] [--data PATH]
uv run python -m finance_tracker migrate --from-json OLD_JSON_PATH [--data DB_PATH]
uv run python -m finance_tracker export --output PATH [--from DATE] [--to DATE] [--category CATEGORY] [--data PATH]
uv run python -m finance_tracker report --month YYYY-MM [--format json] [--data PATH]
```

## Required behavior

- JSON list output must stay sorted by date ascending, then insertion order for ties
- `export` writes a CSV file containing the filtered transaction set
- the CSV header is exactly `date,amount,category,description`
- CSV output must use normal CSV escaping for commas, quotes, and newlines in field values
- exported transaction rows must use the same order as `list --format json` for the same filters
- if `export` matches no transactions, it must still create the CSV file with only the header row
- `report --month YYYY-MM --format json` returns one object per category seen in that month
- each report object contains `category`, `income_total`, `expense_total`, `net_total`, and `transaction_count`
- category report totals are computed only from transactions in the requested month
- `expense_total` is reported as a positive magnitude, and `net_total = income_total - expense_total`
- report objects must be sorted by `category` ascending
- omitted `--data` on normal commands must still use the SQLite default backend file `./finance_data.db`
- all stage 01 to stage 05 behavior must continue to work
