# Project 5 / Stage 06

You are continuing from the repository produced in stage 05. Preserve all prior behavior while adding provenance-aware resolution.

The repository must still expose:

```bash
uv run python -m config_manager <command> [options]
```

## Change request

Explain where each resolved setting came from.

## Commands that must work at this stage

```bash
uv run python -m config_manager profile resolve --name NAME --target TARGET --explain --format json
```

## Required behavior

- `profile resolve --explain --format json` returns exactly `{"config": ..., "sources": ..., "schema_version": INT, "target": TARGET, "name": NAME}`
- `config` must use the same nested section structure as `profile resolve --format json`
- `sources` maps flattened keys such as `service.debug` to either `base` or `target:<TARGET>`
- if a target override replaces a base value, the source for that resolved key must be `target:<TARGET>`
- keys added by migration defaults, such as `service.retries`, have source `base` unless a target override replaces them
- `sources` must contain exactly the resolved keys and no extras
- plain `profile resolve --format json` without `--explain` must continue to preserve the stage 05 output contract unchanged
