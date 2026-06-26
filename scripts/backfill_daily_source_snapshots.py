#!/usr/bin/env python3

import argparse
from collections import Counter
from datetime import date
import os
import sqlite3
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.source_archive import DAILY_SNAPSHOT_DIR, save_daily_source_snapshot


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


SQLITE_DB_PATH = Path(os.getenv("SQLITE_DB_PATH", "data/ai_research.db"))


def _parse_date(value):
    if value is None:
        return None
    return date.fromisoformat(str(value).strip())


def _fetch_article_days(start_date=None, end_date=None):
    conditions = []
    params = {}

    if start_date is not None:
        conditions.append("substr(published_at, 1, 10) >= :start_date")
        params["start_date"] = start_date.isoformat()
    if end_date is not None:
        conditions.append("substr(published_at, 1, 10) <= :end_date")
        params["end_date"] = end_date.isoformat()

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT substr(published_at, 1, 10) AS published_day
        FROM articles
        {where_clause}
        GROUP BY published_day
        ORDER BY published_day ASC
    """

    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        return [row[0] for row in conn.execute(query, params).fetchall() if row[0]]


def _fetch_articles_for_day(published_day):
    query = """
        SELECT
            title,
            source,
            COALESCE(original_publisher, source) AS original_publisher,
            summary,
            url,
            published_at,
            companies,
            advisor_relevance,
            ai_score,
            is_space_economy_related,
            space_relevance,
            space_ai_connection,
            space_time_horizon,
            space_investment_layer
        FROM articles
        WHERE substr(published_at, 1, 10) = :published_day
        ORDER BY
            CASE WHEN ai_score IS NULL THEN 1 ELSE 0 END,
            ai_score DESC,
            published_at DESC
    """

    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, {"published_day": published_day}).fetchall()
    return [dict(row) for row in rows]


def backfill_daily_source_snapshots(start_date=None, end_date=None, overwrite=False):
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_DB_PATH}")

    archived_days = []
    skipped_days = []
    article_counts = Counter()

    for published_day in _fetch_article_days(start_date=start_date, end_date=end_date):
        snapshot_path = DAILY_SNAPSHOT_DIR / f"{published_day}.json"
        if snapshot_path.exists() and not overwrite:
            skipped_days.append(published_day)
            continue

        articles = _fetch_articles_for_day(published_day)
        save_daily_source_snapshot(published_day, articles)
        archived_days.append(published_day)
        article_counts[published_day] = len(articles)

    return {
        "archived_days": archived_days,
        "skipped_days": skipped_days,
        "article_counts": article_counts,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backfill archived daily source snapshots from existing article history.")
    parser.add_argument("--start-date", help="Optional start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="Optional end date in YYYY-MM-DD format.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing source snapshots.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    result = backfill_daily_source_snapshots(
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        overwrite=bool(args.overwrite),
    )

    archived_days = result["archived_days"]
    skipped_days = result["skipped_days"]
    article_counts = result["article_counts"]

    print(f"Archived {len(archived_days)} day(s) into {DAILY_SNAPSHOT_DIR}")
    if archived_days:
        print(f"Date range archived: {archived_days[0]} -> {archived_days[-1]}")
        print(f"Total articles archived: {sum(article_counts.values())}")
        print("Largest daily archives:")
        for published_day, count in article_counts.most_common(10):
            print(f"  {published_day}: {count} article(s)")
    if skipped_days:
        print(f"Skipped existing snapshot days: {len(skipped_days)}")


if __name__ == "__main__":
    main()