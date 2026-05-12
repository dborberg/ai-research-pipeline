CRITICAL INSTRUCTION: Your response must contain EXACTLY these 9 sections in EXACTLY this order after the title/date. Do not combine, rename, or omit sections.

Output format:
<h2>{{daily_title}}</h2>
<p><strong>{{today}}</strong></p>

<h3>TOP THEME OF THE DAY</h3>
<p>3 to 5 sentences identifying the dominant cross-story investment theme of the day and why it matters for internal CPM, advisor, and wholesaler conversations.</p>

Then for each remaining section:
<h3>SECTION NAME</h3>
<ul>
<li><strong>Lead phrase:</strong> Event + why it matters + investment/advisor implication. (Source: X)</li>
</ul>

Use only clean HTML with h2, h3, p, ul, li, and strong tags.
Do not use markdown.
Do not use tables.
Do not use arrows.
Do not use emojis.

Required section order:

TOP THEME OF THE DAY

TOP STORIES

ENTERPRISE ADOPTION AND LABOR

INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS

CAPITAL MARKETS AND INVESTMENT IMPLICATIONS

REGULATION, GOVERNANCE AND POLICY

PHYSICAL AI AND ROBOTICS

WHAT TO WATCH

ADVISOR / WHOLESALER SOUNDBITES

TOP THEME OF THE DAY:
Write one short paragraph. Synthesize the day's strongest cross-story theme. Do not list headlines. Explain what today's news says about the direction of the AI investment cycle. Useful themes include AI moving from a model story to an infrastructure story; power, grid, cooling, and permitting as AI bottlenecks; enterprise AI moving from copilots to governed agents; AI capex becoming a financing and balance-sheet story; governance becoming a commercial-access issue; second-derivative beneficiaries emerging beyond the largest platforms; labor impact shifting from replacement to workflow redesign; or physical AI moving from pilots toward deployment.

TOP STORIES:
Write the 3 to 5 most important developments and why they matter to financial services professionals. Each bullet must begin with a concrete event, company action, government action, financing event, policy move, deployment, or market signal.

ENTERPRISE ADOPTION AND LABOR:
Write about AI impact on enterprise adoption, agentic AI, copilots, white-collar work, productivity, hiring, workforce restructuring, workflow redesign, professional services, coding, governance, and compliance.

INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS:
Write about data centers, energy demand, grid investment, semiconductors, cooling, power equipment, batteries, networking, optical, fiber, nuclear, backup power, interconnection, permitting, zoning, and water constraints.

CAPITAL MARKETS AND INVESTMENT IMPLICATIONS:
Write about earnings, valuations, stock moves, financing, bond issuance, private credit, VC funding, IPOs, capex, opportunities beyond Mag 7, and second-derivative beneficiaries. Because this is internal use, named companies and ticker-level read-throughs are allowed when useful, but do not use buy/sell/hold language or make performance promises.

REGULATION, GOVERNANCE AND POLICY:
Write about US and global AI policy, export controls, labor policy responses, antitrust, public-sector AI rules, procurement, model safety, privacy, IP, AI hiring rules, and governance as a commercial-access issue.

PHYSICAL AI AND ROBOTICS:
Write about autonomous systems, humanoid robots, logistics automation, industrial automation, warehouse automation, eVTOL, drones, defense autonomy, lab automation, healthcare robotics, and embodied AI. If no meaningful commercial physical AI or robotics development exists, use this exact fallback:
<li><strong>No major commercial Physical AI or robotics developments surfaced:</strong> Continue monitoring robotics, autonomous systems, lab automation, industrial automation, and AI-enabled manufacturing for signs that pilots are moving into real deployment. (Source: Full article set)</li>

WHAT TO WATCH:
Write 3 to 5 leading indicators, risks, or emerging themes worth monitoring over the next 30 to 90 days. These should be monitorable signals, not just repeated story summaries.

ADVISOR / WHOLESALER SOUNDBITES:
Write 5 plain-English one-liners a financial advisor or wholesaler could use in an internal or client conversation. These should be memorable, non-promotional, and easy to say out loud.

Selection rules:
- Prefer a mix of sources and avoid using the same source more than 2 times per section when alternatives exist.
- Avoid leaning on the same publisher across the full briefing when credible alternatives exist elsewhere in the input.
- Prefer high-confidence and credible industry sources when available.
- Use lower-confidence sources cautiously and do not let weak sources drive TOP THEME OF THE DAY unless corroborated by stronger evidence elsewhere.
- Prefer real-world developments over technical research.
- If multiple articles are similar, keep the one with clearer business impact, market impact, source quality, and investment usefulness.
- Before writing "Nothing to report today." for any section, check whether relevant stories exist elsewhere in the input and include at least one meaningful item if possible.
- Keep bullets specific, event-driven, and concise.
- Every bullet should follow this logic: Event + why it matters + investment/advisor implication.
- Where relevant, include the read-through beyond the obvious company to suppliers, customers, infrastructure providers, software vendors, industrials, utilities, cybersecurity, compliance tools, or physical AI beneficiaries.
- Do not insert companies mechanically. Mention companies only when the input supports the connection or when they are clearly useful examples of a theme.
- Each section should include multiple distinct topics rather than repeating one underlying narrative.
- Once a story appears in TOP STORIES, do not reuse that same underlying development in other analytical sections.
- If a company, financing event, law, moratorium, policy action, market move, or named report is used in one analytical section, do not reuse that same event in another analytical section.
- WHAT TO WATCH and ADVISOR / WHOLESALER SOUNDBITES may synthesize broader themes from earlier sections, but they should not repeat the same named event as a standalone bullet.
- Ensure diversity across companies, sectors, geographies, and use cases.
- If several articles cover the same event, include only one and replace the others with different topics.
- Each section should re-scan the full dataset independently for relevant stories instead of relying on a single preselected subset.
- Do not mistake event deduplication for theme suppression. Repeated patterns across distinct events should still appear as synthesized takeaways when supported by the input.
- Preserve company-specific insight in wording that can roll up cleanly into a weekly internal report for the broader sales group.

Avoid explicit recommendation language:
- Do not use buy, sell, hold, overweight, underweight, price target, guaranteed winner, guaranteed loser, or performance-promise language unless directly quoted from a reputable source and clearly attributed.

Minimum coverage targets:
- TOP THEME OF THE DAY: 1 short paragraph
- TOP STORIES: 3 to 5 distinct developments
- ENTERPRISE ADOPTION AND LABOR: 3 to 4 distinct developments
- INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS: 3 to 5 distinct developments
- CAPITAL MARKETS AND INVESTMENT IMPLICATIONS: 3 to 5 distinct developments
- REGULATION, GOVERNANCE AND POLICY: 2 to 3 distinct developments
- PHYSICAL AI AND ROBOTICS: 1 to 3 distinct developments
- WHAT TO WATCH: 3 to 5 monitorable signals
- ADVISOR / WHOLESALER SOUNDBITES: 5 one-liners

Critical overrides:
- You must include at least one macro, policy, or capital markets signal every day.
- If none are initially selected, search the input again and promote the strongest available government policy, regulation, capital markets, valuation, funding, stock, earnings, financing, or macroeconomic AI story.
- This override is more important than ranking preferences.
- If any article is marked BIG_STORY_HINT: YES, at least one BIG story must appear in TOP STORIES.
- If any article references data centers, power, grid, energy, semiconductors, fabs, networking, optical, fiber, cooling, thermal, nuclear, batteries, backup power, or interconnection, at least one such story must appear in INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS.
- If any article includes legislation, named policymakers, government action, regulatory proposals, infrastructure restrictions, export controls, antitrust, labor policy, government procurement, or AI safety rules, include it in either TOP STORIES or REGULATION, GOVERNANCE AND POLICY.
- If the input contains any material related to robotics, physical AI, humanoid systems, warehouse automation, autonomous systems, industrial AI, lab automation, eVTOL, drones, defense autonomy, or AI-enabled manufacturing, include at least one substantive bullet under PHYSICAL AI AND ROBOTICS.

Fill rule:
- If a section looks thin, search again for secondary but still relevant stories before using "Nothing to report today."
- Avoid using "Nothing to report today." unless absolutely no relevant content exists after a second pass and the Physical AI fallback rule is not applicable.

THEME SIGNALS FROM THE FULL, PRE-DEDUPED ARTICLE SET:
{{theme_signal_block}}

ARTICLES:
{{article_block}}
