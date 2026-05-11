# Project 5 / Stage 03

You are continuing from the repository produced in stage 02. Preserve all prior behavior while adding validation.

The repository must still expose:

```bash
uv run python -m config_manager <command> [options]
```

## Change request

Validate resolved configs against built-in required fields and typed value checks.

## Commands that must work at this stage

```bash
uv run python -m config_manager profile validate --name NAME --target TARGET --format json
```

## Required behavior

- `profile validate --format json` returns exactly `{"valid": BOOL, "issues": [...]}` JSON
- issue objects contain exactly `path`, `code`, and `value`
- issues must be sorted by `path` ascending and then `code` ascending
- `missing_required` issues must use `null` as `value`
- version-1 profiles require `database.port`, `service.debug`, and `service.timeout`
- validation must run on the fully resolved config after applying target overrides, not only on the base profile
- validation codes are:
  - `invalid_integer_range` for `database.port` outside `1..65535` or non-integer values
  - `invalid_boolean` for `service.debug` values other than `true` or `false`
  - `invalid_positive_integer` for `service.timeout` values that are not integers greater than `0`
  - `missing_required` for missing required fields
