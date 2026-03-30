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
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.db import init_db, upsert_daily_digest

# ✅ Load environment variables (works locally + GitHub Actions)
load_dotenv()


# Logging
logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


DB_PATH = "sqlite:///data/ai_research.db"
DAILY_OUTPUT_DIR = Path("outputs/daily")
_CENTRAL_TZ = ZoneInfo("America/Chicago")


def _central_today():
    """Return today's date in Central Time (CDT/CST), matching the workflow guard step."""
    return datetime.now(_CENTRAL_TZ).date()


def ingest_articles():
    logging.info("Starting ingestion")
    print("Ingesting articles...")

    from app.fetch_rss_articles import fetch_rss_articles, RSS_FEEDS

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    engine = create_engine(DB_PATH)

    # Create table if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedly_id TEXT UNIQUE,
                title TEXT,
                source TEXT,
                url TEXT,
                published_at TEXT,
                created_at TEXT,
                ai_score REAL
            )
        """))
        conn.commit()

    articles = fetch_rss_articles(RSS_FEEDS)

    inserted = 0

    with engine.connect() as conn:
        for article in articles:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO articles 
                    (feedly_id, title, source, url, published_at, created_at, summary)
                    VALUES (:feedly_id, :title, :source, :url, :published_at, :created_at, :summary)
                """), {
                    'feedly_id': article.get('link'),
                    'title': article.get('title'),
                    'source': article.get('source'),
                    'url': article.get('link'),
                    'published_at': article.get('published'),
                    'created_at': datetime.utcnow().isoformat(),
                    'summary': article.get('summary') or article.get('text') or '',
                })
                # Fill summary for any existing article that was stored without one
                conn.execute(text("""
                    UPDATE articles
                    SET summary = :summary
                    WHERE feedly_id = :feedly_id AND (summary IS NULL OR summary = '')
                """), {
                    'feedly_id': article.get('link'),
                    'summary': article.get('summary') or article.get('text') or '',
                })
                inserted += 1
            except Exception as e:
                logging.warning(f"Insert failed: {e}")

        conn.commit()

    logging.info(f"Ingestion completed: {inserted} articles processed")
    print(f"Ingested {inserted} articles")
    return articles


def enrich_articles():
    logging.info("Starting enrichment")
    print("Enriching articles...")
    subprocess.run([sys.executable, "app/enrich_articles.py"], check=True)
    logging.info("Enrichment completed")


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
        logging.info("Pipeline started")

        init_db()
        articles = ingest_articles()
        if not articles:
            print("No articles available — skipping digest generation safely")
            logging.warning("No articles available — skipping digest generation safely")
            return
        enrich_articles()

        # ✅ Generate ONCE and reuse
        digest_text = generate_daily_digest()
        if not digest_text or not digest_text.strip():
            raise ValueError("Digest generation returned empty content — aborting to prevent blank output file")
        save_daily_digest(digest_text)
        upsert_daily_digest(_central_today(), digest_text)

        send_digest(digest_text=digest_text, dry_run=dry_run)

        logging.info("Pipeline completed successfully")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily AI research pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Generate digest but do not send email.")
    args = parser.parse_args()

    run(dry_run=args.dry_run)
