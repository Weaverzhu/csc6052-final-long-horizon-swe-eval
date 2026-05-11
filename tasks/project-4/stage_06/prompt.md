# Project 4 / Stage 06

You are continuing from the repository produced in stage 05. Preserve all prior behavior while adding structured reports.

The repository must still expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Change request

Add deterministic JSON reports over tags and note-link relationships.

## Commands that must work at this stage

```bash
uv run python -m knowledge_base report tags --format json
uv run python -m knowledge_base report graph --format json
```

## Required behavior

- `report tags --format json` returns a JSON array of objects with exactly `tag` and `count`, sorted by `tag` ascending
- `report graph --format json` returns a JSON array of objects with exactly `source` and `target`, sorted by `source` ascending and then `target` ascending
