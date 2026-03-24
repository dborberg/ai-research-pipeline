def generate_daily_digest():
    import os
    from datetime import datetime, timedelta
    from sqlalchemy import create_engine, text
    from openai import OpenAI

    DB_PATH = "sqlite:///data/ai_research.db"
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    def source_quality_hint(article):
        source = (article.get("source") or "").lower()
        if any(term in source for term in ["reuters", "financial times", "ft", "economist", "bloomberg", "wsj"]):
            return "business_financial"
        if any(term in source for term in ["government", "policy", "regulation"]):
            return "policy_regulatory"
        if any(term in source for term in ["eetimes", "semiconductor", "design news", "robot report", "ieee"]):
            return "industry_technical"
        if any(term in source for term in ["arxiv", "blog"]):
            return "research_blog"
        return "general_news"

    def get_recent_articles():
        engine = create_engine(DB_PATH)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT title, source, summary, url, published_at
                FROM articles
                WHERE published_at >= :cutoff
                ORDER BY published_at DESC
            """), {"cutoff": cutoff})

            rows = result.fetchall()

        articles = []
        for row in rows:
            title = row[0] or ""
            source = row[1] or ""
            summary = row[2] or ""
            url = row[3] or ""
            published_at = row[4] or ""

            # Skip empty/incomplete content per your rule
            if not title or not summary:
                continue

            articles.append({
                "title": title,
                "source": source,
                "summary": summary,
                "url": url,
                "published_at": published_at,
            })

        return articles

    articles = get_recent_articles()
    today = datetime.utcnow().strftime("%B %d, %Y")

    if not articles:
        return f"""Daily Riffs from the Gen AI Songbook
{today}

No relevant articles found in the last 24 hours.
"""
    article_block = "\n\n---\n\n".join(
        "\n".join(
            [
                f"TITLE: {article['title']}",
                f"SOURCE: {article['source']}",
                f"SOURCE_QUALITY_HINT: {source_quality_hint(article)}",
                f"BIG_STORY_HINT: {'YES' if is_big_story(article) else 'NO'}",
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

Prefer coverage over precision. It is better to include multiple distinct real-world developments than to repeat one dominant theme across sections.

If an article is marked BIG_STORY_HINT: YES, treat it as a high-priority candidate for TOP STORIES. If any BIG story exists in the dataset, at least one BIG story must appear in TOP STORIES.

When similar stories exist, prefer sources with SOURCE_QUALITY_HINT of business_financial, policy_regulatory, or industry_technical over research_blog, unless the research_blog source adds unique insight not available elsewhere.
"""

    user_prompt = f"""
CRITICAL INSTRUCTION: Your response must contain EXACTLY these 8 sections in EXACTLY this order. Do not combine, rename, or omit sections.

Output format:
<h2>Daily Riffs from the Gen AI Songbook</h2>
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
- Prefer real-world developments over technical research.
- If multiple articles are similar, keep the one with clearer business or market impact.
- Before writing "Nothing to report today." for any section, check whether relevant stories exist elsewhere in the input and include at least one meaningful item if possible.
- Keep bullets specific, event-driven, and concise.
- Each section should include multiple distinct topics rather than repeating one underlying narrative.
- Once a story appears in TOP STORIES, do not reuse that same underlying development in other sections.
- Ensure diversity across companies, sectors, geographies, and use cases.
- If several articles cover the same event, include only one and replace the others with different topics.
- Each section should re-scan the full dataset independently for relevant stories instead of relying on a single preselected subset.

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

ARTICLES:
{article_block}
"""

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ],
        temperature=0.2,
        max_completion_tokens=1800,
    )
    content = response.choices[0].message.content.strip()

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return content
