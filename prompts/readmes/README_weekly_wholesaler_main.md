# Weekly Wholesaler Main Prompt Pair

## Label

Standalone prompt pair for the main `WHOLESALER` weekly digest body.

## Source

- Files: `prompts/weekly/wholesaler_main_system_prompt.md` and `prompts/weekly/wholesaler_main_user_prompt.md`
- Function: `generate_wholesaler_weekly(client, source_context, week_start, article_data=None)`
- Loaded by: `run_weekly_pipeline.py`

## Purpose

Generates the main wholesaler-ready weekly digest sections, including top stories, non-mega-cap developments, disruption signals, regulatory radar, soundbites, and client questions.

## Where It Is Used

- Used only for weekly mode `WHOLESALER`
- The result becomes the main body of the wholesaler email before the practice-tip section is appended

## Notes For Editing

- This is the primary weekly email-writing prompt for wholesalers.
- Keep section names and counts stable unless downstream expectations are intentionally changing.
- This prompt is separate from the practice-tip prompt so the main digest and the appended tip can evolve independently.