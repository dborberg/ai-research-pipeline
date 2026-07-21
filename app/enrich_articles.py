import json
import os
import time
import datetime
import argparse
from dotenv import load_dotenv
from openai import APITimeoutError, OpenAI
from sqlalchemy import text

from app.db import get_engine, init_db
from app.pipeline_window import get_pipeline_window
from app.space_economy import classify_space_economy_article

load_dotenv()

try:
    from openai import APIConnectionError, InternalServerError, RateLimitError
except ImportError:
    APIConnectionError = InternalServerError = RateLimitError = None


MAX_API_ATTEMPTS = max(1, int(os.getenv("OPENAI_ENRICH_MAX_ATTEMPTS", "5")))
BASE_RETRY_DELAY_SECONDS = max(1.0, float(os.getenv("OPENAI_ENRICH_RETRY_BASE_SECONDS", "2")))


def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_db_engine():
    return get_engine()


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


def _is_retryable_openai_error(exc):
    retryable_types = tuple(
        error_type
        for error_type in (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
        if error_type is not None
    )
    if retryable_types and isinstance(exc, retryable_types):
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True

    message = str(exc).lower()
    return any(
        signal in message
        for signal in [
            "rate limit",
            "too many requests",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "connection error",
            "server error",
        ]
    )


def _retry_delay_seconds(attempt):
    return BASE_RETRY_DELAY_SECONDS * (2 ** max(0, attempt - 1))


def _create_enrichment_response(client, system_message, user_message):
    response_text = None

    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-5.5",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
            )

            response_text = response.choices[0].message.content.strip()

            try:
                return json.loads(response_text)
            except Exception:
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    try:
                        return json.loads(response_text[start:end+1])
                    except Exception:
                        pass

            if attempt < MAX_API_ATTEMPTS:
                time.sleep(1)
                continue
            return None

        except Exception as exc:
            if not _is_retryable_openai_error(exc) or attempt == MAX_API_ATTEMPTS:
                print(f"API error: {exc}")
                return None

            delay_seconds = _retry_delay_seconds(attempt)
            print(
                f"API error: {exc} | retrying in {delay_seconds:.0f}s "
                f"({attempt}/{MAX_API_ATTEMPTS})"
            )
            time.sleep(delay_seconds)

    return None


def _load_articles_to_enrich(limit, max_age_hours):
    window_start, window_end = get_pipeline_window(hours=max_age_hours)
    with get_db_engine().connect() as conn:
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
                   OR is_space_economy_related IS NULL
                   OR space_relevance IS NULL
                   OR space_ai_connection IS NULL
                   OR space_time_horizon IS NULL
                   OR space_investment_layer IS NULL
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


def main():
    init_db()
    args = parse_args()
    articles = _load_articles_to_enrich(args.limit, args.max_age_hours)
    client = get_openai_client()

    print(f"Articles to enrich: {len(articles)}")

    for article in articles:
        rowid = article["id"]
        title = article["title"]

        system_message = """You are a senior AI research analyst writing for mutual fund wholesalers.
Your job is to analyze AI-related news and produce structured insights usable in advisor conversations.
Keep language clear, factual, and consistent. Use only the information provided in the article context. If details are unclear, stay conservative and do not invent facts.

Score articles higher when they show investment-relevant AI developments in infrastructure buildout, power and physical bottlenecks, capital intensity and financing, enterprise AI adoption and monetization, second-derivative beneficiaries, labor redesign, regulation and governance, physical AI and robotics, market structure, named company relevance, or forward-looking AI adoption signals.

Forward-looking AI adoption signals include enterprise production readiness, workflow orchestration, platform convergence, agent capability or time-horizon expansion, professional amplification, and AI-mediated discovery evolution. Prioritize concrete real-world actions over generic commentary."""

        user_message = f"""{_build_article_context(article)}

Produce structured output with exactly these fields:

{{
  "summary": "2-3 sentence summary",
  "themes": ["3-5 key themes"],
  "companies": ["companies mentioned"],
  "advisor_relevance": "why this matters",
  "ai_score": number between 1 and 10
}}

AI_SCORE guidance:
9-10: concrete company, policy, financing, market, infrastructure, enterprise deployment, platform convergence, agent workflow, or robotics development with clear investment or advisor implications.
7-8: credible real-world AI development with useful read-throughs to adoption, capex, labor, governance, or suppliers.
5-6: relevant but narrower, earlier, or less directly investable.
1-4: generic commentary, weak sourcing, technical novelty without commercial implication, or low advisor usefulness.

Return ONLY valid JSON. No extra text.
"""

        parsed = _create_enrichment_response(client, system_message, user_message)

        if not parsed:
            print(f"❌ Failed: {title}")
            continue

        try:
            summary = parsed.get("summary")
            themes = parsed.get("themes") or []
            companies = parsed.get("companies") or []
            advisor_relevance = parsed.get("advisor_relevance")
            ai_score = parsed.get("ai_score")
            space_metadata = classify_space_economy_article(
                {
                    **article,
                    "summary": summary or article.get("summary") or "",
                    "themes": themes,
                    "companies": companies,
                    "advisor_relevance": advisor_relevance or "",
                }
            )

            if isinstance(themes, str):
                themes = [themes]
            if isinstance(companies, str):
                companies = [companies]

            try:
                ai_score = int(ai_score)
                if ai_score < 1 or ai_score > 10:
                    ai_score = None
            except Exception:
                ai_score = None

            with get_db_engine().begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE articles
                        SET summary = :summary,
                            themes = :themes,
                            companies = :companies,
                            advisor_relevance = :advisor_relevance,
                            ai_score = :ai_score,
                            is_space_economy_related = :is_space_economy_related,
                            space_relevance = :space_relevance,
                            space_ai_connection = :space_ai_connection,
                            space_time_horizon = :space_time_horizon,
                            space_investment_layer = :space_investment_layer
                        WHERE id = :article_id
                        """
                    ),
                    {
                        "summary": summary,
                        "themes": json.dumps(themes),
                        "companies": json.dumps(companies),
                        "advisor_relevance": advisor_relevance,
                        "ai_score": ai_score,
                        "is_space_economy_related": 1 if space_metadata["is_space_economy_related"] else 0,
                        "space_relevance": space_metadata["space_relevance"],
                        "space_ai_connection": space_metadata["space_ai_connection"],
                        "space_time_horizon": space_metadata["space_time_horizon"],
                        "space_investment_layer": space_metadata["space_investment_layer"],
                        "article_id": rowid,
                    },
                )

            print(f"✓ Enriched: {title[:60]}")

        except Exception as exc:
            print(f"❌ Error processing {title}: {exc}")

    timestamp = datetime.datetime.now().isoformat()
    os.makedirs("data", exist_ok=True)
    with open("data/.last_refresh", "w") as f:
        f.write(timestamp)

    print("Enrichment complete")
    print(f"Timestamp saved: {timestamp}")


if __name__ == "__main__":
    main()
