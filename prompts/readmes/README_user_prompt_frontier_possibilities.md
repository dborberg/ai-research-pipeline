# Frontier User Prompt Template

## Label

Frontier user prompt template for sector frontier-possibilities reports.

## Source

- File: `prompts/user_prompt_frontier_possibilities.md`
- Loaded by: `scripts/render_prompt.py`
- Report mode: `frontier_possibilities`

## Purpose

Provides the run-time task framing, output requirements, and interpolated fields for frontier-mode sector reports.

## Where It Is Used

- `scripts/render_prompt.py` renders this template with replacements and packages it as the `User Prompt` section
- The rendered result is used downstream by `scripts/generate_sector_report.py`
- The file pairs with `prompts/frontier_system_prompt.md`

## Notes For Editing

- Change this when the frontier report output, emphasis, or run-time framing should change.
- Keep reusable frontier behavior in the frontier system prompt.
- Keep sector-specific nuance in the sector adapter files.