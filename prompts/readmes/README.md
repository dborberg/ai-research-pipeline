# Prompt Reference Readmes

This folder documents the prompt assets used across the repository.

## Modular Sector-Report Prompts

- `README_core_system_prompt.md`: documents `prompts/core_system_prompt.md`
- `README_frontier_system_prompt.md`: documents `prompts/frontier_system_prompt.md`
- `README_user_prompt_template.md`: documents `prompts/user_prompt_template.md`
- `README_user_prompt_frontier_possibilities.md`: documents `prompts/user_prompt_frontier_possibilities.md`

These files are assembled by `scripts/render_prompt.py` into a prompt package for the manual sector-report workflow.

## Weekly Pipeline Prompt Pairs

- `README_weekly_cluster_articles.md`: standalone system and user prompt files for weekly article clustering
- `README_weekly_pattern_extraction.md`: standalone system and user prompt files for extracting cross-cluster patterns
- `README_weekly_wholesaler_main.md`: standalone system and user prompt files for the main `WHOLESALER` digest body
- `README_weekly_wholesaler_practice_tip.md`: standalone system and user prompt files for the `AI PRACTICE TIP OF THE WEEK` section appended to the `WHOLESALER` digest
- `README_weekly_thematic.md`: standalone system and user prompt files for the `THEMATIC` digest
- `README_weekly_signal_command_brief.md`: notes for the `SIGNAL` mode, which is deterministic and does not use an LLM prompt pair

The weekly prompt files now live in `prompts/weekly/` and are loaded by `run_weekly_pipeline.py`.

## Daily Pipeline Prompt Pair

- `README_daily_digest.md`: standalone system and user prompt files for the daily AI briefing

The daily prompt files live in `prompts/daily/` and are loaded by `app/generate_digest.py`.

## Weekly Mode Mapping

- `WHOLESALER`: uses `README_weekly_wholesaler_main.md` and `README_weekly_wholesaler_practice_tip.md`
- `THEMATIC`: uses `README_weekly_thematic.md`
- `SIGNAL`: uses `README_weekly_signal_command_brief.md`

## Ownership Notes

- Weekly workflow entrypoint: `.github/workflows/weekly_digests.yml`
- Weekly runner: `run_weekly_investment_pipeline.py` -> `run_weekly_pipeline.py`
- Daily workflow entrypoint: `.github/workflows/daily_pipeline.yml`
- Daily runner: `run_pipeline.py` -> `app/generate_digest.py`
- Sector-report prompt assembler: `scripts/render_prompt.py`
