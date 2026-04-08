import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db import get_engine, init_db
from app.fetch_rss_articles import fetch_full_article


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill stored article text for recent articles.")
    parser.add_argument("--days", type=int, default=3, help="Look back this many days from now (default: 3).")
    parser.add_argument("--limit", type=int, default=30, help="Maximum articles to backfill (default: 30).")
    parser.add_argument(
        "--min-text-length",
        type=int,
        default=500,
        help="Treat stored article text shorter than this as incomplete (default: 500).",
    )
    return parser.parse_args()


def _parse_timestamp(value):
    if not value:
        return None

    text_value = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _load_candidates(days, limit, min_text_length):
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    title,
                    url,
                    published_at,
                    created_at,
                    summary,
                    raw_text,
                    cleaned_text
                FROM articles
                WHERE url IS NOT NULL
                  AND TRIM(url) != ''
                ORDER BY published_at DESC, created_at DESC
                """
            )
        ).mappings().all()

    candidates = []
    for row in rows:
        reference_dt = _parse_timestamp(row["published_at"]) or _parse_timestamp(row["created_at"])
        if reference_dt and reference_dt < cutoff:
            continue

        raw_text = row["raw_text"] or ""
        cleaned_text = row["cleaned_text"] or ""
        if len(raw_text) >= min_text_length and len(cleaned_text) >= min_text_length:
            continue

        candidates.append(row)
        if len(candidates) >= limit:
            break

    return candidates


def main():
    args = parse_args()
    init_db()

    candidates = _load_candidates(args.days, args.limit, args.min_text_length)
    print(f"Candidates to backfill: {len(candidates)}")

    updated = 0
    for row in candidates:
        article_id = row["id"]
        title = row["title"] or ""
        url = row["url"] or ""
        print(f"Fetching: {title[:90]}")

        full_text = fetch_full_article(url)
        if not full_text:
            print("  Skipped: unable to extract enough article text")
            continue

        with get_engine().begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE articles
                    SET raw_text = :raw_text,
                        cleaned_text = :cleaned_text
                    WHERE id = :article_id
                    """
                ),
                {
                    "article_id": article_id,
                    "raw_text": full_text,
                    "cleaned_text": full_text,
                },
            )

        updated += 1
        print(f"  Updated article {article_id}")

    print(f"Backfill complete: {updated}/{len(candidates)} updated")


if __name__ == "__main__":
    main()