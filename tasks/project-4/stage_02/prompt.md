# Project 4 / Stage 02

You are continuing from the repository produced in stage 01. Preserve all prior behavior while adding search and tag filtering.

The repository must still expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Change request

Allow users to search note content and filter notes by tag.

## Commands that must work at this stage

```bash
uv run python -m knowledge_base note search --query TEXT --format json
uv run python -m knowledge_base note list --tag TAG --format json
```

## Required behavior

- `note search --format json` returns the same note object shape as `note list --format json`
- search must match case-insensitive substrings in either `title` or `body`
- a query that appears only in `title` must still match, and a query that appears only in `body` must still match
- `note list --tag TAG --format json` returns only notes containing that exact tag
- search and filtered list results must both be sorted by `id` ascending
