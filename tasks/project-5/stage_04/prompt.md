# Project 5 / Stage 04

You are continuing from the repository produced in stage 03. Preserve all prior behavior while adding target-specific policy checks.

The repository must still expose:

```bash
uv run python -m config_manager <command> [options]
```

## Change request

Add stricter policy rules for production configs and one cross-field timeout bound check.

## Required behavior

- `profile validate --name NAME --target prod --format json` must additionally enforce:
  - `service.debug` must be `false`
  - `service.replicas` must be an integer greater than or equal to `2`
  - if `service.max_timeout` exists, compare the resolved `service.timeout` value after applying target overrides against the resolved `service.max_timeout`, and the timeout must be less than or equal to that max
- if a prod override changes `service.timeout`, the cross-field timeout check must use that overridden value
- policy issue codes are:
  - `prod_debug_forbidden`
  - `prod_replicas_too_low`
  - `timeout_exceeds_max`
- policy issues use the same issue object shape and sorting rules from stage 03
- `prod_debug_forbidden` is reported at path `service.debug` with the resolved invalid debug value
- `prod_replicas_too_low` is reported at path `service.replicas` with the resolved invalid replicas value; a missing or non-integer replicas value is invalid for this policy
- `timeout_exceeds_max` is reported at path `service.timeout` with the resolved timeout value
