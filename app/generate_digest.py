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
                f"PUBLISHED_AT: {article['published_at']}",
                f"SUMMARY: {article['summary']}",
                f"URL: {article['url']}",
            ]
        )
        for article in articles
    )

    system_prompt = """
You are an AI research analyst producing a daily briefing for financial advisors and mutual fund wholesalers. Distill generative AI news into clear, concise, professionally written summaries that a non-technical financial professional can understand and act on. Present both opportunities and risks where appropriate. Ensure emerging physical AI and robotics developments are included when strategically meaningful to industrial automation, logistics, defense, or public market exposure. If article content appears incomplete or missing, skip that article silently and summarize only what was provided. Do not use markdown formatting in your response. Use plain text only.

Responses must be in bullet point format only. Write concise sound bites suitable for sharing directly with sales teams and advisors. Avoid long paragraphs. Maintain a professional, forward-looking tone. Cite the source publication for each bullet point using parentheses.
"""

    user_prompt = f"""
CRITICAL INSTRUCTION: Your response must contain EXACTLY these 8 section headers in EXACTLY this order. Each header must appear on its own line in ALL CAPS. You are forbidden from combining sections, renaming sections, or omitting sections.

For each section: write 2–5 bullets when relevant material exists. If and only if there are zero relevant items, write exactly: “Nothing to report today.” Do not write that line if you included any bullets.

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
    return f"""Daily Riffs from the Gen AI Songbook
{today}

{content}
"""
