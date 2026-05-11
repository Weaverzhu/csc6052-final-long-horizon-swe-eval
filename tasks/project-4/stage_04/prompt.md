# Project 4 / Stage 04

You are continuing from the repository produced in stage 03. Preserve all prior behavior while adding references and backlinks.

The repository must still expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Change request

Allow notes to reference other notes and show those relationships in both directions.

## Commands that must work at this stage

```bash
uv run python -m knowledge_base link add --source ID --target ID
uv run python -m knowledge_base note show --id ID --format json
```

## Required behavior

- `note show --format json` returns a JSON object with exactly `id`, `title`, `body`, `tags`, `references`, and `backlinks`
- `references` and `backlinks` must be sorted note-id arrays
- sorting requirements apply to multi-link cases too, not only single-link notes
- adding a self-link, linking from an unknown source note, or linking to an unknown target note must fail cleanly
- duplicate links must not produce duplicate entries in `references`, `backlinks`, snapshot exports, or graph reports
