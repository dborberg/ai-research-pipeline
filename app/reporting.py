from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.db import fetch_daily_digests, fetch_top_articles, fetch_weekly_digests

MODEL_NAME = "gpt-5.4"
WEEKLY_WHOLESALER_TEMPERATURE = 0.3
WEEKLY_THEMATIC_TEMPERATURE = 0.35
MONTHLY_REPORT_TEMPERATURE = 0.35
_CENTRAL_TZ = ZoneInfo("America/Chicago")


def get_openai_client(api_key):
    return OpenAI(api_key=api_key)


def save_text_output(output_dir, filename, content):
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_path = path / filename
    output_path.write_text(content, encoding="utf-8")
    return output_path


def format_daily_digest_context(days=7, limit=7):
    digests = fetch_daily_digests(days=days, limit=limit)
    if not digests:
        return ""

    blocks = []
    for digest in reversed(digests):
        blocks.append(
            "\n".join(
                [
                    f"DATE: {digest['date']}",
                    "DIGEST:",
                    digest["content"].strip(),
                ]
            )
        )

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)


def format_top_article_context(days=7, limit=15):
    articles = fetch_top_articles(days=days, limit=limit)
    if not articles:
        return ""

    blocks = []
    for article in articles:
        blocks.append(
            "\n".join(
                [
                    f"TITLE: {article.get('title') or ''}",
                    f"SOURCE: {article.get('source') or ''}",
                    f"PUBLISHED_AT: {article.get('published_at') or ''}",
                    f"AI_SCORE: {article.get('ai_score') if article.get('ai_score') is not None else ''}",
                    f"SUMMARY: {article.get('summary') or ''}",
                    f"ADVISOR_RELEVANCE: {article.get('advisor_relevance') or ''}",
                    f"URL: {article.get('url') or ''}",
                ]
            )
        )

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)


def build_weekly_source_context(days=7, digest_limit=7, article_limit=15):
    digest_context = format_daily_digest_context(days=days, limit=digest_limit)
    article_context = format_top_article_context(days=days, limit=article_limit)

    if digest_context:
        if article_context:
            return (
                "PRIMARY INPUT: DAILY DIGESTS\n"
                f"{digest_context}\n\n"
                "SUPPLEMENTAL INPUT: TOP SCORED ARTICLES\n"
                f"{article_context}"
            )
        return f"PRIMARY INPUT: DAILY DIGESTS\n{digest_context}"

    if article_context:
        return f"PRIMARY INPUT: TOP SCORED ARTICLES\n{article_context}"

    return ""


def build_monthly_source_context(weeks=4):
    weekly_rows = fetch_weekly_digests(weeks=weeks, limit=weeks * 4)
    if not weekly_rows:
        return ""

    blocks = []
    for row in reversed(weekly_rows):
        blocks.append(
            "\n".join(
                [
                    f"WEEK_START: {row['week_start']}",
                    f"TYPE: {row['type']}",
                    "CONTENT:",
                    row["content"].strip(),
                ]
            )
        )

    return "\n\n" + ("\n\n" + ("=" * 80) + "\n\n").join(blocks)


def call_chat_model(client, system_prompt, user_prompt, temperature=0.3, max_completion_tokens=2200):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )
    return response.choices[0].message.content.strip()


def get_week_start(target_date=None):
    if target_date is None:
        target_date = datetime.now(_CENTRAL_TZ).date()
    return target_date - timedelta(days=target_date.weekday())


def get_latest_completed_friday(target_date=None):
    if target_date is None:
        target_date = datetime.now(_CENTRAL_TZ).date()

    days_since_friday = (target_date.weekday() - 4) % 7

    return target_date - timedelta(days=days_since_friday)
