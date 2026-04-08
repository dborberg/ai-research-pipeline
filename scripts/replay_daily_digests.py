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

from app.db import init_db, upsert_daily_digest
from app.generate_digest import generate_daily_digest
from app.pipeline_window import PIPELINE_WINDOW_END_ENV, PIPELINE_WINDOW_START_ENV


_CENTRAL_TZ = ZoneInfo("America/Chicago")
OUTPUT_DIR = REPO_ROOT / "outputs" / "daily"


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value).strip())


def _build_utc_window_for_central_date(target_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=_CENTRAL_TZ)
    end_local = start_local + timedelta(days=1) - timedelta(seconds=1)
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None, microsecond=0)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None, microsecond=0)
    return start_utc, end_utc


def _iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _save_output(target_date: date, content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{target_date.isoformat()}.txt"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay and persist historical daily digests from stored articles without sending email."
    )
    parser.add_argument("--date", help="Single Central date to replay, in YYYY-MM-DD format.")
    parser.add_argument("--start-date", help="Inclusive Central start date to replay, in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="Inclusive Central end date to replay, in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Generate output but do not persist files or DB rows.")
    args = parser.parse_args()

    if args.date:
        if args.start_date or args.end_date:
            parser.error("Use either --date or --start-date/--end-date, not both.")
        args.start_date = args.date
        args.end_date = args.date

    if not args.start_date or not args.end_date:
        parser.error("Provide --date or both --start-date and --end-date.")

    return args


def main():
    args = parse_args()
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if start_date > end_date:
        raise ValueError("start date must be on or before end date")

    init_db()
    original_window_start = os.getenv(PIPELINE_WINDOW_START_ENV)
    original_window_end = os.getenv(PIPELINE_WINDOW_END_ENV)

    try:
        for target_date in _iter_dates(start_date, end_date):
            window_start, window_end = _build_utc_window_for_central_date(target_date)
            os.environ[PIPELINE_WINDOW_START_ENV] = window_start.isoformat()
            os.environ[PIPELINE_WINDOW_END_ENV] = window_end.isoformat()

            print(f"=== REPLAY {target_date.isoformat()} ===")
            print(f"Window UTC: {window_start.isoformat()} -> {window_end.isoformat()}")
            digest_text = generate_daily_digest(report_date=target_date)

            if args.dry_run:
                print("DRY RUN: generated digest but did not persist file or database row")
                continue

            output_path = _save_output(target_date, digest_text)
            upsert_daily_digest(target_date, digest_text)
            print(f"Saved {output_path}")

    finally:
        if original_window_start is None:
            os.environ.pop(PIPELINE_WINDOW_START_ENV, None)
        else:
            os.environ[PIPELINE_WINDOW_START_ENV] = original_window_start

        if original_window_end is None:
            os.environ.pop(PIPELINE_WINDOW_END_ENV, None)
        else:
            os.environ[PIPELINE_WINDOW_END_ENV] = original_window_end


if __name__ == "__main__":
    main()