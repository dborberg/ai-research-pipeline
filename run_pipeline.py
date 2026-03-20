"""
Pipeline runner for daily AI research digest.

Scheduling instructions (cron):

- Example (runs daily at 6:00 AM):
  0 6 * * * /FULL/PATH/venv/bin/python /FULL/PATH/run_pipeline.py
"""

import subprocess
import sys
import argparse
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ✅ Load environment variables (works locally + GitHub Actions)
load_dotenv()


# Logging
logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


DB_PATH = "sqlite:///data/ai_research.db"


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
                    (feedly_id, title, source, url, published_at, created_at)
                    VALUES (:feedly_id, :title, :source, :url, :published_at, :created_at)
                """), {
                    'feedly_id': article.get('link'),
                    'title': article.get('title'),
                    'source': article.get('source'),
                    'url': article.get('link'),
                    'published_at': article.get('published'),
                    'created_at': datetime.utcnow().isoformat()
                })
                inserted += 1
            except Exception as e:
                logging.warning(f"Insert failed: {e}")

        conn.commit()

    logging.info(f"Ingestion completed: {inserted} articles processed")
    print(f"Ingested {inserted} articles")


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

        ingest_articles()
        enrich_articles()

        # ✅ Generate ONCE and reuse
        digest_text = generate_daily_digest()

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