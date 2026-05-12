# Core System Prompt

## Label

Core system prompt for sector investment-impact reports.

## Source

- File: `prompts/core_system_prompt.md`
- Loaded by: `scripts/render_prompt.py`
- Report mode: `investment_implications`

## Purpose

Defines the reusable analysis role, writing standards, audience assumptions, report structure, and analytical quality bar for the default sector-report flow.

## Where It Is Used

- `scripts/render_prompt.py` selects this file for `investment_implications`
- The assembled prompt package is later consumed by `scripts/generate_sector_report.py`
- The end-to-end workflow is `.github/workflows/generate_sector_report.yml`

## Notes For Editing

- Change this when the shared analytical framework should shift across all default sector reports.
- Keep sector-specific detail in `prompts/sectors/*.md`, not here.
- Keep run-time formatting or special instructions in the user prompt template, not here.