def generate_daily_digest(report_date=None):
    import json
    import os
    import re
    from collections import Counter
    from datetime import datetime, timedelta
    from html import unescape
    from zoneinfo import ZoneInfo
    from sqlalchemy import text
    from openai import OpenAI

    from app.branding import DAILY_TITLE
    from app.db import get_engine
    from app.pipeline_window import get_pipeline_window

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    _CENTRAL_TZ = ZoneInfo("America/Chicago")

    # -----------------------------
    # GET ARTICLES
    # -----------------------------
    def is_big_story(article):
        text = f"{article.get('title') or ''} {article.get('summary') or ''}".lower()
        return any(term in text for term in [
            "nvidia", "microsoft", "amazon", "google", "tesla", "apple", "openai", "tsmc", "asml",
            "government", "policy", "regulation", "white house", "lawmakers",
            "upgrade", "earnings", "index", "investment", "capex", "valuation", "funding",
            "data center", "power", "grid", "fab", "fabs", "campus", "semiconductor",
        ])

    def parse_companies(raw_companies):
        if not raw_companies:
            return []
        if isinstance(raw_companies, list):
            return [str(item).strip() for item in raw_companies if str(item).strip()]
        try:
            parsed = json.loads(raw_companies)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in str(raw_companies).split(",") if part.strip()]

    def has_policy_priority(article):
        text = f"{article.get('title') or ''} {article.get('summary') or ''} {article.get('advisor_relevance') or ''}".lower()
        return any(term in text for term in [
            "white house", "congress", "senate", "house of representatives", "lawmakers", "lawmaker",
            "regulator", "regulators", "regulation", "regulatory", "rulemaking", "antitrust",
            "export control", "export controls", "restriction", "restrictions", "ban", "tariff",
            "commission", "eu", "european union", "european commission", "ftc", "doj", "fcc",
            "legislation", "bill", "policy proposal", "executive order", "compliance",
            "sanders", "ocasio-cortez", "aoc", "senator", "representative",
        ])

    def has_named_event_anchor(article):
        if parse_companies(article.get("companies")):
            return True
        title = article.get("title") or ""
        return bool(re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", title))

    def article_priority_score(article):
        score = float(article.get("ai_score") or 0)

        if has_policy_priority(article):
            score += 40
        if is_big_story(article):
            score += 20
        if has_named_event_anchor(article):
            score += 10

        source_hint = source_quality_hint(article)
        if source_hint == "policy_regulatory":
            score += 10
        elif source_hint == "business_financial":
            score += 8
        elif source_hint == "industry_technical":
            score += 4
        elif source_hint == "research_blog":
            score -= 3

        if parse_companies(article.get("companies")):
            score += min(len(parse_companies(article.get("companies"))), 3)

        return score

    def source_quality_hint(article):
        source = (article.get("original_publisher") or article.get("source") or "").lower()
        if any(term in source for term in ["reuters", "financial times", "ft", "economist", "bloomberg", "wsj"]):
            return "business_financial"
        if any(term in source for term in ["government", "policy", "regulation"]):
            return "policy_regulatory"
        if any(term in source for term in ["eetimes", "semiconductor", "design news", "robot report", "ieee"]):
            return "industry_technical"
        if any(term in source for term in ["arxiv", "blog"]):
            return "research_blog"
        return "general_news"

    def extract_theme_tags(article):
        text = " ".join(
            [
                article.get("title") or "",
                article.get("summary") or "",
                article.get("advisor_relevance") or "",
            ]
        ).lower()
        theme_rules = {
            "infrastructure_and_power": [
                "data center", "datacenter", "power", "grid", "electricity", "utility", "utilities",
                "cooling", "thermal", "nuclear", "land", "water", "semiconductor", "chip", "networking",
                "optical", "fab", "fabs",
            ],
            "enterprise_and_labor": [
                "hiring", "layoff", "layoffs", "job", "jobs", "workforce", "productivity", "automation",
                "employee", "employees", "coding", "developer", "software development", "copilot",
            ],
            "capital_markets_and_investment": [
                "earnings", "revenue", "valuation", "funding", "raised", "investment", "investor",
                "capital", "stock", "shares", "private equity", "venture", "vc", "lease",
            ],
            "regulation_and_policy": [
                "regulation", "regulatory", "policy", "lawmakers", "congress", "senate", "government",
                "public feedback", "moratorium", "antitrust", "export control", "compliance", "bill",
            ],
            "physical_ai_and_robotics": [
                "robot", "robotics", "autonomous", "autonomy", "warehouse automation", "drone", "aviation",
                "manufacturing", "factory", "humanoid", "inspection", "logistics",
            ],
        }

        tags = []
        for theme_name, terms in theme_rules.items():
            if any(term in text for term in terms):
                tags.append(theme_name)
        return tags

    def event_anchor(article):
        companies = [company.lower() for company in parse_companies(article.get("companies"))]
        title = (article.get("title") or "").lower()
        normalized_title = re.sub(r"[^a-z0-9\s]", " ", title)
        stopwords = {
            "the", "and", "for", "with", "from", "into", "after", "amid", "over", "under", "that",
            "this", "will", "would", "could", "about", "their", "they", "says", "said", "report",
            "reported", "announced", "launches", "launch", "launching", "new", "its", "are", "now",
            "more", "than", "into", "using", "use", "shows",
        }
        title_tokens = [
            token for token in normalized_title.split()
            if len(token) > 2 and token not in stopwords and not token.isdigit()
        ]
        theme_tags = extract_theme_tags(article)

        if companies:
            return "company|" + "|".join(companies[:2] + theme_tags[:2])
        if title_tokens:
            return "title|" + "|".join(title_tokens[:6] + theme_tags[:2])
        return "fallback|" + (article.get("url") or article.get("published_at") or "")

    def deduplicate_articles_by_event(articles):
        grouped_articles = {}
        for article in articles:
            anchor = event_anchor(article)
            incumbent = grouped_articles.get(anchor)
            if incumbent is None or article_priority_score(article) > article_priority_score(incumbent):
                grouped_articles[anchor] = article

        deduped_articles = list(grouped_articles.values())
        deduped_articles.sort(
            key=lambda article: (
                has_policy_priority(article),
                is_big_story(article),
                has_named_event_anchor(article),
                article_priority_score(article),
                article.get("published_at") or "",
            ),
            reverse=True,
        )
        return deduped_articles

    def build_theme_signal_block(all_articles):
        theme_labels = {
            "infrastructure_and_power": "INFRASTRUCTURE AND POWER",
            "enterprise_and_labor": "ENTERPRISE AND LABOR",
            "capital_markets_and_investment": "CAPITAL MARKETS AND INVESTMENT",
            "regulation_and_policy": "REGULATION AND POLICY",
            "physical_ai_and_robotics": "PHYSICAL AI AND ROBOTICS",
        }
        theme_examples = {theme_name: [] for theme_name in theme_labels}

        for article in all_articles:
            companies = parse_companies(article.get("companies"))
            example_label = companies[0] if companies else (article.get("title") or "").split(":")[0].strip()
            for theme_name in extract_theme_tags(article):
                if example_label and example_label not in theme_examples[theme_name]:
                    theme_examples[theme_name].append(example_label)

        theme_counts = Counter(
            theme_name
            for article in all_articles
            for theme_name in extract_theme_tags(article)
        )

        lines = []
        for theme_name, count in theme_counts.most_common():
            examples = ", ".join(theme_examples[theme_name][:4])
            lines.append(
                f"THEME_SIGNAL: {theme_labels[theme_name]} | corroborating_articles={count} | representative_examples={examples}"
            )

        if not lines:
            return ""
        return "\n".join(lines)

    def get_recent_articles():
        engine = get_engine()
        window_start, window_end = get_pipeline_window(hours=24)

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT title, source, COALESCE(original_publisher, source) AS original_publisher, summary, url, published_at, companies, advisor_relevance, ai_score
                FROM articles
                WHERE published_at >= :window_start
                  AND published_at <= :window_end
                ORDER BY published_at DESC
            """), {"window_start": window_start.isoformat(), "window_end": window_end.isoformat()})

            rows = result.fetchall()

        articles = []
        for row in rows:
            title = row[0] or ""
            source = row[1] or ""
            original_publisher = row[2] or source
            summary = row[3] or ""
            url = row[4] or ""
            published_at = row[5] or ""
            companies = row[6] or ""
            advisor_relevance = row[7] or ""
            ai_score = row[8]

            # Skip empty/incomplete content per your rule
            if not title or not summary:
                continue

            articles.append({
                "title": title,
                "source": source,
                "original_publisher": original_publisher,
                "summary": summary,
                "url": url,
                "published_at": published_at,
                "companies": companies,
                "advisor_relevance": advisor_relevance,
                "ai_score": ai_score,
            })

        articles.sort(
            key=lambda article: (
                has_policy_priority(article),
                is_big_story(article),
                has_named_event_anchor(article),
                article_priority_score(article),
                article.get("published_at") or "",
            ),
            reverse=True,
        )

        return articles

    def _normalize_text(value):
        text_value = unescape(re.sub(r"<[^>]+>", " ", value or ""))
        return " ".join(text_value.lower().split())

    def _extract_digest_bullets(content):
        sections = []
        for section_name, section_body in re.findall(r"<h3>(.*?)</h3>\s*<ul>(.*?)</ul>", content or "", flags=re.DOTALL | re.IGNORECASE):
            for item in re.findall(r"<li>(.*?)</li>", section_body, flags=re.DOTALL | re.IGNORECASE):
                lead_match = re.search(r"<strong>(.*?)</strong>", item, flags=re.DOTALL | re.IGNORECASE)
                source_match = re.search(r"\(Source:\s*([^\)]+)\)", item, flags=re.DOTALL | re.IGNORECASE)
                sections.append(
                    {
                        "section": unescape(section_name.strip()),
                        "lead": unescape((lead_match.group(1) if lead_match else item).strip()),
                        "source": unescape((source_match.group(1) if source_match else "").strip()),
                        "text": _normalize_text(item),
                    }
                )
        return sections

    def _find_diversity_issues(content, available_publishers):
        expected_sections = [
            "TOP STORIES",
            "ENTERPRISE AND LABOR",
            "INFRASTRUCTURE AND POWER",
            "CAPITAL MARKETS AND INVESTMENT",
            "REGULATION AND POLICY",
            "PHYSICAL AI AND ROBOTICS",
            "WHAT TO WATCH",
            "ADVISOR SOUNDBITES",
        ]
        issues = []
        found_sections = re.findall(r"<h3>(.*?)</h3>", content or "", flags=re.IGNORECASE)
        normalized_found_sections = [unescape(section).strip().upper() for section in found_sections]
        missing_sections = [section for section in expected_sections if section not in normalized_found_sections]
        if missing_sections:
            issues.append(f"Missing required sections: {', '.join(missing_sections)}")

        bullets = _extract_digest_bullets(content)
        lead_counts = Counter(_normalize_text(bullet["lead"]) for bullet in bullets if bullet["lead"])
        repeated_leads = [lead for lead, count in lead_counts.items() if lead and count > 1]
        if repeated_leads:
            issues.append("Repeated lead phrases suggest the same development is being reused across sections")

        publisher_counts = Counter(bullet["source"] for bullet in bullets if bullet["source"])
        unique_publishers = len({publisher for publisher in publisher_counts if publisher})
        dominant_publishers = [
            publisher for publisher, count in publisher_counts.items()
            if count >= 5 and unique_publishers >= 4 and len(available_publishers) >= 4
        ]
        if dominant_publishers:
            issues.append(
                "Publisher concentration is still too high: " + ", ".join(
                    f"{publisher} ({publisher_counts[publisher]})" for publisher in dominant_publishers
                )
            )

        section_story_map = {}
        for bullet in bullets:
            normalized_lead = _normalize_text(bullet["lead"])
            if not normalized_lead:
                continue
            section_story_map.setdefault(normalized_lead, set()).add(bullet["section"])
        cross_section_repeats = [lead for lead, sections in section_story_map.items() if len(sections) > 1]
        if cross_section_repeats:
            issues.append("The same underlying development appears in multiple sections")

        return issues

    all_articles = get_recent_articles()
    articles = deduplicate_articles_by_event(all_articles)
    if report_date is None:
        report_date = datetime.now(_CENTRAL_TZ).date()
    today = report_date.strftime("%B %d, %Y")
    available_publishers = {
        article.get("original_publisher") or article.get("source")
        for article in all_articles
        if article.get("original_publisher") or article.get("source")
    }
    theme_signal_block = build_theme_signal_block(all_articles)

    if not all_articles:
        return f"""{DAILY_TITLE}
{today}

No relevant articles found in the last 24 hours.
"""
    article_block = "\n\n---\n\n".join(
        "\n".join(
            [
                f"TITLE: {article['title']}",
                f"SOURCE: {article.get('original_publisher') or article['source']}",
                f"FEED_SOURCE: {article['source']}",
                f"SOURCE_QUALITY_HINT: {source_quality_hint(article)}",
                f"BIG_STORY_HINT: {'YES' if is_big_story(article) else 'NO'}",
                f"POLICY_PRIORITY_HINT: {'YES' if has_policy_priority(article) else 'NO'}",
                f"EVENT_ANCHOR_HINT: {'YES' if has_named_event_anchor(article) else 'NO'}",
                f"COMPANIES_MENTIONED: {', '.join(parse_companies(article.get('companies')))}",
                f"AI_SCORE: {article.get('ai_score') if article.get('ai_score') is not None else ''}",
                f"ADVISOR_RELEVANCE: {article.get('advisor_relevance') or ''}",
                f"PUBLISHED_AT: {article['published_at']}",
                f"SUMMARY: {article['summary']}",
                f"URL: {article['url']}",
            ]
        )
        for article in articles
    )

    system_prompt = """
You are an AI research analyst producing a daily briefing for financial advisors and mutual fund wholesalers. Distill generative AI news into clear, concise, professionally written summaries that a non-technical financial professional can understand and act on. Present both opportunities and risks where appropriate. Ensure emerging physical AI and robotics developments are included when strategically meaningful to industrial automation, logistics, defense, or public market exposure. If article content appears incomplete or missing, skip that article silently and summarize only what was provided.

Return clean HTML only. Do not use markdown. Use email-friendly spacing and structure.

Prioritize diversity across these domains:
- infrastructure and power
- enterprise and labor
- capital markets and investment
- regulation and policy
- physical AI and robotics

Do not allow one source, one publication, or one type of content to dominate the output. Prefer real-world developments such as company announcements, policy changes, infrastructure projects, enterprise deployments, capital allocation, and robotics deployments over technical research. Use technical or research sources only when they add unique insight or when no stronger real-world coverage exists for that section.

If multiple articles say similar things, choose the one with broader market relevance and clearer real-world impact. If the input is dominated by arXiv, EE Times, or other niche technical sources, actively rebalance toward business news, policy coverage, capital markets, and major company developments when those are present.

Treat SOURCE as the original publisher when available. FEED_SOURCE may be an aggregator feed and should not be treated as true source diversity.

Prefer coverage over precision. It is better to include multiple distinct real-world developments than to repeat one dominant theme across sections.

The article set may already be deduplicated at the event level before it reaches you. Treat that as a reduction of duplicate evidence, not a signal to ignore broader thematic patterns.

If multiple distinct events point to the same higher-order theme, preserve that theme explicitly in WHAT TO WATCH and ADVISOR SOUNDBITES even when duplicate event articles have been removed.

If an article is marked BIG_STORY_HINT: YES, treat it as a high-priority candidate for TOP STORIES. If any BIG story exists in the dataset, at least one BIG story must appear in TOP STORIES.

When similar stories exist, prefer sources with SOURCE_QUALITY_HINT of business_financial, policy_regulatory, or industry_technical over research_blog, unless the research_blog source adds unique insight not available elsewhere.

ADDITIONAL SELECTION AND WRITING RULES (CRITICAL UPGRADE)

1. EVENT-FIRST RULE (MANDATORY)
- Every bullet must start with a specific event.
- Prefer named companies, named government actions, named legislation or policy proposals, and named investments, funding rounds, or market moves.
- Do not start bullets with abstract framing such as "AI infrastructure is...", "AI adoption is...", or "Utilities are becoming...".
- Instead, anchor bullets to concrete developments such as "Meta announced...", "Arm launched...", or "Lawmakers introduced...".

2. POLICY / MACRO PRIORITY RULE
- If any article includes legislation, named policymakers, government action, regulatory proposals, or infrastructure restrictions, it must be included in either TOP STORIES or REGULATION AND POLICY.
- This rule overrides normal selection preferences.

3. COMPANY SPECIFICITY RULE
- Each section should include at least 1 to 2 named companies when available.
- Avoid fully abstract summaries when a company, institution, or policymaker can be named.

4. ANTI-ABSTRACTION RULE
- Before finalizing output, check whether a bullet can be rewritten to include a company, policy, or real-world action.
- If it can, rewrite it to include that specificity.

5. PRIORITIZATION SHIFT
- Prefer real events over general themes.
- Even if a theme is strong, choose the article that anchors it to a real development.

EXPECTED RESULT
- Policy events such as named lawmaker or regulatory actions are never missed.
- Output includes more named companies.
- Output uses less generic language.
- Output keeps the current structure but increases specificity.

MANDATORY INTERNAL WORKFLOW
- Before writing, silently identify the strongest 12 to 18 candidate developments from the full dataset.
- Group together articles covering the same underlying event, company announcement, policy action, paper, or deployment.
- For each group, keep only the best candidate based on real-world relevance, source quality, and specificity.
- Build the final briefing from those deduplicated event groups rather than selecting bullets one article at a time.

MANDATORY FINAL AUDIT
- Before returning the final HTML, silently check whether one publisher, one event, or one topic is overrepresented.
- If the same underlying event appears in multiple sections, keep the strongest placement and replace the rest with different developments.
- If one publisher appears repeatedly and credible alternatives exist in the input, swap in the alternatives.
- Prefer breadth across publishers, sectors, and event types over repeated emphasis on one technically strong but narrow source.
"""

    user_prompt = f"""
CRITICAL INSTRUCTION: Your response must contain EXACTLY these 8 sections in EXACTLY this order. Do not combine, rename, or omit sections.

Output format:
<h2>{DAILY_TITLE}</h2>
<p><strong>{today}</strong></p>

Then for each section:
<h3>SECTION NAME</h3>
<ul>
<li><strong>Lead phrase:</strong> Explanation (Source: X)</li>
</ul>

Use only clean HTML with h2, h3, p, ul, li, and strong tags.
Do not use markdown.
Do not use arrows.

If the input contains any material related to robotics, physical AI, humanoid systems, warehouse automation, autonomous systems, or industrial AI, you MUST include at least one substantive bullet under PHYSICAL AI AND ROBOTICS summarizing the most strategically meaningful development for investors.

TOP STORIES

ENTERPRISE AND LABOR

INFRASTRUCTURE AND POWER

CAPITAL MARKETS AND INVESTMENT

REGULATION AND POLICY

PHYSICAL AI AND ROBOTICS

WHAT TO WATCH

ADVISOR SOUNDBITES

Under TOP STORIES write the 2-3 most important developments and why they matter to financial services professionals.

Under ENTERPRISE AND LABOR write about AI impact on white-collar work, productivity, hiring, and workforce restructuring.

Under INFRASTRUCTURE AND POWER write about data centers, energy demand, grid investment, semiconductors, cooling, and nuclear.

Under CAPITAL MARKETS AND INVESTMENT write about earnings, valuations, private credit, VC funding, and opportunities beyond Mag 7.

Under REGULATION AND POLICY write about US and global AI policy, export controls, labor policy responses, and antitrust.

Under PHYSICAL AI AND ROBOTICS write about autonomous systems, humanoid robots, and logistics automation.

Under WHAT TO WATCH write 3-5 leading indicators or emerging themes worth monitoring over the next 30-90 days.

Under ADVISOR SOUNDBITES write 5 plain English one-liners a financial advisor could say verbatim in a client meeting today.

Selection rules:
- Prefer a mix of sources and avoid using the same source more than 2 times per section when alternatives exist.
- Avoid leaning on the same publisher across the full briefing when credible alternatives exist elsewhere in the input.
- Prefer real-world developments over technical research.
- If multiple articles are similar, keep the one with clearer business or market impact.
- Before writing "Nothing to report today." for any section, check whether relevant stories exist elsewhere in the input and include at least one meaningful item if possible.
- Keep bullets specific, event-driven, and concise.
- Each section should include multiple distinct topics rather than repeating one underlying narrative.
- Once a story appears in TOP STORIES, do not reuse that same underlying development in other sections.
- Ensure diversity across companies, sectors, geographies, and use cases.
- If several articles cover the same event, include only one and replace the others with different topics.
- Each section should re-scan the full dataset independently for relevant stories instead of relying on a single preselected subset.
- Do not mistake event deduplication for theme suppression. Repeated patterns across distinct events should still appear as synthesized takeaways when supported by the input.

Thought process instruction:
- Silently do a first pass for event grouping and publisher diversity, then a second pass for section assignment, and only then write the final HTML.

Minimum coverage targets:
- TOP STORIES: 3-5 distinct developments
- ENTERPRISE AND LABOR: 3-4 distinct developments
- INFRASTRUCTURE AND POWER: 3-5 distinct developments
- CAPITAL MARKETS AND INVESTMENT: 3-5 distinct developments
- REGULATION AND POLICY: 2-3 distinct developments
- PHYSICAL AI AND ROBOTICS: 1-3 distinct developments

Critical override:
- You must include at least one macro, policy, or capital markets signal every day.
- If none are initially selected, search the input again and promote the strongest available government policy, regulation, capital markets, valuation, funding, stock, or macroeconomic AI story.
- This override is more important than ranking preferences.
- If any article is marked BIG_STORY_HINT: YES, at least one BIG story must appear in TOP STORIES.
- If any article references data centers, power, grid, energy, semiconductors, fabs, networking, optical, cooling, or thermal, at least one such story must appear in INFRASTRUCTURE AND POWER.

Fill rule:
- If a section looks thin, search again for secondary but still relevant stories before using "Nothing to report today."
- Avoid using "Nothing to report today." unless absolutely no relevant content exists after a second pass.

THEME SIGNALS FROM THE FULL, PRE-DEDUPED ARTICLE SET:
{theme_signal_block}

ARTICLES:
{article_block}
"""

    content = ""
    issues = []
    extra_feedback = ""
    for attempt in range(3):
        request_prompt = user_prompt.strip()
        if extra_feedback:
            request_prompt = f"{request_prompt}\n\nREVISION FEEDBACK:\n{extra_feedback}"

        response = client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": request_prompt}
            ],
            max_completion_tokens=4000,
        )
        choice = response.choices[0]
        content = (choice.message.content or "").strip()

        if not content:
            raise ValueError(
                f"LLM returned empty digest content "
                f"(finish_reason={choice.finish_reason})"
            )

        issues = _find_diversity_issues(content, available_publishers)
        if not issues:
            break

        extra_feedback = (
            "The previous draft did not satisfy diversity requirements. "
            "Rewrite from the same article set and fix these issues:\n- "
            + "\n- ".join(issues)
            + "\nDo not explain the fixes. Return only the corrected HTML."
        )

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return content
