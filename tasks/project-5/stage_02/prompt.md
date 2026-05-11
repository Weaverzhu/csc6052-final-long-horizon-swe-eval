# Project 5 / Stage 02

You are continuing from the repository produced in stage 01. Preserve all prior behavior while adding target-specific overrides.

The repository must still expose:

```bash
uv run python -m config_manager <command> [options]
```

## Change request

Allow each profile to define overrides for named targets such as `dev` or `prod`.

## Commands that must work at this stage

```bash
uv run python -m config_manager override set --profile NAME --target TARGET --section SECTION --key KEY --value VALUE
uv run python -m config_manager profile resolve --name NAME --target TARGET --format json
```

## Required behavior

- `profile resolve --format json` returns a JSON object with exactly `name`, `target`, `schema_version`, and `sections`
- merge precedence is fixed: base sections first, then target overrides
- if both base settings and target overrides provide the same section key, the target override must replace the base value in the resolved config
- resolved nested mappings must be deterministic and stable across runs, with section names and keys sorted ascending
