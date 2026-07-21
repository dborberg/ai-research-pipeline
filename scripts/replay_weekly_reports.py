#!/usr/bin/env python3

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from app.db import init_db
from app.reporting import get_openai_client, save_text_output
from app.runtime_secrets import get_openai_api_key
from app.source_archive import load_daily_digest_file, load_daily_source_snapshot
from app.pipeline_window import PIPELINE_WINDOW_END_ENV, PIPELINE_WINDOW_START_ENV
from run_weekly_pipeline import (
    DEBUG_WEEKLY_SCORING,
    DEFAULT_SCORE_THRESHOLD,
    THEMATIC_TITLE,
    WHOLESALER_TITLE,
    _build_weekly_cluster_bundle,
    _build_wholesaler_event_context,
    _format_cluster_context,
    _with_weekly_report_header,
    generate_thematic_weekly,
    generate_wholesaler_weekly,
)
from app.generate_digest import generate_daily_digest


_CENTRAL_TZ = ZoneInfo("America/Chicago")


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value).strip())


def _week_dates(week_ending: date) -> list[date]:
    return [week_ending - timedelta(days=offset) for offset in range(6, -1, -1)]


def _build_utc_window_for_central_date(target_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=_CENTRAL_TZ)
    end_local = start_local + timedelta(days=1) - timedelta(seconds=1)
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None, microsecond=0)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None, microsecond=0)
    return start_utc, end_utc


def _format_replay_daily_digest_context(daily_digests: list[tuple[date, str]]) -> str:
    if not daily_digests:
        return ""

    digest_blocks = []
    for digest_date, content in daily_digests:
        digest_blocks.append(
            "\n".join(
                [
                    f"DATE: {digest_date.isoformat()}",
                    "DIGEST:",
                    str(content).strip(),
                ]
            )
        )

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(digest_blocks)


def _build_replay_weekly_source_context(clustered_context: str, daily_digest_context: str) -> str:
    if clustered_context and daily_digest_context:
        return (
            "PRIMARY INPUT: TIER 1 DAILY-DERIVED CANDIDATES\n"
            "These Daily Riffs are the inheritance base and should normally supply 80-90% of the Weekly Riffs content.\n"
            f"{daily_digest_context}\n\n"
            "SUPPLEMENTAL INPUT: CLUSTERED THEMES FROM THE WEEKLY ARTICLE SET\n"
            f"{clustered_context}"
        )
    if clustered_context:
        return f"SUPPLEMENTAL INPUT: CLUSTERED THEMES FROM THE WEEKLY ARTICLE SET\n{clustered_context}"
    if daily_digest_context:
        return (
            "PRIMARY INPUT: TIER 1 DAILY-DERIVED CANDIDATES\n"
            "These Daily Riffs are the inheritance base and should normally supply 80-90% of the Weekly Riffs content.\n"
            f"{daily_digest_context}"
        )
    return ""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Replay Daily Riffs, Weekly Riffs, and Weekly Motifs for a chosen Friday week-ending date without sending email."
    )
    parser.add_argument(
        "--week-ending",
        required=True,
        help="Friday week-ending date to replay, in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--debug-weekly-scoring",
        action="store_true",
        help="Include the internal weekly scoring table in the replayed Weekly Riffs output.",
    )
    return parser.parse_args(argv)


def replay_weekly_reports(week_ending: date, *, debug_weekly_scoring: bool = False):
    api_key = get_openai_api_key(default="")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")

    init_db()
    client = get_openai_client(api_key)
    replay_root = REPO_ROOT / "outputs" / "replay" / week_ending.isoformat()
    daily_output_dir = replay_root / "daily"
    weekly_output_dir = replay_root / "weekly"

    original_window_start = os.getenv(PIPELINE_WINDOW_START_ENV)
    original_window_end = os.getenv(PIPELINE_WINDOW_END_ENV)

    daily_digests = []
    try:
        for target_date in _week_dates(week_ending):
            window_start, window_end = _build_utc_window_for_central_date(target_date)
            os.environ[PIPELINE_WINDOW_START_ENV] = window_start.isoformat()
            os.environ[PIPELINE_WINDOW_END_ENV] = window_end.isoformat()

            print(f"=== REPLAY DAILY {target_date.isoformat()} ===")
            print(f"Window UTC: {window_start.isoformat()} -> {window_end.isoformat()}")
            archived_digest = load_daily_digest_file(target_date)
            archived_articles = load_daily_source_snapshot(target_date)
            if archived_digest and archived_articles:
                print("Using archived daily digest and article snapshot")
                digest_text = archived_digest
            else:
                digest_text = generate_daily_digest(report_date=target_date)
            daily_digests.append((target_date, digest_text))
            save_text_output(str(daily_output_dir), f"{target_date.isoformat()}.txt", digest_text)

        weekly_bundle = _build_weekly_cluster_bundle(
            client,
            week_ending,
            score_threshold=DEFAULT_SCORE_THRESHOLD,
        )
        digest_context = _format_replay_daily_digest_context(daily_digests)
        clustered_context = _format_cluster_context(weekly_bundle["clusters"], weekly_bundle["patterns"])
        source_context = _build_replay_weekly_source_context(clustered_context, digest_context)
        curated_event_context = _build_wholesaler_event_context(weekly_bundle["article_data"])

        import run_weekly_pipeline as weekly_module

        original_debug = DEBUG_WEEKLY_SCORING
        weekly_module.DEBUG_WEEKLY_SCORING = bool(debug_weekly_scoring)
        try:
            wholesaler_content = generate_wholesaler_weekly(
                client,
                source_context,
                week_ending,
                article_data=weekly_bundle["article_data"],
            )
            thematic_content = generate_thematic_weekly(
                client,
                source_context,
                article_data=weekly_bundle["article_data"],
                space_economy_theme_active=weekly_bundle.get("SPACE_ECONOMY_THEME_ACTIVE", False),
            )
        finally:
            weekly_module.DEBUG_WEEKLY_SCORING = original_debug

        wholesaler_content = _with_weekly_report_header(WHOLESALER_TITLE, week_ending, wholesaler_content)
        thematic_content = _with_weekly_report_header(THEMATIC_TITLE, week_ending, thematic_content)

        save_text_output(str(weekly_output_dir), f"{week_ending.isoformat()}_wholesaler.txt", wholesaler_content)
        save_text_output(str(weekly_output_dir), f"{week_ending.isoformat()}_thematic.txt", thematic_content)
        save_text_output(str(weekly_output_dir), "source_context.txt", source_context)
        save_text_output(str(weekly_output_dir), "curated_event_context.txt", curated_event_context)

        print(f"Saved replay artifacts under {replay_root}")
        return {
            "replay_root": replay_root,
            "daily_output_dir": daily_output_dir,
            "weekly_output_dir": weekly_output_dir,
            "wholesaler_path": weekly_output_dir / f"{week_ending.isoformat()}_wholesaler.txt",
            "thematic_path": weekly_output_dir / f"{week_ending.isoformat()}_thematic.txt",
            "source_context_path": weekly_output_dir / "source_context.txt",
            "curated_event_context_path": weekly_output_dir / "curated_event_context.txt",
        }

    finally:
        if original_window_start is None:
            os.environ.pop(PIPELINE_WINDOW_START_ENV, None)
        else:
            os.environ[PIPELINE_WINDOW_START_ENV] = original_window_start

        if original_window_end is None:
            os.environ.pop(PIPELINE_WINDOW_END_ENV, None)
        else:
            os.environ[PIPELINE_WINDOW_END_ENV] = original_window_end


def main(argv=None):
    args = parse_args(argv)
    week_ending = _parse_date(args.week_ending)
    replay_weekly_reports(
        week_ending,
        debug_weekly_scoring=bool(args.debug_weekly_scoring),
    )


if __name__ == "__main__":
    main()