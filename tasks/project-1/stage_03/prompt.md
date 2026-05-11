# Project 1 / Stage 03

You are continuing from the repository produced in stage 02. Preserve all earlier behavior while making storage configurable.

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
- read commands must support `--format json`
- validation failures must exit non-zero and write a short error to stderr
- JSON list output must stay sorted by date ascending, then insertion order for ties
- monetary JSON fields keep the stage 02 serialization contract: JSON numbers or decimal strings are both acceptable when they parse to the same finite decimal values
- when `--data PATH` is omitted, the application still uses `./finance_data.json`

## Change request

Keep all existing behavior, but make storage location configurable and formalize the JSON persistence contract so test fixtures can be generated deterministically.

## Commands that must work at this stage

```bash
uv run python -m finance_tracker add --date DATE --amount AMOUNT --category CATEGORY --description DESCRIPTION [--data PATH]
uv run python -m finance_tracker list [--from DATE] [--to DATE] [--category CATEGORY] [--format json] [--data PATH]
uv run python -m finance_tracker summary [--format json] [--data PATH]
```

## Required behavior

- `--data PATH` is accepted by all read and write commands
- `summary --format json --data PATH` must read from the same custom dataset selected by `add` and `list`
- if `--data PATH` is omitted, commands continue using the default JSON file
- if `--data PATH` points to a missing file, the application initializes an empty dataset there
- two different `--data` paths remain fully isolated
- the JSON file is a valid JSON object with at least a top-level `transactions` array
- each stored transaction record preserves the four public transaction fields
- malformed JSON files are rejected with a non-zero exit and readable stderr for any read command that opens them
