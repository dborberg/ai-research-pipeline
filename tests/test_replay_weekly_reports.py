import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_replay_module():
    module_names = [
        "dotenv",
        "app.db",
        "app.reporting",
        "app.pipeline_window",
        "app.generate_digest",
        "run_weekly_pipeline",
    ]
    original_modules = {name: sys.modules.get(name) for name in module_names}

    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_module

    app_db = types.ModuleType("app.db")
    app_db.get_sqlite_db_path = lambda *args, **kwargs: None
    app_db.init_db = lambda: None
    sys.modules["app.db"] = app_db

    app_reporting = types.ModuleType("app.reporting")
    app_reporting.get_openai_client = lambda *args, **kwargs: None
    app_reporting.save_text_output = lambda *args, **kwargs: None
    sys.modules["app.reporting"] = app_reporting

    app_pipeline_window = types.ModuleType("app.pipeline_window")
    app_pipeline_window.PIPELINE_WINDOW_START_ENV = "PIPELINE_WINDOW_START_UTC"
    app_pipeline_window.PIPELINE_WINDOW_END_ENV = "PIPELINE_WINDOW_END_UTC"
    sys.modules["app.pipeline_window"] = app_pipeline_window

    app_generate_digest = types.ModuleType("app.generate_digest")
    app_generate_digest.generate_daily_digest = lambda *args, **kwargs: ""
    sys.modules["app.generate_digest"] = app_generate_digest

    weekly_module = types.ModuleType("run_weekly_pipeline")
    weekly_module.DEBUG_WEEKLY_SCORING = False
    weekly_module.DEFAULT_SCORE_THRESHOLD = 6
    weekly_module.THEMATIC_TITLE = "Thematic"
    weekly_module.WHOLESALER_TITLE = "Wholesaler"
    weekly_module._build_weekly_cluster_bundle = lambda *args, **kwargs: {
        "clusters": [],
        "patterns": {},
        "article_data": {},
        "SPACE_ECONOMY_THEME_ACTIVE": False,
    }
    weekly_module._build_wholesaler_event_context = lambda *args, **kwargs: ""
    weekly_module._format_cluster_context = lambda *args, **kwargs: ""
    weekly_module._with_weekly_report_header = lambda title, week_start, content: content
    weekly_module.generate_thematic_weekly = lambda *args, **kwargs: ""
    weekly_module.generate_wholesaler_weekly = lambda *args, **kwargs: ""
    sys.modules["run_weekly_pipeline"] = weekly_module

    try:
        module_path = REPO_ROOT / "scripts" / "replay_weekly_reports.py"
        spec = importlib.util.spec_from_file_location("replay_weekly_reports_test_module", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


replay_weekly_reports = _load_replay_module()


class ReplayWeeklyReportsTests(unittest.TestCase):
    def test_week_dates_cover_full_friday_ending_range(self):
        week_ending = date(2026, 6, 26)

        dates = replay_weekly_reports._week_dates(week_ending)

        self.assertEqual(dates[0].isoformat(), "2026-06-20")
        self.assertEqual(dates[-1].isoformat(), "2026-06-26")
        self.assertEqual(len(dates), 7)

    def test_format_replay_daily_digest_context_matches_weekly_shape(self):
        context = replay_weekly_reports._format_replay_daily_digest_context(
            [
                (date(2026, 6, 25), "Digest A"),
                (date(2026, 6, 26), "Digest B"),
            ]
        )

        self.assertIn("DATE: 2026-06-25", context)
        self.assertIn("DIGEST:\nDigest A", context)
        self.assertIn("DATE: 2026-06-26", context)
        self.assertIn("DIGEST:\nDigest B", context)

    def test_build_replay_weekly_source_context_includes_both_inputs(self):
        source_context = replay_weekly_reports._build_replay_weekly_source_context(
            "CLUSTERED",
            "DAILIES",
        )

        self.assertIn("PRIMARY INPUT: TIER 1 DAILY-DERIVED CANDIDATES", source_context)
        self.assertIn("SUPPLEMENTAL INPUT: CLUSTERED THEMES FROM THE WEEKLY ARTICLE SET", source_context)
        self.assertIn("DAILIES", source_context)
        self.assertIn("CLUSTERED", source_context)


if __name__ == "__main__":
    unittest.main()