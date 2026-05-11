# Project 2 / Stage 01

You are starting from a benchmark-provided starter repository.

Build a CLI text analyzer in Python 3.11. The repository must expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Environment constraints

- Python 3.11
- use `uv` for Python project management and command execution
- preserve the starter `uv` project setup, including `pyproject.toml` and the package entry point
- standard library only
- no network access
- keep the implementation in a package such as `text_analyzer/` or `src/text_analyzer/`
- keep the CLI entry thin and split the implementation across multiple modules
- a single top-level `main.py` solution does not satisfy this benchmark

## Shared output rules

- validation failures must exit with non-zero status and write a short error message to stderr
- `analyze` must support `--format json`
- JSON output must be deterministic and stable across runs

## Change request

Build a CLI tool that analyzes one text file and returns basic statistics.

## Commands that must work

```bash
uv run python -m text_analyzer analyze PATH --format json
```

## Required behavior

- `analyze` reads one UTF-8 text file
- `--format json` returns a JSON object
- the JSON object must contain `word_count`, `character_count`, `line_count`, and `average_word_length`
- words are tokenized with regex `[A-Za-z0-9']+`
- `character_count` is `len(text)` on the decoded Python string, including whitespace and newline characters
- `line_count` counts non-empty lines only; a line counts if `line.strip()` is non-empty
- `average_word_length` is the mean token length rounded to 2 decimal places, or `0.0` when the file has no words
- missing files fail cleanly with a short stderr message
- empty files must not crash
