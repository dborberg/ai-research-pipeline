import importlib
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path


def _load_weekly_investment_module():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    app_db = types.ModuleType("app.db")
    app_db.fetch_weekly_digests = lambda *args, **kwargs: []
    app_db.init_db = lambda: None
    sys.modules["app.db"] = app_db

    app_reporting = types.ModuleType("app.reporting")
    app_reporting.get_latest_completed_friday = lambda: date(2026, 7, 3)
    app_reporting.get_openai_client = lambda api_key: object()
    sys.modules["app.reporting"] = app_reporting

    app_send_email = types.ModuleType("app.send_email")
    app_send_email.send_report = lambda *args, **kwargs: None
    sys.modules["app.send_email"] = app_send_email

    weekly_pipeline = types.ModuleType("run_weekly_pipeline")
    weekly_pipeline.THEMATIC_TITLE = "thematic"
    weekly_pipeline.WHOLESALER_TITLE = "wholesaler"
    weekly_pipeline._generate_and_store_weekly_reports = lambda *args, **kwargs: {
        "wholesaler": "generated wholesaler",
        "thematic": "generated thematic",
    }
    sys.modules["run_weekly_pipeline"] = weekly_pipeline

    sys.modules.pop("run_weekly_investment_pipeline", None)
    return importlib.import_module("run_weekly_investment_pipeline")


run_weekly_investment_pipeline = _load_weekly_investment_module()


class WeeklyInvestmentPipelineTests(unittest.TestCase):
    def test_thematic_mode_uses_saved_output_without_regeneration(self):
        module = run_weekly_investment_pipeline
        original_outputs_dir = module.OUTPUTS_DIR
        original_generator = module._generate_and_store_weekly_reports

        with tempfile.TemporaryDirectory() as temp_dir:
            module.OUTPUTS_DIR = Path(temp_dir)
            thematic_path = module.OUTPUTS_DIR / "2026-07-03_thematic.txt"
            thematic_path.write_text("saved thematic output\n", encoding="utf-8")

            def fail_if_called(*args, **kwargs):
                raise AssertionError("generation should not run when saved thematic output exists")

            module._generate_and_store_weekly_reports = fail_if_called

            try:
                reports = module._load_or_generate_reports("THEMATIC", date(2026, 7, 3))
            finally:
                module.OUTPUTS_DIR = original_outputs_dir
                module._generate_and_store_weekly_reports = original_generator

        self.assertEqual(reports["thematic"], "saved thematic output")


if __name__ == "__main__":
    unittest.main()