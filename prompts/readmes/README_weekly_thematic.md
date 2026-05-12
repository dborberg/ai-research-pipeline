# Weekly Thematic Prompt Pair

## Label

Standalone prompt pair for the `THEMATIC` weekly digest.

## Source

- Files: `prompts/weekly/thematic_system_prompt.md` and `prompts/weekly/thematic_user_prompt.md`
- Function: `generate_thematic_weekly(client, source_context)`
- Loaded by: `run_weekly_pipeline.py`

## Purpose

Synthesizes the prior week of daily briefings into a concise thematic email focused on mechanisms of change, second-order effects, infrastructure signals, productivity signals, and emerging business models.

## Where It Is Used

- Used only for weekly mode `THEMATIC`
- Output is saved and emailed as the thematic weekly digest

## Notes For Editing

- Keep the output plain text and section-driven.
- This prompt is intended to synthesize patterns, not summarize article-by-article headlines.
- Maintain alignment with the wholesaler digest where shared analytical priorities matter, but do not force the same section structure.