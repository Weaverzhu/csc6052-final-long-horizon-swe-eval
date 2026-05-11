# Project 5 / Stage 05

You are continuing from the repository produced in stage 04. Preserve all prior behavior while adding schema migration.

The repository must still expose:

```bash
uv run python -m config_manager <command> [options]
```

## Change request

Support migration from schema version 1 to schema version 2.

## Commands that must work at this stage

```bash
uv run python -m config_manager profile migrate --name NAME --to-version 2
```

## Required behavior

- migrating from version 1 to version 2 must:
  - move `service.timeout` to `service.request_timeout`
  - add `service.retries = "3"` if it is missing
  - update both base sections and all target overrides
  - set `schema_version` to `2`
- after migration, no migrated base section or target override may still contain `service.timeout`
- if `service.retries` already exists, preserve its existing value instead of overwriting it
- rerunning the same migration on an already-migrated profile is not supported; it must fail clearly and leave the profile unchanged
- after migration, `profile resolve` and `profile validate` must use `service.request_timeout` for version-2 profiles while preserving version-1 behavior for unmigrated profiles
- migrated validation must therefore report issues against `service.request_timeout`, including values coming from migrated target overrides
