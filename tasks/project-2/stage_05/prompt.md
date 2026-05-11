# Project 2 / Stage 05

You are continuing from the repository produced in stage 04. Preserve all prior analysis behavior while adding configurable output formatting.

The repository must still expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Change request

Support plain-text, JSON, and Markdown-table outputs.

## Commands that must work at this stage

```bash
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format json
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format text
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format markdown
```

## Required behavior

- `json`, `text`, and `markdown` are all supported output formats
- the underlying analysis results must stay consistent across formats
- `text` output must contain one line per analysis in alphabetical order, using the exact format `analysis_name: VALUE`
- in `text` output, `VALUE` must be the compact canonical JSON serialization of that analysis result, with object keys sorted and no extra whitespace
- `markdown` output must use the exact header `| analysis | value |`
- `markdown` output must use the exact separator row `| --- | --- |`
- `markdown` output must contain one data row per analysis in alphabetical order
- in `markdown` output, the `value` cell must be the compact canonical JSON serialization of that analysis result, with object keys sorted and no extra whitespace
- `text` and `markdown` output must contain no extra prose and end with exactly one trailing newline
