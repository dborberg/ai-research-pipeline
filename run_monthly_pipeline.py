import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

from app.branding import MONTHLY_TITLE
from app.cluster_schema import normalize_cluster_df
from app.db import fetch_daily_digests, fetch_weekly_digests, get_weekly_clusters, init_db, upsert_monthly_report
from app.reporting import (
    build_monthly_source_context,
    call_chat_model,
    get_latest_completed_friday,
    get_latest_completed_month,
    get_month_bounds,
    get_openai_client,
    save_text_output,
)
from app.send_email import send_report

_CENTRAL_TZ = ZoneInfo("America/Chicago")

def _with_monthly_report_header(title, report_month, content):
    month_label = datetime.strptime(report_month, "%Y-%m").strftime("%B %Y")
    cleaned_content = (content or "").strip()

    for prefix in (
        "AI SIGNAL COMMAND REVIEW - MONTHLY\nMonth: ",
        "AI SIGNAL COMMAND REVIEW - MONTHLY",
    ):
        if cleaned_content.startswith(prefix):
            if prefix == "AI SIGNAL COMMAND REVIEW - MONTHLY\nMonth: ":
                lines = cleaned_content.splitlines()
                cleaned_content = "\n".join(lines[2:]).strip()
            else:
                cleaned_content = cleaned_content[len(prefix):].strip()
            break

    return "\n\n".join([
        title,
        f"Month of {month_label}",
        cleaned_content,
    ]).strip()


def _iter_fridays_in_month(report_month):
    month_start, next_month_start = get_month_bounds(report_month)
    first_friday_offset = (4 - month_start.weekday()) % 7
    current_friday = month_start + timedelta(days=first_friday_offset)

    fridays = []
    while current_friday < next_month_start:
        fridays.append(current_friday)
        current_friday += timedelta(days=7)
    return fridays


def _load_recent_cluster_history(report_month):
    rows = []

    for week_start in _iter_fridays_in_month(report_month):
        weekly_rows = get_weekly_clusters(week_start)
        for row in weekly_rows:
            row_dict = dict(row)
            row_dict["week_start"] = week_start.isoformat()
            rows.append(row_dict)

    return normalize_cluster_df(pd.DataFrame(rows))


def classify_regime(row):
    if row["avg_velocity"] > 0 and row["persistence"] >= 3:
        return "ACCELERATING"
    elif row["avg_velocity"] < 0:
        return "FADING"
    else:
        return "STABLE"


def _compute_theme_summary(history_df):
    if history_df.empty:
        return pd.DataFrame()

    history_df = history_df.copy()
    history_df["article_count"] = pd.to_numeric(history_df["article_count"], errors="coerce").fillna(0)
    history_df["avg_score"] = pd.to_numeric(history_df["avg_score"], errors="coerce").fillna(0)
    history_df["cluster_strength"] = pd.to_numeric(history_df["cluster_strength"], errors="coerce").fillna(0)
    history_df["week_start"] = pd.to_datetime(history_df["week_start"], errors="coerce")
    history_df = history_df.sort_values(["theme_id", "week_start"])

    history_df["previous_article_count"] = history_df.groupby("theme_id")["article_count"].shift(1).fillna(0)
    history_df["velocity"] = history_df["article_count"] - history_df["previous_article_count"]

    summary_df = history_df.groupby("theme_id", as_index=False).agg(
        theme_name=("theme_name", "last"),
        total_article_count=("article_count", "sum"),
        avg_score=("avg_score", "mean"),
        avg_velocity=("velocity", "mean"),
        persistence=("week_start", "nunique"),
        latest_strength=("cluster_strength", "last"),
        latest_relevance=("investment_relevance", "last"),
        latest_article_count=("article_count", "last"),
    )

    summary_df["avg_score"] = summary_df["avg_score"].round(2)
    summary_df["avg_velocity"] = summary_df["avg_velocity"].round(2)
    summary_df["latest_strength"] = summary_df["latest_strength"].round(2)
    summary_df["conviction_score"] = (
        (summary_df["latest_strength"] * 0.4) +
        (summary_df["avg_velocity"].clip(lower=0) * 0.3) +
        (summary_df["persistence"] * 0.3)
    ).round(2)
    summary_df["regime"] = summary_df.apply(classify_regime, axis=1)
    summary_df["priority"] = pd.cut(
        summary_df["conviction_score"],
        bins=[-1, 4, 7, 100],
        labels=["LOW", "MEDIUM", "HIGH"],
    )
    summary_df = normalize_cluster_df(summary_df)

    return summary_df.sort_values(
        ["persistence", "conviction_score", "avg_velocity"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _build_llm_context(summary_df):
    context_lines = []
    for _, row in summary_df.iterrows():
        context_lines.extend(
            [
                f"THEME: {row['theme_name']}",
                f"CONVICTION_SCORE: {row['conviction_score']:.2f}",
                f"REGIME: {row['regime']}",
                f"PRIORITY: {row['priority']}",
                f"PERSISTENCE: {int(row['persistence'])}",
                f"AVG_VELOCITY: {row['avg_velocity']:+.2f}",
                f"LATEST_STRENGTH: {row['latest_strength']:.2f}",
                f"WHY_IT_MATTERS: {row['latest_relevance'] or 'No relevance summary available.'}",
                "",
            ]
        )
    return "\n".join(context_lines).strip()


def _build_monthly_scorecard(summary_df):
    if summary_df.empty:
        return "No cluster summary data available."

    persistent_count = int((summary_df["persistence"] >= 3).sum())
    accelerating_count = int((summary_df["regime"] == "ACCELERATING").sum())
    fading_count = int((summary_df["regime"] == "FADING").sum())
    median_conviction = float(summary_df["conviction_score"].median())

    top_row = summary_df.sort_values(
        ["persistence", "conviction_score", "avg_velocity"],
        ascending=[False, False, False],
    ).iloc[0]

    lines = [
        f"THEME_COUNT: {len(summary_df)}",
        f"PERSISTENT_THEMES_3PLUS_WEEKS: {persistent_count}",
        f"ACCELERATING_THEMES: {accelerating_count}",
        f"FADING_THEMES: {fading_count}",
        f"MEDIAN_CONVICTION: {median_conviction:.2f}",
        (
            "TOP_SIGNAL: "
            f"{top_row['theme_name']} "
            f"(conviction {float(top_row['conviction_score']):.1f}, "
            f"persistence {int(top_row['persistence'])} weeks, "
            f"velocity {float(top_row['avg_velocity']):+.1f})"
        ),
    ]
    return "\n".join(lines)


def _generate_monthly_synthesis(report_month, client, source_context, summary_df=None):
    context_sections = []

    if summary_df is not None and not summary_df.empty:
        top_summary_df = summary_df.head(12)
        context_sections.extend(
            [
                "MONTHLY SCORECARD",
                _build_monthly_scorecard(summary_df),
                "",
                "TOP THEME TABLE",
                _build_llm_context(top_summary_df),
            ]
        )

    if source_context:
        if context_sections:
            context_sections.append("")
        context_sections.extend(
            [
                "MONTHLY SOURCE MATERIAL",
                source_context,
            ]
        )

    combined_context = "\n".join(section for section in context_sections if section is not None).strip()
    if not combined_context:
        raise RuntimeError("No monthly source material is available for synthesis")

    system_prompt = """
You are a senior portfolio strategy analyst writing a useful monthly AI investment review.
Use plain text only. Be concise, analytical, and portfolio-relevant. Do not invent facts beyond the supplied material.
Prefer synthesis over theme dumping.
"""
    user_prompt = f"""
Write the monthly AI signal review for {report_month}.

Requirements:
- Use these exact section headers:
  EXECUTIVE SUMMARY
  THE BIG SHIFTS
  INVESTABLE SIGNALS
  FRICTIONS AND RISKS
  PORTFOLIO ACTIONS
- Under EXECUTIVE SUMMARY, provide exactly 3 bullets.
- Under THE BIG SHIFTS, provide 2 to 4 numbered items.
- Under INVESTABLE SIGNALS, provide 2 to 4 numbered items.
- Under FRICTIONS AND RISKS, provide 2 to 3 numbered items.
- Under PORTFOLIO ACTIONS, provide 3 to 5 bullets.
- Group overlapping topics into broader themes instead of repeating near-duplicate compute, power, or capex items.
- Do not output raw label dumps such as repeated Conviction/Velocity/Persistence lines.
- Only surface single-week or low-persistence signals if they reinforce a broader pattern; otherwise treat them as watch items or omit them.
- Each numbered item should start with a short theme headline followed by 2 to 4 sentences explaining what changed and why it matters for investors.
- If the evidence base is thin or noisy, say so directly in the relevant section.
- Focus on what changed across the month, what seems durable, and what actually matters for portfolio positioning.
- Plain text only.

SOURCE MATERIAL:
{combined_context}
"""

    return call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=2200,
    )


def _generate_executive_summary(client, summary_df, report_month):
    context = _build_llm_context(summary_df.head(8))
    system_prompt = """
You are a senior portfolio strategy analyst writing a concise executive summary for a monthly AI signal review.
Use plain text only. Be analytical, investment-oriented, and concise.
"""
    user_prompt = f"""
Write a short executive summary for the monthly AI signal review for {report_month}.

Requirements:
- 3 to 5 bullets
- Focus on conviction, regime change, and investment relevance
- Prioritize implications for portfolio managers
- Plain text only

DATA:
{context}
"""
    return call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=500,
    )


def _generate_pm_take(client, row):
    system_prompt = """
You are a portfolio strategist writing a one- to two-sentence PM take on an AI theme.
Use plain text only. Be concise, analytical, and investment-relevant.
"""
    user_prompt = f"""
Write a short PM Take for this theme.

THEME: {row['theme_name']}
CONVICTION_SCORE: {row['conviction_score']:.2f}
REGIME: {row['regime']}
PERSISTENCE: {int(row['persistence'])}
AVG_VELOCITY: {row['avg_velocity']:+.2f}
LATEST_STRENGTH: {row['latest_strength']:.2f}
WHY_IT_MATTERS: {row['latest_relevance'] or 'No relevance summary available.'}
"""
    return call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=180,
    )


def _generate_portfolio_implications(client, summary_df):
    context = _build_llm_context(summary_df.head(10))
    system_prompt = """
You are a senior portfolio strategy analyst.
Write 3 to 5 plain-text bullets covering capital allocation implications, sector impact, and risk considerations.
"""
    user_prompt = f"""
Generate portfolio implications from these monthly AI themes.

Requirements:
- 3 to 5 bullets
- Cover capital allocation implications
- Cover sector impact
- Cover risk considerations
- Plain text only

DATA:
{context}
"""
    return call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=400,
    )


def _truncate_block(text, max_chars=3500):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _build_text_history_context(weekly_rows, daily_rows):
    sections = []

    for row in weekly_rows:
        sections.extend([
            f"WEEKLY DIGEST ({row['type']}) - {row['week_start']}",
            _truncate_block(row["content"], max_chars=4500),
            "",
        ])

    for row in daily_rows:
        sections.extend([
            f"DAILY DIGEST - {row['date']}",
            _truncate_block(row["content"], max_chars=1800),
            "",
        ])

    return "\n".join(sections).strip()


def _should_use_text_history(history_df, minimum_cluster_weeks=3):
    if history_df.empty:
        return True

    if "week_start" not in history_df.columns:
        return True

    unique_weeks = pd.to_datetime(history_df["week_start"], errors="coerce").dropna().dt.date.nunique()
    return unique_weeks < minimum_cluster_weeks


def generate_monthly_brief_from_text_history(report_month, client):
    month_start, next_month_start = get_month_bounds(report_month)
    weekly_rows = fetch_weekly_digests(weeks=12, limit=24)
    weekly_rows = [
        row for row in weekly_rows
        if month_start.isoformat() <= str(row["week_start"]) < next_month_start.isoformat()
    ]
    daily_rows = fetch_daily_digests(days=45, limit=45)
    daily_rows = [
        row for row in daily_rows
        if month_start.isoformat() <= str(row["date"]) < next_month_start.isoformat()
    ]

    if not weekly_rows and not daily_rows:
        raise RuntimeError("No daily or weekly digest history available for monthly fallback mode")

    history_context = _build_text_history_context(weekly_rows, daily_rows)
    return _generate_monthly_synthesis(report_month, client, history_context)


def generate_monthly_brief(summary_df, report_month, client):
    if summary_df.empty:
        return "\n".join([
            "No monthly theme data is available yet.",
        ]).strip()

    summary_df = normalize_cluster_df(summary_df)
    weekly_context = build_monthly_source_context(weeks=6)
    return _generate_monthly_synthesis(report_month, client, weekly_context, summary_df=summary_df)


def main():
    load_dotenv()
    init_db()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")

    report_month = get_latest_completed_month()
    history_df = _load_recent_cluster_history(report_month)
    client = get_openai_client(api_key)

    if _should_use_text_history(history_df):
        monthly_content = generate_monthly_brief_from_text_history(report_month, client)
    else:
        summary_df = _compute_theme_summary(history_df)
        monthly_content = generate_monthly_brief(summary_df, report_month, client)

    monthly_content = _with_monthly_report_header(MONTHLY_TITLE, report_month, monthly_content)

    upsert_monthly_report(report_month, monthly_content)
    save_text_output("outputs/monthly", f"{report_month}.txt", monthly_content)
    send_report(MONTHLY_TITLE, monthly_content)


if __name__ == "__main__":
    main()
