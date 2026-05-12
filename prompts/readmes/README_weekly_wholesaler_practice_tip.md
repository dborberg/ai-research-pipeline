# Weekly Wholesaler Practice Tip Prompt Pair

## Label

Standalone prompt pair for the `AI PRACTICE TIP OF THE WEEK` section appended to the `WHOLESALER` digest.

## Source

- Files: `prompts/weekly/wholesaler_practice_tip_system_prompt.md` and `prompts/weekly/wholesaler_practice_tip_user_prompt.md`
- Function: `generate_wholesaler_weekly(client, source_context, week_start, article_data=None)`
- Loaded by: `run_weekly_pipeline.py`

## Purpose

Generates a single practical advisor workflow use case with rotation constraints, output structure, guardrails, and a copy-ready prompt.

## Where It Is Used

- Used only for weekly mode `WHOLESALER`
- Appended to the main wholesaler digest after the main body is generated

## Notes For Editing

- This prompt intentionally rotates workflows and concept families week to week.
- Keep the required output labels stable unless the post-processing logic is updated.
- Avoid collapsing this into generic productivity advice, since the current prompt is explicitly tuned against that failure mode.