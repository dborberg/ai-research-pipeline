# Weekly Pattern Extraction Prompt Pair

## Label

Standalone weekly prompt pair for extracting cross-cluster patterns.

## Source

- Files: `prompts/weekly/pattern_extraction_system_prompt.md` and `prompts/weekly/pattern_extraction_user_prompt.md`
- Function: `extract_patterns(client, clusters)`
- Loaded by: `run_weekly_pipeline.py`

## Purpose

Converts theme clusters into ranked lists of emerging trends, converging signals, and second-order effects for investor-oriented synthesis.

## Where It Is Used

- Called inside the weekly clustering bundle before final report generation
- Supports the source context used by weekly downstream outputs

## Notes For Editing

- This prompt expects valid JSON output with three top-level arrays.
- Changes here can alter the framing available to multiple weekly reports, not just one mode.
- Keep output ranking language aligned with the parsing and rendering expectations.