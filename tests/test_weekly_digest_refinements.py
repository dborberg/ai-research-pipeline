import unittest
from datetime import date
from pathlib import Path
import sys
import types

from scripts.validate_weekly_digest_output import validate_weekly_digest_text


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_weekly_runner_module():
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None
    sys.modules.setdefault("dotenv", dotenv_module)

    pandas_module = types.ModuleType("pandas")
    pandas_module.DataFrame = lambda *args, **kwargs: None
    sys.modules.setdefault("pandas", pandas_module)

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.text = lambda value: value
    sys.modules.setdefault("sqlalchemy", sqlalchemy_module)

    app_cluster_schema = types.ModuleType("app.cluster_schema")
    app_cluster_schema.normalize_cluster_df = lambda value: value
    sys.modules.setdefault("app.cluster_schema", app_cluster_schema)

    app_branding = types.ModuleType("app.branding")
    app_branding.WEEKLY_THEMATIC_TITLE = "thematic"
    app_branding.WEEKLY_WHOLESALER_TITLE = "wholesaler"
    sys.modules.setdefault("app.branding", app_branding)

    app_db = types.ModuleType("app.db")
    app_db.fetch_daily_digests = lambda *args, **kwargs: []
    app_db.fetch_weekly_digests = lambda *args, **kwargs: []
    app_db.get_engine = lambda: None
    app_db.get_weekly_clusters = lambda *args, **kwargs: []
    app_db.init_db = lambda: None
    app_db.save_weekly_clusters = lambda *args, **kwargs: None
    app_db.upsert_weekly_digest = lambda *args, **kwargs: None
    sys.modules.setdefault("app.db", app_db)

    app_generate_digest = types.ModuleType("app.generate_digest")
    app_generate_digest.frontier_technology_capital_markets_score = lambda article: 0.0
    app_generate_digest.is_frontier_technology_capital_markets_event = lambda article: False
    sys.modules.setdefault("app.generate_digest", app_generate_digest)

    app_reporting = types.ModuleType("app.reporting")
    app_reporting.call_chat_model = lambda *args, **kwargs: ""
    app_reporting.get_month_bounds = lambda *args, **kwargs: None
    app_reporting.get_openai_client = lambda *args, **kwargs: None
    app_reporting.get_latest_completed_friday = lambda: None
    app_reporting.get_weekly_window_bounds = lambda *args, **kwargs: ("", "")
    app_reporting.save_text_output = lambda *args, **kwargs: None
    sys.modules.setdefault("app.reporting", app_reporting)

    app_send_email = types.ModuleType("app.send_email")
    app_send_email.send_report = lambda *args, **kwargs: None
    sys.modules.setdefault("app.send_email", app_send_email)

    app_space_economy = types.ModuleType("app.space_economy")
    app_space_economy.SPACE_ECONOMY_FILTER_PROMPT = ""
    app_space_economy.calculate_space_economy_theme_active = lambda *args, **kwargs: False
    app_space_economy.ensure_space_metadata = lambda article: article
    app_space_economy.format_space_metadata_lines = lambda article: []
    sys.modules.setdefault("app.space_economy", app_space_economy)

    app_velocity = types.ModuleType("app.velocity")
    app_velocity.apply_velocity_metrics = lambda *args, **kwargs: None
    app_velocity.compute_velocity = lambda *args, **kwargs: None
    sys.modules.setdefault("app.velocity", app_velocity)

    import importlib

    sys.modules.pop("run_weekly_pipeline", None)
    return importlib.import_module("run_weekly_pipeline")


run_weekly_pipeline = _load_weekly_runner_module()


def _valid_weekly_text(top_story=None):
    top_story = top_story or (
        "1. SpaceX's IPO became a major frontier-technology capital markets signal, even though it is not a pure Gen AI story. "
        "The offering matters for the broader innovation cycle because it tests public-market appetite for mega-cap private technology and connects to satellite communications, defense, autonomy, edge connectivity, strategic infrastructure, and private-market liquidity."
    )
    return f"""
Beyond the Horizon: Weekly Riffs from the Gen AI Songbook
Week Ending June 12, 2026

TOP 5 STORIES THIS WEEK
{top_story}
2. Microsoft expanded governed agent workflows for enterprise customers, showing that production readiness is becoming a practical adoption test. The advisor takeaway is that workflow orchestration, identity, auditability, and cost control are now part of the AI infrastructure conversation.
3. A major data center financing package showed that AI infrastructure is becoming a balance-sheet and credit-market story across the week. The portfolio conversation is broadening from chips to power equipment, cooling, networking, utilities, and private credit.
4. Regulators advanced AI procurement and disclosure rules, reinforcing the pattern that governance is becoming a commercial-access requirement. The wholesaler angle is that compliance, audit trails, and privacy controls can shape which platforms enterprises trust.
5. Robotics deployments moved from demonstrations toward production workflows in logistics and manufacturing. That signal matters because physical AI commercialization depends on uptime, safety approvals, and unit economics rather than funding headlines alone.

BEYOND THE MAG 7
1. Frontier technology capital markets broadened beyond the largest AI platform names as satellite communications, defense networks, and edge connectivity became part of the AI-adjacent infrastructure discussion. This matters now because private-market liquidity and IPO tone can influence risk appetite across the innovation cycle.
2. Power equipment, cooling, networking, and utility suppliers remained central to the week's infrastructure pattern. The supplier effect is that AI demand is showing up as grid, thermal, and interconnection pressure rather than only cloud software demand.
3. Governance software and implementation partners gained relevance as enterprises asked for production controls. The customer adoption lens is that AI spending is shifting toward systems that can run inside regulated workflows.

WHAT IS BEING DISRUPTED
1. The old assumption that AI infrastructure means only chips is being disrupted by financing, power, cooling, satellite communications, and defense connectivity signals.
2. Standalone chatbot adoption is being disrupted by governed workflow orchestration and platform convergence across enterprise systems.
3. Robotics hype is being disrupted by the need for real deployments, uptime, safety approvals, and measurable unit economics.

REGULATORY RADAR
1. AI procurement guidance from policymakers made governance a practical buying requirement rather than a theoretical policy issue. Advisors can frame this as a business-model signal for auditability and compliance infrastructure.
2. Local permitting and interconnection debates around data centers showed that infrastructure policy can influence how quickly AI capacity becomes buildable supply. The investment relevance is that power availability and local approvals may shape deployment timelines.

WHAT TO WATCH NEXT
1. Frontier-tech IPO appetite: Track aftermarket performance, follow-on issuance, and new IPO filings after major frontier technology listings to gauge whether public markets are reopening for large private innovation companies.
2. Data center financing terms: Watch loan spreads, debt capacity, lease structures, and utility-backed financing to see whether capital markets remain willing to fund the next leg of AI infrastructure.
3. Permitting and water disclosures: Monitor moratorium votes, water-use reporting, interconnection queues, and local zoning changes as leading indicators of whether AI capacity forecasts can become buildable supply.
4. Physical AI deployment evidence: Look past robotics funding headlines and monitor customer deployments, uptime, failure rates, safety approvals, and unit economics.
5. Secure inference adoption: Watch whether privacy-preserving AI infrastructure becomes a standard requirement for enterprise and consumer platform deployment.

READY TO USE SOUNDBITES
1. This week showed that AI infrastructure is no longer just a chip story; it is also a financing, power, cooling, networking, and strategic infrastructure story.
2. The useful client conversation is not whether AI matters, but which parts of the buildout are moving from enthusiasm to funded capacity.
3. Production readiness is becoming the enterprise adoption test because permissions, auditability, workflow integration, and cost controls decide what can scale.
4. AI-adjacent infrastructure can include communications and defense networks when autonomy and distributed compute become part of the innovation cycle.
5. The pattern across the week is that capital markets, regulation, and infrastructure constraints are starting to shape the next phase of AI adoption.

QUESTIONS TO BRING TO YOUR CLIENTS
1. Are we monitoring AI infrastructure broadly enough to include power, cooling, financing, and strategic connectivity rather than only the most visible platform companies?
2. Which companies in the portfolio benefit if enterprise AI spending shifts from pilots to governed production workflows?
3. What indicators would tell us that frontier technology IPOs are reopening the private-to-public liquidity window for innovation companies?

AI PRACTICE TIP OF THE WEEK
What to try: Ask an AI assistant to turn this week's infrastructure pattern into three client-friendly questions for a review meeting.
Why it helps: It converts research into a practical conversation without making recommendations or performance promises.
""".strip()


class WeeklyDigestRefinementTests(unittest.TestCase):
    def test_weekly_prompts_include_frontier_override_and_what_to_watch_next(self):
        system_prompt = (REPO_ROOT / "prompts/weekly/wholesaler_main_system_prompt.md").read_text(encoding="utf-8")
        user_prompt = (REPO_ROOT / "prompts/weekly/wholesaler_main_user_prompt.md").read_text(encoding="utf-8")

        for prompt in [system_prompt, user_prompt]:
            self.assertIn("FRONTIER TECHNOLOGY CAPITAL MARKETS WEEKLY OVERRIDE", prompt)
            self.assertIn("not a pure Gen AI story", prompt)
            self.assertIn("WHAT TO WATCH NEXT", prompt)

    def test_weekly_prompts_require_two_tier_scoring_and_arms_race_check(self):
        system_prompt = (REPO_ROOT / "prompts/weekly/wholesaler_main_system_prompt.md").read_text(encoding="utf-8")
        user_prompt = (REPO_ROOT / "prompts/weekly/wholesaler_main_user_prompt.md").read_text(encoding="utf-8")

        for prompt in [system_prompt, user_prompt]:
            self.assertIn("tier 1", prompt.lower())
            self.assertIn("tier 2", prompt.lower())
            self.assertIn("Weekly Impact Score", prompt)
            self.assertIn("arms-race", prompt.lower())
            self.assertIn("OpenAI, Meta, Microsoft, Google / Alphabet, Amazon / AWS, Anthropic, Nvidia, xAI, Oracle, and CoreWeave", prompt)
            self.assertIn("DEBUG_WEEKLY_SCORING", prompt)

    def test_weekly_runner_emits_frontier_override_metadata(self):
        runner = (REPO_ROOT / "run_weekly_pipeline.py").read_text(encoding="utf-8")

        self.assertIn("FRONTIER_CAPITAL_MARKETS_SCORE", runner)
        self.assertIn("FRONTIER_CAPITAL_MARKETS_OVERRIDE", runner)
        self.assertIn("FRONTIER CAPITAL MARKETS OVERRIDE", runner)

    def test_weekly_runner_emits_weekly_impact_metadata(self):
        runner = (REPO_ROOT / "run_weekly_pipeline.py").read_text(encoding="utf-8")

        self.assertIn("WEEKLY_IMPACT_SCORE", runner)
        self.assertIn("CANDIDATE_TIER: TIER 2 - WEEKLY OVERRIDE CANDIDATE", runner)
        self.assertIn("INTERNAL DEBUG WEEKLY SCORING TABLE", runner)

    def test_weekly_runner_emits_new_override_metadata_and_cli_flag(self):
        runner = (REPO_ROOT / "run_weekly_pipeline.py").read_text(encoding="utf-8")

        self.assertIn("weekly_override_candidates", runner)
        self.assertIn("MAJOR_EARNINGS_OVERRIDE", runner)
        self.assertIn("HEALTHCARE_FDA_OVERRIDE", runner)
        self.assertIn("--debug-weekly-scoring", runner)

    def test_major_earnings_override_detected(self):
        article = {
            "title": "Micron reports blowout earnings and raises guidance on AI memory demand",
            "summary": "The quarterly results showed stronger HBM and data center memory demand tied to AI server buildouts.",
            "advisor_relevance": "This earnings read-through broadens the AI semiconductor conversation beyond GPUs.",
            "companies": ["Micron"],
        }

        self.assertTrue(run_weekly_pipeline._is_major_earnings_override(article))
        self.assertGreaterEqual(run_weekly_pipeline.weekly_impact_score(article), 8.0)

    def test_healthcare_fda_override_detected(self):
        article = {
            "title": "FDA clears generative AI radiology workflow assistant for clinical use",
            "summary": "The approval covers medical imaging workflow support using a generative AI foundation model in hospitals.",
            "advisor_relevance": "This is a healthcare workflow adoption signal with regulatory relevance.",
            "companies": ["FDA"],
        }

        self.assertTrue(run_weekly_pipeline._is_healthcare_fda_override(article))
        self.assertGreaterEqual(run_weekly_pipeline.weekly_impact_score(article), 8.0)

    def test_thematic_weekly_receives_curated_event_context(self):
        captured = {}

        original_load = run_weekly_pipeline._load_weekly_prompt
        original_call = run_weekly_pipeline.call_chat_model
        original_build = run_weekly_pipeline._build_wholesaler_event_context
        try:
            def fake_load(name, **replacements):
                if name == "thematic_user":
                    captured["source_context"] = replacements["source_context"]
                return "PROMPT"

            run_weekly_pipeline._load_weekly_prompt = fake_load
            run_weekly_pipeline.call_chat_model = lambda *args, **kwargs: "THEMATIC OUTPUT"
            run_weekly_pipeline._build_wholesaler_event_context = lambda article_data: "CURATED EVENTS"

            output = run_weekly_pipeline.generate_thematic_weekly(
                client=None,
                source_context="PRIMARY SOURCE",
                article_data={"weekly_override_candidates": [{"title": "Micron earnings"}]},
                space_economy_theme_active=False,
            )

            self.assertEqual(output, "THEMATIC OUTPUT")
            self.assertIn("PRIMARY SOURCE", captured["source_context"])
            self.assertIn("CURATED EVENTS", captured["source_context"])
        finally:
            run_weekly_pipeline._load_weekly_prompt = original_load
            run_weekly_pipeline.call_chat_model = original_call
            run_weekly_pipeline._build_wholesaler_event_context = original_build

    def test_daily_digest_context_falls_back_to_archived_files(self):
        original_fetch = run_weekly_pipeline.fetch_daily_digests
        original_archive = run_weekly_pipeline.load_daily_digests_from_files
        try:
            run_weekly_pipeline.fetch_daily_digests = lambda *args, **kwargs: []
            run_weekly_pipeline.load_daily_digests_from_files = lambda week_start: [
                {"date": "2026-06-20", "content": "Archived Digest A"},
                {"date": "2026-06-21", "content": "Archived Digest B"},
            ]

            context = run_weekly_pipeline._format_daily_digest_context(date(2026, 6, 26))

            self.assertIn("DATE: 2026-06-20", context)
            self.assertIn("Archived Digest A", context)
            self.assertIn("DATE: 2026-06-21", context)
            self.assertIn("Archived Digest B", context)
        finally:
            run_weekly_pipeline.fetch_daily_digests = original_fetch
            run_weekly_pipeline.load_daily_digests_from_files = original_archive

    def test_weekly_archive_fallback_respects_signal_caps(self):
        original_engine = run_weekly_pipeline.get_engine
        original_archive = run_weekly_pipeline.load_weekly_articles_from_daily_snapshots
        original_frontier = run_weekly_pipeline.is_frontier_technology_capital_markets_event
        try:
            class _FakeResult:
                def __init__(self, rows):
                    self._rows = rows

                def mappings(self):
                    return self

                def all(self):
                    return list(self._rows)

            class _FakeConnection:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def execute(self, *args, **kwargs):
                    return _FakeResult([])

            class _FakeEngine:
                def connect(self):
                    return _FakeConnection()

            archived_articles = []
            for index in range(40):
                archived_articles.append(
                    {
                        "id": index + 1,
                        "title": f"High signal article {index}",
                        "url": f"https://example.com/high-{index}",
                        "published_at": f"2026-07-03T{index % 24:02d}:00:00",
                        "summary": "High signal summary",
                        "advisor_relevance": "High signal relevance",
                        "companies": [],
                        "ai_score": 9,
                    }
                )
            for index in range(40):
                archived_articles.append(
                    {
                        "id": 100 + index,
                        "title": f"Medium signal article {index}",
                        "url": f"https://example.com/medium-{index}",
                        "published_at": f"2026-07-02T{index % 24:02d}:00:00",
                        "summary": "Medium signal summary",
                        "advisor_relevance": "Medium signal relevance",
                        "companies": [],
                        "ai_score": 7,
                    }
                )

            run_weekly_pipeline.get_engine = lambda: _FakeEngine()
            run_weekly_pipeline.load_weekly_articles_from_daily_snapshots = lambda week_start: archived_articles
            run_weekly_pipeline.is_frontier_technology_capital_markets_event = lambda article: False

            article_data = run_weekly_pipeline.get_weekly_articles(date(2026, 7, 3))

            self.assertEqual(len(article_data["high_signal"]), run_weekly_pipeline.HIGH_SIGNAL_LIMIT)
            self.assertEqual(len(article_data["medium_signal"]), run_weekly_pipeline.MEDIUM_SIGNAL_LIMIT)
            self.assertEqual(
                len(article_data["articles"]),
                run_weekly_pipeline.HIGH_SIGNAL_LIMIT + run_weekly_pipeline.MEDIUM_SIGNAL_LIMIT,
            )
        finally:
            run_weekly_pipeline.get_engine = original_engine
            run_weekly_pipeline.load_weekly_articles_from_daily_snapshots = original_archive
            run_weekly_pipeline.is_frontier_technology_capital_markets_event = original_frontier

    def test_validator_accepts_weekly_spacex_ipo_synthesis(self):
        self.assertEqual(validate_weekly_digest_text(_valid_weekly_text()), [])

    def test_validator_requires_what_to_watch_next(self):
        text = _valid_weekly_text().replace(
            "WHAT TO WATCH NEXT",
            "WATCHLIST",
            1,
        )

        self.assertIn("WHAT TO WATCH NEXT section missing", validate_weekly_digest_text(text))

    def test_validator_flags_short_what_to_watch_next(self):
        text = _valid_weekly_text()
        text = text.replace(
            "4. Physical AI deployment evidence: Look past robotics funding headlines and monitor customer deployments, uptime, failure rates, safety approvals, and unit economics.\n5. Secure inference adoption: Watch whether privacy-preserving AI infrastructure becomes a standard requirement for enterprise and consumer platform deployment.\n",
            "",
        )

        self.assertIn("WHAT TO WATCH NEXT should include 4 to 6 monitorable indicators", validate_weekly_digest_text(text))

    def test_validator_flags_frontier_capital_markets_without_honest_framing(self):
        top_story = (
            "1. SpaceX's IPO became a major satellite communications and defense capital markets event. "
            "The offering matters because it connects autonomy, edge connectivity, strategic infrastructure, public-market risk appetite, and private-market liquidity."
        )
        issues = validate_weekly_digest_text(_valid_weekly_text(top_story=top_story))

        self.assertIn("Frontier technology capital markets discussion needs honest AI-adjacent framing", issues)


if __name__ == "__main__":
    unittest.main()
