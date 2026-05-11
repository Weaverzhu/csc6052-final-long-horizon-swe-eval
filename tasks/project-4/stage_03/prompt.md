# Project 4 / Stage 03

You are continuing from the repository produced in stage 02. Preserve all prior behavior while adding snapshot import and export.

The repository must still expose:

```bash
uv run python -m knowledge_base <command> [options]
```

## Change request

Support portable snapshots of the knowledge base state.

## Commands that must work at this stage

```bash
uv run python -m knowledge_base snapshot export PATH
uv run python -m knowledge_base snapshot import PATH
```

## Required behavior

- `snapshot export PATH` writes a JSON object with exactly two top-level keys: `notes` and `links`
- each link object is shaped exactly like `{"source": "ID", "target": "ID"}`
- exported `notes` must be sorted by `id` ascending, and exported `links` must be sorted by `source` ascending then `target` ascending
- the default data file `./knowledge_base_data.json` must use the same top-level object shape as exported snapshots
- `snapshot import PATH` replaces the full current state with the snapshot contents
- importing and re-exporting a snapshot with non-empty `links` must preserve those links and their sorted export order
- importing a snapshot must preserve the same `note list --format json` behavior and note ordering as before
