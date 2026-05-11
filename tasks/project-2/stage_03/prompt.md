# Project 2 / Stage 03

You are continuing from the repository produced in stage 02. Preserve stage 01 to stage 02 behavior while introducing a real plugin system.

The repository must still expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Change request

Design a plugin architecture so new analysis types can be added without modifying the core code.

## Commands that must work at this stage

```bash
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format json
uv run python -m text_analyzer list-plugins --format json
```

## Required plugin contract

- plugin modules live under a plugins directory inside the package
- each plugin module must define:
  - `PLUGIN_NAME = "some_name"`
  - `def analyze(text: str, results: dict | None = None) -> object`
- the built-in stage 01 and stage 02 analyses are first-class plugins too
- plugin discovery must scan the plugins directory dynamically
- dropping a new plugin file into the plugins directory must make it available without editing existing core files
- `list-plugins --format json` returns a sorted JSON array of all available plugin names, including built-ins and discovered drop-in plugins
- selected-analysis execution remains strict after the plugin refactor: when `--analysis NAME` is provided, only requested plugin `analyze` functions may be called
- an unrequested plugin may have side effects, and those side effects must not occur during a run that did not request that plugin
