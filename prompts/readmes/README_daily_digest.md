# Daily Digest Prompt Pair

## Label

Standalone prompt pair for the daily AI briefing.

## Source

- Files: `prompts/daily/daily_digest_system_prompt.md` and `prompts/daily/daily_digest_user_prompt.md`
- Function: `generate_daily_digest(report_date=None)`
- Loaded by: `app/generate_digest.py`

## Purpose

Generates the daily AI briefing for internal CPM research, financial advisors, and mutual fund wholesalers, including the top theme of the day, top stories, enterprise adoption and labor, infrastructure/power bottlenecks, capital markets and investment implications, regulation/governance/policy, physical AI and robotics, what to watch, and advisor/wholesaler soundbites.

## Where It Is Used

- Used by the daily pipeline runner through `run_pipeline.py`
- The result is saved as the daily digest and can be emailed by the existing workflow

## Notes For Editing

- Keep the required section names and order stable unless downstream daily digest expectations are intentionally changing.
- The user prompt uses `{{daily_title}}`, `{{today}}`, `{{theme_signal_block}}`, and `{{article_block}}` placeholders.
- The loader performs simple string replacement, matching the weekly prompt style.
- Keep the output requirement as clean HTML unless the daily ingestion, email, and display process are intentionally updated together.
- The current output contract requires exactly 9 sections after title/date, starting with `TOP THEME OF THE DAY`.
- Company-specific and ticker-level interpretation is allowed for internal use, but should remain framed as analytical read-through, watchlist context, risk to monitor, or business-model implication.
- Saved daily output can be checked with `scripts/validate_daily_digest_output.py`.
