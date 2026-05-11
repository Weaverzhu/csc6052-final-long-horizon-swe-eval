# Project 2 / Stage 02

You are continuing from the repository produced in stage 01. Preserve stage 01 behavior while adding more analyses and selective execution.

The repository must still expose:

```bash
uv run python -m text_analyzer <command> [options]
```

## Change request

Add sentence count, paragraph count, and top frequent words. The CLI must let the user select a subset of analyses.

## Commands that must work at this stage

```bash
uv run python -m text_analyzer analyze PATH [--analysis NAME ...] --format json
```

## Required behavior

- when no `--analysis` flags are provided, `analyze` returns all currently available analyses, including the stage 01 metrics `word_count`, `character_count`, `line_count`, and `average_word_length`
- when one or more `--analysis` flags are provided, the JSON output must include only the requested analyses
- selected-analysis execution is strict: unrequested analyses must not be executed just to filter them out later
- stage 02 adds `sentence_count`, `paragraph_count`, and `top_words`
- `sentence_count` is the number of matches for regex `[.!?]+`
- `paragraph_count` is the number of blocks produced by splitting on `"\n\n"` whose `block.strip()` is non-empty; whitespace-only blocks do not count
- words for `top_words` must use the same tokenization as stage 01 word counting: regex `[A-Za-z0-9']+`, normalized to lowercase
- `top_words` must be a JSON list of at most 10 objects shaped like `{"word": "...", "count": N}`
- `top_words` must be ordered by descending count and then alphabetically for ties
- unknown analysis names fail cleanly with a short stderr message
