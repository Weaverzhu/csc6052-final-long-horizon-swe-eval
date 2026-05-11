# Project 2 / Stage 06

You are continuing from the repository produced in stage 05. Preserve all prior behavior while extending the analyzer from one file to directory-wide batch processing.

The repository must still expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Change request

Add directory analysis with per-file outputs and an aggregate summary.

## Commands that must work at this stage

```bash
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] [--format json|text|markdown]
uv run python -m text_analyzer analyze-dir DIR [--analysis NAME ...] --format json
```

## Required behavior

- `analyze-dir ... --format json` returns a JSON object with `files` and `aggregate`
- `files` is a list of objects shaped like `{"path": "relative/path.txt", "results": {...}}`
- each `path` is relative to the analyzed directory and uses forward slashes
- `files` must be sorted by `path` ascending
- `analyze-dir` walks the target directory recursively and analyzes regular files only
- if the target directory contains no regular files, `files` must be `[]` and `aggregate` must be `{}`
- each `results` object must match the single-file `analyze ... --format json` contract for the selected analyses
- `aggregate` must sum the selected analyses whose per-file results are numeric
- when selected analyses mix numeric and non-numeric results, `aggregate` must include only the numeric ones
- analyses whose per-file results are not numeric do not need aggregate entries
- if no selected analyses produce numeric per-file results, `aggregate` must be `{}`
- later-stage batch support must reuse the existing plugin pipeline instead of bypassing it
