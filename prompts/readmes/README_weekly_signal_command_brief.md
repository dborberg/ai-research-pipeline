# Weekly Signal Command Brief

## Label

Deterministic weekly `SIGNAL` report generator.

## Source

- File: `run_weekly_pipeline.py`
- Function: `generate_signal_command_brief(cluster_df, week_start)`

## Purpose

Builds the `SIGNAL` weekly output directly from scored weekly clusters and velocity metrics. It does not call the language model and does not define a system/user prompt pair.

## Where It Is Used

- Used only for weekly mode `SIGNAL`
- Generated after weekly clusters and momentum metrics are computed

## Notes For Editing

- Edit this function directly for output structure or wording changes.
- If you want `SIGNAL` to become prompt-driven in the future, add explicit prompt variables and document them here.
- Because this mode is deterministic, changes here are code changes rather than prompt changes.