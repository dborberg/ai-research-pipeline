import unittest
from pathlib import Path

from scripts.validate_weekly_digest_output import validate_weekly_digest_text


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_weekly_runner_emits_frontier_override_metadata(self):
        runner = (REPO_ROOT / "run_weekly_pipeline.py").read_text(encoding="utf-8")

        self.assertIn("FRONTIER_CAPITAL_MARKETS_SCORE", runner)
        self.assertIn("FRONTIER_CAPITAL_MARKETS_OVERRIDE", runner)
        self.assertIn("FRONTIER CAPITAL MARKETS OVERRIDE", runner)

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
