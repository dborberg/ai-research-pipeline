# Weekly Cluster Articles Prompt Pair

## Label

Standalone weekly prompt pair for clustering scored articles into distinct themes.

## Source

- Files: `prompts/weekly/cluster_articles_system_prompt.md` and `prompts/weekly/cluster_articles_user_prompt.md`
- Function: `cluster_articles(client, articles)`
- Loaded by: `run_weekly_pipeline.py`

## Purpose

Transforms the weekly high-signal and medium-signal article set into 5 to 10 non-overlapping theme clusters with representative summaries, company anchors, and investment relevance.

## Where It Is Used

- Called during `_build_weekly_cluster_bundle(...)`
- Feeds the weekly `WHOLESALER`, `THEMATIC`, and `SIGNAL` outputs downstream

## Notes For Editing

- This is an upstream analytical prompt, not an email-formatting prompt.
- Changes here affect all weekly modes because cluster output is reused across the weekly pipeline.
- Keep JSON structure stable unless the parsing code is updated in tandem.