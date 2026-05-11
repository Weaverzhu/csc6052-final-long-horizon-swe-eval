# Project 4 / Stage 01

You are starting from a benchmark-provided starter repository.

Build a CLI knowledge base manager in Python 3.11. The repository must expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup, including `pyproject.toml` and the package entry point
- standard library only
- no network access
- keep the implementation in a package such as `knowledge_base/` or `src/knowledge_base/`
- keep the CLI entry thin and split the implementation across multiple modules
- a single top-level `main.py` solution does not satisfy this benchmark

## Shared state and output rules

- the application must persist state across separate process invocations using the default file `./knowledge_base_data.json`
- validation failures must exit with non-zero status and write a short error message to stderr
- read commands must support `--format json`
- JSON output must be deterministic and stable across runs

## Change request

Build a CLI knowledge base that lets the user add notes, attach tags, and list stored notes.

## Commands that must work

```bash
uv run python -m knowledge_base note add --id ID --title TITLE --body TEXT
uv run python -m knowledge_base note tag --id ID --tag TAG
uv run python -m knowledge_base note list --format json
```

## Required behavior

- `note list --format json` returns a JSON array of note objects sorted by `id` ascending
- each note object must contain exactly `id`, `title`, `body`, and `tags`
- `tags` must be sorted ascending and deduplicated
- repeated write commands from separate processes must persist state in `./knowledge_base_data.json`
- duplicate note ids and attempts to tag unknown notes must fail cleanly
