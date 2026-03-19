"""Pipeline runner for daily AI research digest.

Scheduling instructions (cron):

- Use cron (Mac/Linux) to run this script automatically every day.
- Example (runs daily at 6:00 AM):

  0 6 * * * /FULL/PATH/venv/bin/python /FULL/PATH/run_pipeline.py

- Replace /FULL/PATH with the absolute path to your workspace and the correct python executable.

Cron is a standard time-based scheduler used to run scripts automatically at set times.
"""

import subprocess
import sys
import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


# Set up logging to file
logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def ingest_articles():
    logging.info("Starting ingestion")
    from app.fetch_rss_articles import fetch_rss_articles, RSS_FEEDS
    from sqlalchemy import create_engine, text
    articles = fetch_rss_articles(RSS_FEEDS)
    engine = create_engine("sqlite:///data/ai_research.db")
    with engine.connect() as conn:
        for article in articles:
            conn.execute(text("""
                INSERT OR IGNORE INTO articles (feedly_id, title, source, url, published_at, created_at)
                VALUES (:feedly_id, :title, :source, :url, :published_at, :created_at)
            """), {
                'feedly_id': article.get('link'),
                'title': article.get('title'),
                'source': article.get('source'),
                'url': article.get('link'),
                'published_at': article.get('published'),
                'created_at': datetime.utcnow().isoformat()
            })
        conn.commit()
    logging.info(f"Ingestion completed: {len(articles)} articles inserted")


def enrich_articles():
    logging.info("Starting enrichment")
    subprocess.run([sys.executable, "app/enrich_articles.py"], check=True)
    logging.info("Enrichment completed")


def generate_daily_digest():
    logging.info("Starting digest generation")
    from app.generate_digest import generate_daily_digest as _generate
    digest = _generate()
    logging.info("Digest generation completed")
    return digest


def send_digest(dry_run=False):
    if dry_run:
        digest = generate_daily_digest()
        print("DRY RUN: Digest generated (not sent)")
        print("=" * 50)
        print(digest)
        return

    logging.info("Starting email send")
    from app.send_email import send_digest as _send
    _send()
    logging.info("Email send completed")


def run(dry_run=False):
    try:
        logging.info("Pipeline started")
        print("Ingesting...")
        ingest_articles()

        print("Enriching...")
        enrich_articles()

        print("Generating digest...")
        digest_text = generate_daily_digest()

        print("Sending email...")
        send_digest(dry_run=dry_run)

        logging.info("Pipeline completed successfully")
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily AI research pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Generate digest but do not send email.")
    args = parser.parse_args()

    run(dry_run=args.dry_run)
