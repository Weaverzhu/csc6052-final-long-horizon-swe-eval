# Project 1 / Stage 01

You are starting from a benchmark-provided starter repository.

Build a CLI personal finance tracker in Python 3.11. You may choose any internal architecture, but the repository must expose:

```bash
uv run python -m finance_tracker <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup, including `pyproject.toml` and the package entry point
- standard library only
- no network access
- no daemon or background server
- commands should finish within 5 seconds for datasets smaller than 1,000 transactions
- the implementation must live in a package such as `finance_tracker/` or `src/finance_tracker/`
- keep the CLI entry thin and split the implementation across multiple modules
- a single top-level `main.py` solution does not satisfy this benchmark

## Shared data and output rules

- each transaction has `date`, `amount`, `category`, and `description`
- `date` format is `YYYY-MM-DD`
- `amount` must parse as a finite decimal number; `NaN`, `Infinity`, and `-Infinity` are invalid
- positive `amount` means income
- negative `amount` means expense
- zero amount is invalid
- `category` must be non-empty after trimming whitespace
- `description` may contain spaces and punctuation, and leading or trailing whitespace should be trimmed
- validation failures must exit with non-zero status and write a short error message to stderr
- read commands must support `--format json`
- JSON list output must be sorted by date ascending, then insertion order for ties
- data must persist across separate process invocations using the default file `./finance_data.json`

## Change request

Build a CLI finance tracker that can add transactions and list stored transactions. The starter repo already provides the `uv` scaffolding, so focus on the application logic instead of recreating packaging boilerplate.

## Commands that must work

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION
uv run python -m finance_tracker list [--format json]
```

## Required behavior

- `add` stores one transaction in the default data file
- `list --format json` returns a JSON array of transaction objects
- each transaction object includes exactly `date`, `amount`, `category`, and `description`
- `amount` in JSON output may be either a JSON number or a decimal string, but it must parse back to the same finite decimal value
- repeated `add` calls from separate processes accumulate state
- listing with no transactions returns `[]`
