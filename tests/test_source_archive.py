import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import source_archive


class SourceArchiveTests(unittest.TestCase):
    def test_save_and_load_daily_source_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_daily_output_dir = source_archive.DAILY_OUTPUT_DIR
            original_daily_snapshot_dir = source_archive.DAILY_SNAPSHOT_DIR
            try:
                source_archive.DAILY_OUTPUT_DIR = Path(tmpdir) / "daily"
                source_archive.DAILY_SNAPSHOT_DIR = source_archive.DAILY_OUTPUT_DIR / "source_snapshots"

                source_archive.save_daily_source_snapshot(
                    date(2026, 6, 26),
                    [
                        {
                            "title": "Micron earnings",
                            "url": "https://example.com/micron",
                            "published_at": "2026-06-26T12:00:00",
                            "companies": ["Micron"],
                            "ai_score": 9,
                        }
                    ],
                )

                archived_articles = source_archive.load_daily_source_snapshot(date(2026, 6, 26))

                self.assertEqual(len(archived_articles), 1)
                self.assertEqual(archived_articles[0]["title"], "Micron earnings")
                self.assertEqual(archived_articles[0]["companies"], ["Micron"])
            finally:
                source_archive.DAILY_OUTPUT_DIR = original_daily_output_dir
                source_archive.DAILY_SNAPSHOT_DIR = original_daily_snapshot_dir

    def test_load_weekly_articles_from_daily_snapshots_dedupes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_daily_output_dir = source_archive.DAILY_OUTPUT_DIR
            original_daily_snapshot_dir = source_archive.DAILY_SNAPSHOT_DIR
            try:
                source_archive.DAILY_OUTPUT_DIR = Path(tmpdir) / "daily"
                source_archive.DAILY_SNAPSHOT_DIR = source_archive.DAILY_OUTPUT_DIR / "source_snapshots"

                shared_article = {
                    "title": "Shared story",
                    "url": "https://example.com/shared",
                    "published_at": "2026-06-25T10:00:00",
                    "ai_score": 8,
                }
                source_archive.save_daily_source_snapshot(date(2026, 6, 25), [shared_article])
                source_archive.save_daily_source_snapshot(
                    date(2026, 6, 26),
                    [shared_article, {"title": "Distinct story", "url": "https://example.com/distinct", "published_at": "2026-06-26T11:00:00", "ai_score": 7}],
                )

                archived_articles = source_archive.load_weekly_articles_from_daily_snapshots(date(2026, 6, 26))

                self.assertEqual(len(archived_articles), 2)
                self.assertEqual({article["title"] for article in archived_articles}, {"Shared story", "Distinct story"})
            finally:
                source_archive.DAILY_OUTPUT_DIR = original_daily_output_dir
                source_archive.DAILY_SNAPSHOT_DIR = original_daily_snapshot_dir