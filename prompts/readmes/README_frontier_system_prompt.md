# Frontier System Prompt

## Label

Frontier system prompt for sector frontier-possibilities reports.

## Source

- File: `prompts/frontier_system_prompt.md`
- Loaded by: `scripts/render_prompt.py`
- Report mode: `frontier_possibilities`

## Purpose

Defines the reusable instruction layer for the more exploratory frontier-possibilities mode.

## Where It Is Used

- `scripts/render_prompt.py` selects this file for `frontier_possibilities`
- The assembled prompt package is later consumed by `scripts/generate_sector_report.py`
- The file pairs with `prompts/user_prompt_frontier_possibilities.md`

## Notes For Editing

- Change this when the global stance or analytical standard for frontier-mode reports needs to move.
- Keep sector-specific context in `prompts/sectors/*.md`.
- Keep run-specific interpolation fields in the user prompt template.