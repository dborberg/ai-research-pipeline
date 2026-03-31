"""
Pipeline runner for daily AI research digest.

Scheduling instructions (cron):

- Example (runs daily at 6:30 AM):
  30 6 * * * /FULL/PATH/venv/bin/python /FULL/PATH/run_pipeline.py
"""

import subprocess
import sys
import argparse
import logging
import os
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import text

from app.db import get_engine, init_db, insert_article, upsert_daily_digest

# ✅ Load environment variables (works locally + GitHub Actions)
load_dotenv()


# Logging
logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


DAILY_OUTPUT_DIR = Path("outputs/daily")
_CENTRAL_TZ = ZoneInfo("America/Chicago")


def _central_today():
    """Return today's date in Central Time (CDT/CST), matching the workflow guard step."""
    return datetime.now(_CENTRAL_TZ).date()


def ingest_articles():
    logging.info("Starting ingestion")
    print("Ingesting articles...")

    from app.fetch_rss_articles import fetch_rss_articles, RSS_FEEDS

    # Ensure data directory exists for local SQLite and output artifacts.
    os.makedirs("data", exist_ok=True)

    init_db()

    articles = fetch_rss_articles(RSS_FEEDS)

    inserted = 0

    for article in articles:
        try:
            insert_article(article)
            inserted += 1
        except Exception as e:
            logging.warning(f"Insert failed: {e}")

    logging.info(f"Ingestion completed: {inserted} articles processed")
    print(f"Ingested {inserted} articles")
    return articles


def enrich_articles():
    logging.info("Starting enrichment")
    print("Enriching articles...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "app.enrich_articles",
            "--limit",
            "40",
            "--max-age-hours",
            "36",
        ],
        check=True,
    )
    logging.info("Enrichment completed")


def _count_enriched_articles(feedly_ids):
    unique_ids = sorted({feedly_id for feedly_id in feedly_ids if feedly_id})
    if not unique_ids:
        return 0

    placeholders = ", ".join([f":feedly_id_{index}" for index in range(len(unique_ids))])
    params = {f"feedly_id_{index}": feedly_id for index, feedly_id in enumerate(unique_ids)}

    with get_engine().connect() as conn:
        return conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM articles
                WHERE feedly_id IN ({placeholders})
                  AND ai_score IS NOT NULL
                  AND advisor_relevance IS NOT NULL
                  AND TRIM(advisor_relevance) != ''
                """
            ),
            params,
        ).scalar_one()


def _validate_recent_enrichment(articles):
    ingested_ids = [article.get("link") for article in articles if article.get("link")]
    if not ingested_ids:
        return

    enriched_count = _count_enriched_articles(ingested_ids)
    required_count = len(ingested_ids) if len(ingested_ids) <= 5 else math.ceil(len(ingested_ids) * 0.6)

    if enriched_count < required_count:
        raise RuntimeError(
            "Recent article enrichment is incomplete "
            f"({enriched_count}/{len(ingested_ids)} enriched, required {required_count})"
        )


def generate_daily_digest():
    logging.info("Starting digest generation")
    print("Generating digest...")
    from app.generate_digest import generate_daily_digest as _generate
    digest = _generate()
    logging.info("Digest generation completed")
    return digest


def save_daily_digest(digest_text):
    logging.info("Saving daily digest")
    print("Saving digest...")

    DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DAILY_OUTPUT_DIR / f"{_central_today().isoformat()}.txt"

    output_path.write_text(digest_text, encoding="utf-8")

    logging.info(f"Daily digest saved to {output_path}")
    return output_path


def send_digest(digest_text=None, dry_run=False):
    # ✅ DRY RUN (no email)
    if dry_run:
        if digest_text is None:
            digest_text = generate_daily_digest()

        print("\nDRY RUN: Digest generated (not sent)")
        print("=" * 60)
        print(digest_text)
        return

    logging.info("Starting email send")
    print("Sending email...")

    from app.send_email import send_digest as _send

    # ✅ Always send email (GitHub + local)
    _send(digest_text)

    logging.info("Email send completed")


def run(dry_run=False):
    try:
        print("=== PIPELINE START ===")
        logging.info("Pipeline started")

        init_db()
        articles = ingest_articles()
        if not articles:
            print("No articles available — skipping digest generation safely")
            logging.warning("No articles available — skipping digest generation safely")
            return
        try:
            enrich_articles()
        except Exception as e:
            print(f"Enrichment failed: {e}")
            logging.exception("Enrichment failed")
            return

        try:
            _validate_recent_enrichment(articles)
        except Exception as e:
            print(f"Enrichment validation failed: {e}")
            logging.exception("Enrichment validation failed")
            return

        # ✅ Generate ONCE and reuse
        try:
            digest_text = generate_daily_digest()
            if not digest_text or not digest_text.strip():
                raise ValueError("Digest generation returned empty content — aborting to prevent blank output file")
            save_daily_digest(digest_text)
            upsert_daily_digest(_central_today(), digest_text)
        except Exception as e:
            print(f"Digest generation failed: {e}")
            logging.exception("Digest generation failed")
            return

        try:
            send_digest(digest_text=digest_text, dry_run=dry_run)
        except Exception as e:
            print(f"Email failed: {e}")
            logging.exception("Email send failed")

        logging.info("Pipeline completed successfully")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        raise
    finally:
        print("=== PIPELINE END ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily AI research pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Generate digest but do not send email.")
    args = parser.parse_args()

    run(dry_run=args.dry_run)
