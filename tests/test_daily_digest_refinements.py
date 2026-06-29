import unittest
from pathlib import Path
from types import SimpleNamespace
import types
from unittest.mock import MagicMock
from unittest.mock import patch

from app.generate_digest import (
    _is_healthcare_fda_override,
    _is_major_earnings_override,
    generate_daily_digest,
    frontier_technology_capital_markets_score,
    is_frontier_technology_capital_markets_event,
)
from scripts.validate_daily_digest_output import validate_daily_digest_html


REPO_ROOT = Path(__file__).resolve().parents[1]


def _daily_html(section_bullets):
    sections = [
        "TOP STORIES",
        "ENTERPRISE ADOPTION AND LABOR",
        "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS",
        "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS",
        "REGULATION, GOVERNANCE AND POLICY",
        "PHYSICAL AI AND ROBOTICS",
        "WHAT TO WATCH",
        "ADVISOR / WHOLESALER SOUNDBITES",
    ]
    parts = [
        "<h2>Beyond the Horizon: Daily Riffs from the Gen AI Songbook</h2>",
        "<p><strong>June 11, 2026</strong></p>",
        "<h3>TOP THEME OF THE DAY</h3>",
        (
            "<p>AI news today points to production deployment, infrastructure bottlenecks, "
            "and policy controls becoming one investment conversation. The useful signal is "
            "which companies can turn pilots into governed workflows while managing cost, "
            "power, and compliance constraints.</p>"
        ),
    ]
    for section in sections:
        parts.append(f"<h3>{section}</h3>")
        parts.append("<ul>")
        for bullet in section_bullets.get(section, []):
            parts.append(f"<li>{bullet}</li>")
        parts.append("</ul>")
    return "\n".join(parts)


class DailyDigestRefinementTests(unittest.TestCase):
    def test_daily_prompts_include_new_concentration_and_adoption_audits(self):
        system_prompt = (REPO_ROOT / "prompts/daily/daily_digest_system_prompt.md").read_text(encoding="utf-8")
        user_prompt = (REPO_ROOT / "prompts/daily/daily_digest_user_prompt.md").read_text(encoding="utf-8")

        for prompt in [system_prompt, user_prompt]:
            self.assertIn("more than three analytical bullets", prompt)
            self.assertIn("Enterprise Production Readiness", prompt)
            self.assertIn("Workflow Orchestration", prompt)
            self.assertIn("Platform Convergence", prompt)
            self.assertIn("4 to 6 most relevant categories", prompt)
            self.assertIn("local or state data center permitting", prompt.lower())
            self.assertIn("FRONTIER TECHNOLOGY CAPITAL MARKETS DAILY OVERRIDE", prompt)
            self.assertIn("not a pure Gen AI story", prompt)

    def test_spacex_ipo_style_article_triggers_frontier_capital_markets_override(self):
        article = {
            "title": "SpaceX weighs IPO as Starlink expands satellite communications network",
            "summary": (
                "The company is considering an initial public offering that could test public-market "
                "appetite for mega-cap private frontier technology. The story centers on space "
                "technology, satellite communications, defense connectivity, autonomy, edge "
                "connectivity, and private-market liquidity."
            ),
            "companies": "SpaceX, Starlink",
            "advisor_relevance": "",
            "ai_score": 0,
        }

        self.assertTrue(is_frontier_technology_capital_markets_event(article))
        self.assertGreaterEqual(frontier_technology_capital_markets_score(article), 80)

    def test_generic_non_frontier_ipo_does_not_trigger_override(self):
        article = {
            "title": "Restaurant chain files for IPO",
            "summary": "The company plans an initial public offering after opening new locations.",
            "companies": "Example Restaurants",
            "advisor_relevance": "",
            "ai_score": 0,
        }

        self.assertFalse(is_frontier_technology_capital_markets_event(article))
        self.assertEqual(frontier_technology_capital_markets_score(article), 0)

    def test_major_earnings_override_detected(self):
        article = {
            "title": "Micron reports blowout earnings and raises guidance on AI memory demand",
            "summary": "The quarterly results showed stronger HBM and data center memory demand tied to AI server buildouts.",
            "companies": "Micron",
            "advisor_relevance": "This earnings read-through broadens the AI semiconductor conversation beyond GPUs.",
            "ai_score": 0,
        }

        self.assertTrue(_is_major_earnings_override(article))

    def test_healthcare_fda_override_detected(self):
        article = {
            "title": "FDA clears generative AI radiology workflow assistant for clinical use",
            "summary": "The approval covers medical imaging workflow support using a generative AI foundation model in hospitals.",
            "companies": "FDA",
            "advisor_relevance": "This is a healthcare workflow adoption signal with regulatory relevance.",
            "ai_score": 0,
        }

        self.assertTrue(_is_healthcare_fda_override(article))

    def test_validator_accepts_clean_daily_digest_shape(self):
        html = _daily_html(
            {
                "TOP STORIES": [
                    "<strong>Reuters reported a cloud provider expanded governed AI deployments:</strong> The move matters because enterprise buyers are asking for security, identity, and cost controls before scaling. The read-through is to data platforms, governance software, and IT services. (Source: Reuters)",
                    "<strong>Bloomberg reported a chip supplier raised AI infrastructure guidance:</strong> The update matters because backlog is still tied to real capacity rather than broad AI enthusiasm. Portfolio teams should monitor networking, memory, and advanced packaging exposure. (Source: Bloomberg)",
                    "<strong>AP reported lawmakers advanced an AI procurement bill:</strong> The policy move matters because public-sector rules can shape enterprise governance standards. The implication is stronger demand for auditability and compliance tooling. (Source: AP)",
                ],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Microsoft added production controls to an agent platform:</strong> The launch matters because orchestration is moving from demos into governed workflow automation. Advisors can frame this as a platform convergence signal, not just another chatbot feature. (Source: Microsoft)",
                    "<strong>Gartner published a report on AI workflow redesign:</strong> The report matters because labor impact is shifting toward process change and quality control. The implication is to monitor services firms that can implement production workflows. (Source: Gartner)",
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [
                    "<strong>Financial Times reported a utility signed a data center power agreement:</strong> The agreement matters because compute growth is colliding with grid capacity. The read-through is to power equipment, cooling, networking, and utilities. (Source: Financial Times)",
                    "<strong>Data Center Dynamics reported a cooling supplier expanded capacity:</strong> The expansion matters because thermal constraints are becoming a deployment bottleneck. The implication is continued monitoring of cooling and electrical infrastructure suppliers. (Source: Data Center Dynamics)",
                ],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [
                    "<strong>Wall Street Journal reported an AI infrastructure financing package:</strong> The financing matters because capex is becoming a balance-sheet and project-finance story. The read-through extends to private credit, construction, power equipment, cooling, networking, and utilities. (Source: Wall Street Journal)",
                    "<strong>IDC published an enterprise AI spending forecast:</strong> The forecast matters because budgets are shifting toward production systems. Portfolio monitoring should separate durable data-platform demand from speculative application spending. (Source: IDC)",
                ],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>The White House released AI procurement guidance:</strong> The guidance matters because governance can become a commercial-access requirement. The implication is stronger demand for audit trails, privacy controls, and compliance software. (Source: White House)",
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>The Robot Report reported a warehouse automation deployment:</strong> The deployment matters because physical AI is moving from pilots into operational workflows. The read-through is to industrial automation, sensors, and logistics software. (Source: The Robot Report)",
                ],
                "WHAT TO WATCH": [
                    "<strong>Enterprise production controls:</strong> Watch whether new agent deployments include identity, observability, and cost controls. Those details separate workflow infrastructure from feature launches. (Source: Full article set)",
                    "<strong>Grid interconnection timelines:</strong> Watch whether power constraints delay data center deployments. The signal matters for utilities, power equipment, and cooling demand. (Source: Full article set)",
                    "<strong>Policy procurement standards:</strong> Watch whether government rules become templates for enterprise AI governance. That would support auditability and compliance vendors. (Source: Full article set)",
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>Production readiness is the new adoption test:</strong> The key question is whether AI can run inside governed enterprise workflows. That framing keeps the conversation grounded in business infrastructure. (Source: Full article set)",
                    "<strong>AI capex is becoming a financing story:</strong> Compute demand now reaches power, cooling, networking, and private credit. That broadens the investment discussion beyond model providers. (Source: Full article set)",
                    "<strong>Governance can be a growth gate:</strong> Companies that solve auditability and permissions may help AI move from pilots to scale. That is an enterprise readiness point advisors can use. (Source: Full article set)",
                    "<strong>Platform convergence matters:</strong> AI embedded in existing work surfaces may have more durable adoption than standalone tools. The monitoring question is who controls the workflow layer. (Source: Full article set)",
                    "<strong>Physical AI remains a deployment watch item:</strong> Robotics signals matter most when pilots become operating workflows. That keeps attention on industrial automation and logistics. (Source: Full article set)",
                ],
            }
        )

        self.assertEqual(validate_daily_digest_html(html), [])

    def test_generate_daily_digest_returns_best_effort_when_final_retry_is_empty(self):
        valid_article = {
            "title": "Data center permitting review expands in Ohio",
            "source": "Local News",
            "original_publisher": "Local News",
            "summary": "Local officials reviewed another AI data center permitting request tied to grid and zoning constraints.",
            "url": "https://example.com/story",
            "published_at": "2026-06-29T10:00:00",
            "companies": "",
            "advisor_relevance": "Infrastructure approvals can shape AI deployment timing.",
            "ai_score": 7,
            "is_space_economy_related": 0,
            "space_relevance": "",
            "space_ai_connection": "",
            "space_time_horizon": "",
            "space_investment_layer": "",
        }

        repetitive_html = _daily_html(
            {
                "TOP STORIES": [
                    "<strong>Local officials reviewed a data center permitting request:</strong> The local zoning process matters because permitting can delay AI infrastructure. The implication is to monitor grid infrastructure and utility planning. (Source: Local News)",
                    "<strong>Local officials reviewed a data center permitting request:</strong> The local zoning process matters because permitting can delay AI infrastructure. The implication is to monitor grid infrastructure and utility planning. (Source: Local News)",
                    "<strong>Local officials reviewed a data center permitting request:</strong> The local zoning process matters because permitting can delay AI infrastructure. The implication is to monitor grid infrastructure and utility planning. (Source: Local News)",
                ],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Workflow controls matter:</strong> Enterprises still need governed production systems. (Source: Gartner)"
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [
                    "<strong>Local officials reviewed a data center permitting request:</strong> The local zoning process matters because permitting can delay AI infrastructure. The implication is to monitor grid infrastructure and utility planning. (Source: Local News)"
                ],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [
                    "<strong>Capital intensity remains high:</strong> AI infrastructure still depends on financing and supplier capacity. (Source: Bloomberg)"
                ],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>State AI policy moved forward:</strong> Policy rules still shape adoption standards. (Source: AP)"
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>Warehouse robotics moved ahead:</strong> Automation is still entering production workflows. (Source: The Robot Report)"
                ],
                "WHAT TO WATCH": [
                    "<strong>Permitting concentration:</strong> Watch whether local approvals become a broader infrastructure bottleneck. (Source: Full article set)"
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>Infrastructure is local too:</strong> Permits and grid queues can shape compute capacity. (Source: Full article set)"
                ],
            }
        )

        responses = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=repetitive_html),
                        finish_reason="stop",
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=repetitive_html),
                        finish_reason="stop",
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=""),
                        finish_reason="length",
                    )
                ]
            ),
        ]

        class FakeClient:
            def __init__(self, queued):
                self._queued = list(queued)
                self.chat = SimpleNamespace(completions=self)

            def create(self, **kwargs):
                return self._queued.pop(0)

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [
            (
                valid_article["title"],
                valid_article["source"],
                valid_article["original_publisher"],
                valid_article["summary"],
                valid_article["url"],
                valid_article["published_at"],
                valid_article["companies"],
                valid_article["advisor_relevance"],
                valid_article["ai_score"],
                valid_article["is_space_economy_related"],
                valid_article["space_relevance"],
                valid_article["space_ai_connection"],
                valid_article["space_time_horizon"],
                valid_article["space_investment_layer"],
            )
        ]

        fake_openai = types.ModuleType("openai")
        fake_openai.APITimeoutError = type("APITimeoutError", (Exception,), {})
        fake_openai.OpenAI = lambda *args, **kwargs: FakeClient(responses)

        fake_sqlalchemy = types.ModuleType("sqlalchemy")
        fake_sqlalchemy.text = lambda value: value

        fake_branding = types.ModuleType("app.branding")
        fake_branding.DAILY_TITLE = "Beyond the Horizon: Daily Riffs from the Gen AI Songbook"

        fake_db = types.ModuleType("app.db")
        fake_db.get_engine = lambda: mock_engine

        fake_pipeline_window = types.ModuleType("app.pipeline_window")
        fake_pipeline_window.get_pipeline_window = lambda hours=24: (
            SimpleNamespace(isoformat=lambda: "2026-06-28T11:30:00"),
            SimpleNamespace(isoformat=lambda: "2026-06-29T11:30:00"),
        )

        fake_space = types.ModuleType("app.space_economy")
        fake_space.SPACE_ECONOMY_FILTER_PROMPT = ""
        fake_space.calculate_space_economy_theme_active = lambda *args, **kwargs: False
        fake_space.ensure_space_metadata = lambda article: article
        fake_space.format_space_metadata_lines = lambda article: []

        with patch.dict(
            "sys.modules",
            {
                "openai": fake_openai,
                "sqlalchemy": fake_sqlalchemy,
                "app.branding": fake_branding,
                "app.db": fake_db,
                "app.pipeline_window": fake_pipeline_window,
                "app.space_economy": fake_space,
            },
        ):
            result = generate_daily_digest(return_metadata=True)

        self.assertEqual(result["content"], repetitive_html)
        self.assertEqual(result["source_articles"][0]["title"], valid_article["title"])

    def test_validator_flags_local_data_center_permitting_repetition(self):
        repeated = "<strong>Local officials reviewed a data center permitting request:</strong> The local zoning process matters because permitting can delay AI infrastructure. The implication is to monitor grid infrastructure and utility planning. (Source: Local News)"
        html = _daily_html(
            {
                "TOP STORIES": [repeated, repeated, repeated],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Gartner published a workflow automation report:</strong> The report matters because enterprises need governed production systems. The implication is to monitor implementation partners. (Source: Gartner)"
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [repeated],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [
                    "<strong>Bloomberg reported an AI financing package:</strong> The financing matters because capital intensity is rising. The read-through is to private credit, construction, power equipment, cooling, networking, and utilities. (Source: Bloomberg)"
                ],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>AP reported a state AI bill advanced:</strong> The policy action matters because compliance rules shape adoption. The implication is demand for auditability tooling. (Source: AP)"
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>The Robot Report reported a robotics deployment:</strong> The deployment matters because automation is entering production workflows. The implication is to monitor industrial automation. (Source: The Robot Report)"
                ],
                "WHAT TO WATCH": [
                    "<strong>Permitting concentration:</strong> Watch whether local approvals become a broader infrastructure bottleneck. The issue matters most when it affects deployment timelines. (Source: Full article set)"
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>AI infrastructure is local too:</strong> Permits and grid queues can shape national compute capacity. That keeps the discussion tied to real bottlenecks. (Source: Full article set)"
                ],
            }
        )

        self.assertIn(
            "Too many bullets repeat local data-center permitting language",
            validate_daily_digest_html(html),
        )

    def test_validator_flags_repeated_long_read_through_lists(self):
        long_list = "<strong>Bloomberg reported a hyperscale financing package:</strong> The financing matters because AI capex is spreading across suppliers. The read-through extends to private credit, construction, electrical equipment, cooling, backup power, fiber, networking, and utilities. (Source: Bloomberg)"
        html = _daily_html(
            {
                "TOP STORIES": [long_list],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Microsoft launched governed agent controls:</strong> The launch matters because production readiness depends on permissions and observability. The implication is to monitor workflow orchestration platforms. (Source: Microsoft)"
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [long_list],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [long_list],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>The White House released AI guidance:</strong> The guidance matters because procurement rules affect enterprise controls. The implication is to monitor governance software. (Source: White House)"
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>The Robot Report reported a warehouse robotics rollout:</strong> The rollout matters because physical AI is entering production. The implication is to monitor industrial automation. (Source: The Robot Report)"
                ],
                "WHAT TO WATCH": [
                    "<strong>Capital intensity:</strong> Watch whether financing costs change hyperscale buildout plans. The signal matters for infrastructure suppliers. (Source: Full article set)"
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>Read-throughs should stay focused:</strong> The useful daily takeaway is the most relevant supplier group. That keeps advisor language concise. (Source: Full article set)"
                ],
            }
        )

        issues = validate_daily_digest_html(html)
        self.assertIn("Investment read-through list appears too long in one or more bullets", issues)
        self.assertIn("Repeated long investment read-through category list detected", issues)

    def test_validator_accepts_spacex_ipo_with_honest_ai_adjacent_framing(self):
        html = _daily_html(
            {
                "TOP STORIES": [
                    "<strong>SpaceX's IPO became a major frontier-technology capital markets signal:</strong> This is not a pure Gen AI story, but it matters for the broader innovation cycle because it tests public-market appetite for mega-cap private technology and connects to satellite communications, defense, autonomy, edge connectivity, and strategic infrastructure. The advisor implication is that AI-adjacent infrastructure may include the communications and defense networks that support autonomy and distributed compute. (Source: Bloomberg)",
                    "<strong>Reuters reported a cloud provider expanded governed AI deployments:</strong> The move matters because enterprise buyers are asking for security, identity, and cost controls before scaling. The read-through is to data platforms, governance software, and IT services. (Source: Reuters)",
                    "<strong>AP reported lawmakers advanced an AI procurement bill:</strong> The policy move matters because public-sector rules can shape enterprise governance standards. The implication is stronger demand for auditability and compliance tooling. (Source: AP)",
                ],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Microsoft added production controls to an agent platform:</strong> The launch matters because orchestration is moving from demos into governed workflow automation. Advisors can frame this as a platform convergence signal, not just another chatbot feature. (Source: Microsoft)"
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [
                    "<strong>Financial Times reported a utility signed a data center power agreement:</strong> The agreement matters because compute growth is colliding with grid capacity. The read-through is to power equipment, cooling, networking, and utilities. (Source: Financial Times)"
                ],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [
                    "<strong>IDC published an enterprise AI spending forecast:</strong> The forecast matters because budgets are shifting toward production systems. Portfolio monitoring should separate durable data-platform demand from speculative application spending. (Source: IDC)"
                ],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>The White House released AI procurement guidance:</strong> The guidance matters because governance can become a commercial-access requirement. The implication is stronger demand for audit trails, privacy controls, and compliance software. (Source: White House)"
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>The Robot Report reported a warehouse automation deployment:</strong> The deployment matters because physical AI is moving from pilots into operational workflows. The read-through is to industrial automation, sensors, and logistics software. (Source: The Robot Report)"
                ],
                "WHAT TO WATCH": [
                    "<strong>IPO market tone:</strong> Watch whether frontier technology listings reopen the private-to-public liquidity window. The signal matters for capital allocation across AI infrastructure and strategic infrastructure. (Source: Full article set)"
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>AI-adjacent infrastructure is broader than chips:</strong> Communications, defense networks, and edge connectivity can matter when autonomy and distributed compute scale. That keeps the innovation-cycle conversation wider but still disciplined. (Source: Full article set)"
                ],
            }
        )

        self.assertEqual(validate_daily_digest_html(html), [])

    def test_validator_flags_frontier_capital_markets_without_honest_framing(self):
        html = _daily_html(
            {
                "TOP STORIES": [
                    "<strong>SpaceX's IPO became a major satellite communications event:</strong> The deal matters because it connects space technology, defense, autonomy, and edge connectivity. The advisor implication is to monitor private-market liquidity and strategic infrastructure. (Source: Bloomberg)"
                ],
                "ENTERPRISE ADOPTION AND LABOR": [
                    "<strong>Microsoft added production controls to an agent platform:</strong> The launch matters because orchestration is moving from demos into governed workflow automation. Advisors can frame this as a platform convergence signal. (Source: Microsoft)"
                ],
                "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS": [
                    "<strong>Financial Times reported a utility signed a data center power agreement:</strong> The agreement matters because compute growth is colliding with grid capacity. The read-through is to power equipment, cooling, networking, and utilities. (Source: Financial Times)"
                ],
                "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS": [
                    "<strong>IDC published an enterprise AI spending forecast:</strong> The forecast matters because budgets are shifting toward production systems. Portfolio monitoring should separate durable data-platform demand from speculative application spending. (Source: IDC)"
                ],
                "REGULATION, GOVERNANCE AND POLICY": [
                    "<strong>The White House released AI procurement guidance:</strong> The guidance matters because governance can become a commercial-access requirement. The implication is stronger demand for audit trails and compliance software. (Source: White House)"
                ],
                "PHYSICAL AI AND ROBOTICS": [
                    "<strong>The Robot Report reported a warehouse automation deployment:</strong> The deployment matters because physical AI is moving from pilots into operational workflows. The read-through is to industrial automation. (Source: The Robot Report)"
                ],
                "WHAT TO WATCH": [
                    "<strong>IPO market tone:</strong> Watch whether strategic infrastructure listings reopen the private-to-public liquidity window. The signal matters for capital allocation. (Source: Full article set)"
                ],
                "ADVISOR / WHOLESALER SOUNDBITES": [
                    "<strong>Infrastructure breadth matters:</strong> Communications and defense networks can matter when autonomy scales. That keeps the innovation-cycle conversation wider. (Source: Full article set)"
                ],
            }
        )

        self.assertIn(
            "Frontier technology capital markets bullet needs honest AI-adjacent framing",
            validate_daily_digest_html(html),
        )


if __name__ == "__main__":
    unittest.main()
