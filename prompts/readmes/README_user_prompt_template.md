# User Prompt Template

## Label

Default user prompt template for sector investment-impact reports.

## Source

- File: `prompts/user_prompt_template.md`
- Loaded by: `scripts/render_prompt.py`
- Report mode: `investment_implications`

## Purpose

Holds the run-time instruction layer for the default sector-report mode, including interpolated fields such as sector, audience, time horizon, style notes, and special instructions.

## Where It Is Used

- `scripts/render_prompt.py` renders this template with replacements and packages it as the `User Prompt` section
- The rendered result is used downstream by `scripts/generate_sector_report.py`

## Notes For Editing

- Change this when the requested output format or run-time framing should change for default reports.
- Keep durable model behavior in the system prompt.
- Keep sector economics in the sector adapter files.