import importlib
import sys
import types
import unittest


def _load_monthly_module():
    original_modules = {name: sys.modules.get(name) for name in [
        "dotenv",
        "pandas",
        "sqlalchemy",
        "app.branding",
        "app.cluster_schema",
        "app.db",
        "app.reporting",
        "app.runtime_secrets",
        "app.send_email",
        "app.source_archive",
        "app.space_economy",
    ]}

    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_module

    pandas_module = types.ModuleType("pandas")
    pandas_module.DataFrame = lambda *args, **kwargs: None
    pandas_module.to_datetime = lambda *args, **kwargs: None
    sys.modules["pandas"] = pandas_module

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.text = lambda value: value
    sys.modules["sqlalchemy"] = sqlalchemy_module

    branding_module = types.ModuleType("app.branding")
    branding_module.MONTHLY_TITLE = "Monthly"
    sys.modules["app.branding"] = branding_module

    cluster_module = types.ModuleType("app.cluster_schema")
    cluster_module.normalize_cluster_df = lambda value: value
    sys.modules["app.cluster_schema"] = cluster_module

    db_module = types.ModuleType("app.db")
    db_module.fetch_daily_digests = lambda *args, **kwargs: []
    db_module.fetch_weekly_digests = lambda *args, **kwargs: []
    db_module.get_engine = lambda: None
    db_module.get_weekly_clusters = lambda *args, **kwargs: []
    db_module.init_db = lambda *args, **kwargs: None
    db_module.upsert_monthly_report = lambda *args, **kwargs: None
    sys.modules["app.db"] = db_module

    reporting_module = types.ModuleType("app.reporting")
    reporting_module.build_monthly_source_context = lambda *args, **kwargs: ""
    reporting_module.call_chat_model = lambda *args, **kwargs: ""
    reporting_module.get_latest_completed_friday = lambda *args, **kwargs: None
    reporting_module.get_latest_completed_month = lambda *args, **kwargs: "2026-06"
    reporting_module.get_month_bounds = lambda report_month: (__import__("datetime").date(2026, 6, 1), __import__("datetime").date(2026, 7, 1))
    reporting_module.get_openai_client = lambda *args, **kwargs: None
    reporting_module.save_text_output = lambda *args, **kwargs: None
    sys.modules["app.reporting"] = reporting_module

    runtime_module = types.ModuleType("app.runtime_secrets")
    runtime_module.get_openai_api_key = lambda default="": default
    sys.modules["app.runtime_secrets"] = runtime_module

    send_module = types.ModuleType("app.send_email")
    send_module.send_report = lambda *args, **kwargs: None
    sys.modules["app.send_email"] = send_module

    source_archive_module = types.ModuleType("app.source_archive")
    source_archive_module.load_daily_digests_for_month = lambda report_month: []
    source_archive_module.load_weekly_digests_from_files = lambda report_month: []
    sys.modules["app.source_archive"] = source_archive_module

    space_module = types.ModuleType("app.space_economy")
    space_module.SPACE_ECONOMY_FILTER_PROMPT = ""
    space_module.calculate_space_economy_theme_active = lambda *args, **kwargs: False
    space_module.ensure_space_metadata = lambda article: article
    sys.modules["app.space_economy"] = space_module

    try:
        sys.modules.pop("run_monthly_pipeline", None)
        return importlib.import_module("run_monthly_pipeline")
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


run_monthly_pipeline = _load_monthly_module()


class MonthlyHistoryFallbackTests(unittest.TestCase):
    def test_merge_monthly_history_rows_adds_file_fallback_without_overwriting_db(self):
        run_monthly_pipeline.load_weekly_digests_from_files = lambda report_month: [
            {"week_start": "2026-06-06", "type": "wholesaler", "content": "File weekly duplicate"},
            {"week_start": "2026-06-13", "type": "thematic", "content": "File weekly new"},
        ]
        run_monthly_pipeline.load_daily_digests_for_month = lambda report_month: [
            {"date": "2026-06-01", "content": "File daily duplicate"},
            {"date": "2026-06-02", "content": "File daily new"},
        ]

        weekly_rows, daily_rows = run_monthly_pipeline._merge_monthly_history_rows(
            "2026-06",
            [{"week_start": "2026-06-06", "type": "wholesaler", "content": "DB weekly"}],
            [{"date": "2026-06-01", "content": "DB daily"}],
        )

        self.assertEqual(
            weekly_rows,
            [
                {"week_start": "2026-06-06", "type": "wholesaler", "content": "DB weekly"},
                {"week_start": "2026-06-13", "type": "thematic", "content": "File weekly new"},
            ],
        )
        self.assertEqual(
            daily_rows,
            [
                {"date": "2026-06-01", "content": "DB daily"},
                {"date": "2026-06-02", "content": "File daily new"},
            ],
        )


if __name__ == "__main__":
    unittest.main()