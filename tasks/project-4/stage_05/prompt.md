# Project 4 / Stage 05

You are continuing from the repository produced in stage 04. Preserve all prior behavior while adding an explicit search index.

The repository must still expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Change request

Introduce a rebuildable search index so search results are decoupled from direct note-file scans.

## Commands that must work at this stage

```bash
uv run python -m knowledge_base index rebuild
uv run python -m knowledge_base note search --query TEXT --format json
```

## Required behavior

- `index rebuild` must refresh a deterministic index file at `./knowledge_base_index.json`
- `index rebuild` is the only command that refreshes `./knowledge_base_index.json`
- `note search` must read only from the index state rather than rescanning the note store directly
- if the index file does not exist yet, `note search --format json` must return `[]` rather than scanning notes directly
- note write commands such as add, tag, import, or link do not refresh the index automatically
- after `note add` or `snapshot import`, search results must remain stale until `index rebuild` runs again
- if the default data file is edited manually, search results must remain stale until `index rebuild` is run again
- repeated rebuilds without data changes must be idempotent
