# Project 5 / Stage 01

You are starting from a benchmark-provided starter repository.

Build a CLI configuration policy manager in Python 3.11. The repository must expose:

```bash
uv run python -m config_manager <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup, including `pyproject.toml` and the package entry point
- standard library only
- no network access
- keep the implementation in a package such as `config_manager/` or `src/config_manager/`
- keep the CLI entry thin and split the implementation across multiple modules
- a single top-level `main.py` solution does not satisfy this benchmark

## Shared state and output rules

- the application must persist state across separate process invocations using the default file `./config_manager_data.json`
- validation failures must exit with non-zero status and write a short error message to stderr
- read commands must support `--format json`
- JSON output must be deterministic and stable across runs

## Change request

Build a CLI tool that stores named configuration profiles with nested section/key settings.

## Commands that must work

```bash
uv run python -m config_manager setting set --profile NAME --section SECTION --key KEY --value VALUE
uv run python -m config_manager profile show --name NAME --format json
uv run python -m config_manager profile list --format json
```

## Required behavior

- `profile show --format json` returns a JSON object with exactly `name`, `schema_version`, and `sections`
- new profiles must start with `schema_version` equal to `1`
- `sections` must be a nested JSON object keyed by section name and then key name
- section names, key names, targets, and values are stored as strings exactly as provided
- nested `sections` mappings must be emitted deterministically, with section names and keys sorted ascending
- `profile list --format json` returns a JSON array of profile names sorted ascending
- repeated write commands from separate processes must persist state in `./config_manager_data.json`
