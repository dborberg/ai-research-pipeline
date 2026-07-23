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
                            "id": 42,
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
                self.assertEqual(archived_articles[0]["id"], 42)
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

    def test_load_daily_source_snapshot_synthesizes_id_for_legacy_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_daily_output_dir = source_archive.DAILY_OUTPUT_DIR
            original_daily_snapshot_dir = source_archive.DAILY_SNAPSHOT_DIR
            try:
                source_archive.DAILY_OUTPUT_DIR = Path(tmpdir) / "daily"
                source_archive.DAILY_SNAPSHOT_DIR = source_archive.DAILY_OUTPUT_DIR / "source_snapshots"
                source_archive.DAILY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

                legacy_snapshot = source_archive.DAILY_SNAPSHOT_DIR / "2026-06-26.json"
                legacy_snapshot.write_text(
                    '{\n'
                    '  "date": "2026-06-26",\n'
                    '  "article_count": 1,\n'
                    '  "articles": [\n'
                    '    {\n'
                    '      "title": "Legacy article",\n'
                    '      "url": "https://example.com/legacy",\n'
                    '      "published_at": "2026-06-26T12:00:00",\n'
                    '      "ai_score": 8\n'
                    '    }\n'
                    '  ]\n'
                    '}\n',
                    encoding="utf-8",
                )

                archived_articles = source_archive.load_daily_source_snapshot(date(2026, 6, 26))

                self.assertEqual(len(archived_articles), 1)
                self.assertIsInstance(archived_articles[0]["id"], int)
                self.assertLess(archived_articles[0]["id"], 0)
            finally:
                source_archive.DAILY_OUTPUT_DIR = original_daily_output_dir
                source_archive.DAILY_SNAPSHOT_DIR = original_daily_snapshot_dir

    def test_load_monthly_digest_files_returns_daily_and_weekly_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_daily_output_dir = source_archive.DAILY_OUTPUT_DIR
            original_daily_snapshot_dir = source_archive.DAILY_SNAPSHOT_DIR
            original_weekly_output_dir = source_archive.WEEKLY_OUTPUT_DIR
            try:
                source_archive.DAILY_OUTPUT_DIR = Path(tmpdir) / "daily"
                source_archive.DAILY_SNAPSHOT_DIR = source_archive.DAILY_OUTPUT_DIR / "source_snapshots"
                source_archive.WEEKLY_OUTPUT_DIR = Path(tmpdir) / "weekly"

                source_archive.DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                source_archive.WEEKLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                (source_archive.DAILY_OUTPUT_DIR / "2026-06-01.txt").write_text("Daily A", encoding="utf-8")
                (source_archive.DAILY_OUTPUT_DIR / "2026-06-15.txt").write_text("Daily B", encoding="utf-8")
                (source_archive.WEEKLY_OUTPUT_DIR / "2026-06-05_wholesaler.txt").write_text("Weekly W", encoding="utf-8")
                (source_archive.WEEKLY_OUTPUT_DIR / "2026-06-12_thematic.txt").write_text("Weekly T", encoding="utf-8")

                daily_rows = source_archive.load_daily_digests_for_month("2026-06")
                weekly_rows = source_archive.load_weekly_digests_from_files("2026-06")

                self.assertEqual(
                    [row["date"] for row in daily_rows],
                    ["2026-06-01", "2026-06-15"],
                )
                self.assertEqual(
                    {(row["week_start"], row["type"]) for row in weekly_rows},
                    {("2026-06-05", "wholesaler"), ("2026-06-12", "thematic")},
                )
            finally:
                source_archive.DAILY_OUTPUT_DIR = original_daily_output_dir
                source_archive.DAILY_SNAPSHOT_DIR = original_daily_snapshot_dir
                source_archive.WEEKLY_OUTPUT_DIR = original_weekly_output_dir