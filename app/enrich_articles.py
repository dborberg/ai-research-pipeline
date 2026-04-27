import json
import os
import time
import datetime
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import text

from app.db import get_engine, init_db
from app.pipeline_window import get_pipeline_window

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
init_db()
engine = get_engine()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--max-age-hours", type=int, default=36)
    return parser.parse_args()


def _parse_published_at(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _load_articles_to_enrich(limit, max_age_hours):
    window_start, window_end = get_pipeline_window(hours=max_age_hours)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    title,
                    source,
                    COALESCE(original_publisher, source) AS original_publisher,
                    summary,
                    raw_text,
                    cleaned_text,
                    published_at,
                    created_at
                FROM articles
                WHERE summary IS NULL
                   OR themes IS NULL
                   OR companies IS NULL
                   OR advisor_relevance IS NULL
                   OR ai_score IS NULL
                ORDER BY published_at DESC, created_at DESC
                """
            )
        ).fetchall()

    candidates = []
    for row in rows:
        rowid, title, source, original_publisher, summary, raw_text, cleaned_text, published_at, created_at = row
        published_dt = _parse_published_at(published_at)
        created_dt = _parse_published_at(created_at)
        reference_dt = published_dt or created_dt
        if reference_dt and (reference_dt < window_start or reference_dt > window_end):
            continue
        candidates.append(
            {
                "id": rowid,
                "title": title,
                "source": source,
                "original_publisher": original_publisher,
                "summary": summary or "",
                "raw_text": raw_text or "",
                "cleaned_text": cleaned_text or "",
            }
        )
        if len(candidates) >= limit:
            break

    return candidates


def _clip_text(value, limit):
    text_value = " ".join(str(value or "").split())
    if len(text_value) <= limit:
        return text_value
    return text_value[: limit - 3].rstrip() + "..."


def _build_article_context(article):
    rss_summary = _clip_text(article.get("summary"), 1200)
    article_text = article.get("cleaned_text") or article.get("raw_text") or article.get("summary") or ""
    article_text = _clip_text(article_text, 6000)

    context_parts = [
        f"Article title: {article.get('title') or ''}",
        f"Source: {article.get('original_publisher') or article.get('source') or ''}",
    ]

    if rss_summary:
        context_parts.append(f"RSS summary/excerpt: {rss_summary}")

    if article_text:
        context_parts.append(f"Article body/extracted text: {article_text}")

    return "\n\n".join(context_parts)


args = parse_args()
articles = _load_articles_to_enrich(args.limit, args.max_age_hours)

print(f"Articles to enrich: {len(articles)}")

for article in articles:
    rowid = article["id"]
    title = article["title"]

    system_message = """You are a senior AI research analyst writing for mutual fund wholesalers. 
Your job is to analyze AI-related news and produce structured insights usable in advisor conversations. 
Keep language clear, factual, and consistent. Use only the information provided in the article context. If details are unclear, stay conservative and do not invent facts."""

    user_message = f"""{_build_article_context(article)}

Produce structured output with exactly these fields:

{{
  "summary": "2-3 sentence summary",
  "themes": ["3-5 key themes"],
  "companies": ["companies mentioned"],
  "advisor_relevance": "why this matters",
  "ai_score": number between 1 and 10
}}

Return ONLY valid JSON. No extra text.
"""

    parsed = None
    response_text = None

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-5.5",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
            )

            response_text = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(response_text)
            except:
                # try to extract JSON block
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(response_text[start:end+1])
                    except:
                        pass

            if parsed:
                break

            time.sleep(1)

        except Exception as e:
            print(f"API error: {e}")
            time.sleep(1)

    if not parsed:
        print(f"❌ Failed: {title}")
        continue

    try:
        summary = parsed.get("summary")
        themes = parsed.get("themes") or []
        companies = parsed.get("companies") or []
        advisor_relevance = parsed.get("advisor_relevance")
        ai_score = parsed.get("ai_score")

        # Normalize lists
        if isinstance(themes, str):
            themes = [themes]
        if isinstance(companies, str):
            companies = [companies]

        # Validate score
        try:
            ai_score = int(ai_score)
            if ai_score < 1 or ai_score > 10:
                ai_score = None
        except:
            ai_score = None

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE articles
                    SET summary = :summary,
                        themes = :themes,
                        companies = :companies,
                        advisor_relevance = :advisor_relevance,
                        ai_score = :ai_score
                    WHERE id = :article_id
                    """
                ),
                {
                    "summary": summary,
                    "themes": json.dumps(themes),
                    "companies": json.dumps(companies),
                    "advisor_relevance": advisor_relevance,
                    "ai_score": ai_score,
                    "article_id": rowid,
                },
            )

        print(f"✓ Enriched: {title[:60]}")

    except Exception as e:
        print(f"❌ Error processing {title}: {e}")

# Save timestamp
timestamp = datetime.datetime.now().isoformat()
os.makedirs("data", exist_ok=True)
with open("data/.last_refresh", "w") as f:
    f.write(timestamp)

print("Enrichment complete")
print(f"Timestamp saved: {timestamp}")