# Project 2 / Stage 04

You are continuing from the repository produced in stage 03. Preserve all prior behavior and add new capabilities by extending the plugin layer only.

The repository must still expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Change request

Add three new plugins without rewriting the core plugin mechanism:

- `unique_word_count`
- `longest_word`
- `keyword_density`

## Commands that must work at this stage

```bash
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format json
uv run python -m text_analyzer list-plugins --format json
```

## Required behavior

- the new plugins must be implemented as separate plugin modules
- use the analyzer's existing word-tokenization and lowercasing rules
- `unique_word_count` returns the count of distinct lowercase words
- `longest_word` returns a JSON object with `word` and `length`; if multiple words tie for maximum length, return the lexicographically smallest lowercase word; if there are no words, return `{"word": "", "length": 0}`
- `keyword_density` returns a JSON object mapping each distinct lowercase word to `count(word) / total_token_count`, rounded to 4 decimal places; if there are no words, return `{}`
- the new plugins must appear in `list-plugins --format json`
