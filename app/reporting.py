from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.db import fetch_daily_digests, fetch_top_articles, fetch_weekly_digests

MODEL_NAME = "gpt-5.5"
_CENTRAL_TZ = ZoneInfo("America/Chicago")
OPENAI_REQUEST_TIMEOUT_SECONDS = 90.0
OPENAI_MAX_RETRIES = 5
OPENAI_TEXT_RETRY_MAX_TOKENS = 7500


def get_openai_client(api_key):
    return OpenAI(
        api_key=api_key,
        timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
        max_retries=OPENAI_MAX_RETRIES,
    )


def get_central_now():
    return datetime.now(_CENTRAL_TZ)


def get_latest_completed_month(target_date=None):
    if target_date is None:
        target_date = get_central_now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    first_day_of_current_month = target_date.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    return last_day_of_previous_month.strftime("%Y-%m")


def get_month_bounds(report_month):
    month_start = datetime.strptime(report_month, "%Y-%m").date().replace(day=1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month_start


def get_weekly_window_bounds(week_ending):
    if isinstance(week_ending, datetime):
        week_ending = week_ending.date()

    local_start = datetime.combine(week_ending - timedelta(days=6), time.min, tzinfo=_CENTRAL_TZ)
    local_end = datetime.combine(week_ending + timedelta(days=1), time.min, tzinfo=_CENTRAL_TZ)

    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start.isoformat(timespec="seconds"), utc_end.isoformat(timespec="seconds")


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
                    f"SOURCE: {article.get('original_publisher') or article.get('source') or ''}",
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


def call_chat_model(client, system_prompt, user_prompt, max_completion_tokens=2200):
    token_budget = max_completion_tokens
    revision_feedback = ""

    for attempt in range(3):
        request_prompt = user_prompt.strip()
        if revision_feedback:
            request_prompt = f"{request_prompt}\n\nREVISION FEEDBACK:\n{revision_feedback}"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": request_prompt},
            ],
            max_completion_tokens=token_budget,
        )

        choices = getattr(response, "choices", None) or []
        if not choices:
            raise ValueError("Chat completion did not return any choices.")

        choice = choices[0]
        message = getattr(choice, "message", None)
        content = (getattr(message, "content", None) or "").strip()
        if content:
            return content

        if getattr(choice, "finish_reason", None) == "length" and attempt < 2:
            token_budget = min(
                max(token_budget + 400, int(token_budget * 1.5)),
                OPENAI_TEXT_RETRY_MAX_TOKENS,
            )
            revision_feedback = (
                "The previous attempt ran out of output tokens before returning usable text. "
                "Rewrite the full response more compactly while preserving all requested sections, "
                "factual grounding, and completeness. Return only the finished text."
            )
            continue

        raise ValueError(
            "Chat completion returned empty content "
            f"(finish_reason={getattr(choice, 'finish_reason', None)})"
        )

    raise ValueError("Chat completion failed to produce usable content after retries.")


def get_week_start(target_date=None):
    if target_date is None:
        target_date = get_central_now().date()
    return target_date - timedelta(days=target_date.weekday())


def get_latest_completed_friday(target_date=None):
    if target_date is None:
        target_date = get_central_now().date()

    days_since_friday = (target_date.weekday() - 4) % 7

    return target_date - timedelta(days=days_since_friday)
