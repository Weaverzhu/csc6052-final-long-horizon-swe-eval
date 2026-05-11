# Project 3 / Stage 02

You are continuing from the repository produced in stage 01. Preserve stage 01 behavior while adding schedule validation and timetable views.

The repository must still expose:

```bash
uv run python -m course_planner <command> [options]
```

## Change request

Detect time conflicts and produce a weekly timetable view for the current schedule.

## Commands that must work at this stage

```bash
uv run python -m course_planner validate --format json
uv run python -m course_planner timetable --format json
```

## Required behavior

- two scheduled sections have a time conflict when their meeting-day strings share at least one day character and their time intervals overlap
- time intervals are half-open: a section ending at `10:00` does not conflict with another section starting at `10:00`
- `validate --format json` returns a JSON object with exactly `valid` and `issues`
- each `time_conflict` issue must be a JSON object with exactly `type`, `course`, `section`, `other_course`, and `other_section`
- `time_conflict` issue objects must use `type = "time_conflict"`
- `issues` must be sorted by `course`, then `section`, then `other_course`, then `other_section`
- `timetable --format json` returns the currently selected section entries as a JSON array
- each timetable entry must contain exactly `course`, `section`, `days`, `start`, and `end`
- timetable entries must be sorted by `days`, then `start`, then `course`, then `section`
