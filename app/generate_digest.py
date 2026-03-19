import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from openai import OpenAI

DB_PATH = "sqlite:///data/ai_research.db"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_recent_articles(limit=25):
    engine = create_engine(DB_PATH)

    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT title, source, url, published_at, ai_score
            FROM articles
            WHERE published_at IS NOT NULL
              AND published_at >= :cutoff
            ORDER BY published_at DESC
            LIMIT :limit
        """), {"cutoff": cutoff, "limit": limit})

        rows = result.fetchall()

    articles = []
    for row in rows:
        articles.append({
            "title": row[0],
            "source": row[1],
            "url": row[2],
            "published_at": row[3],
            "ai_score": row[4]
        })

    return articles


def format_articles_for_prompt(articles):
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. {a['title']} ({a['source']})\n{a['url']}"
        )
    return "\n\n".join(lines)


def generate_daily_digest():
    articles = get_recent_articles()

    today = datetime.utcnow().strftime("%B %d, %Y")

    # ✅ Always return title + date even if no articles
    if not articles:
        return f"""Daily Riffs from the Gen AI Songbook
{today}

No new articles found in the last 24 hours.
"""

    article_block = format_articles_for_prompt(articles)

    prompt = f"""
You are a senior AI research analyst creating a concise daily digest for financial advisors.

Use ONLY the articles below.

ARTICLES:
{article_block}


Produce output with EXACTLY these sections:

TOP 5 STORIES

Provide five numbered items.
Each item should be 2–3 sentences.
Include the source.


WHAT MATTERS FOR CLIENT PORTFOLIOS

Provide 3–5 insights linking AI developments to markets, sectors, or companies.


BEYOND THE MAG 7

Provide 2–3 non-megacap companies or themes worth watching.
Include why each matters.


RISKS TO WATCH

Provide 2–3 emerging risks or concerns.


Formatting rules:

- Clean spacing between sections
- No markdown
- No bullet symbols
- Write in clear, readable paragraphs
- Keep it concise and advisor-ready
- No repetition
"""

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": "You are a precise financial AI analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_completion_tokens=1200,
    )

    content = response.choices[0].message.content.strip()

    # ✅ Enforce title + date at top (clean + consistent)
    final_output = f"""Daily Riffs from the Gen AI Songbook
{today}

{content}
"""

    return final_output