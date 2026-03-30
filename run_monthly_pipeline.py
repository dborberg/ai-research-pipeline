import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

from app.cluster_schema import normalize_cluster_df
from app.db import fetch_daily_digests, fetch_weekly_digests, get_weekly_clusters, init_db, upsert_monthly_report
from app.reporting import call_chat_model, get_openai_client, get_week_start, save_text_output
from app.send_email import send_report

_CENTRAL_TZ = ZoneInfo("America/Chicago")

MONTHLY_TITLE = "Monthly Tunes from the Gen AI Songbook"


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


def _load_recent_cluster_history(weeks=5):
    current_week = get_week_start()
    rows = []

    for index in range(weeks):
        week_start = current_week - timedelta(days=7 * index)
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
        temperature=0.2,
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
        temperature=0.2,
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
        temperature=0.2,
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
    weekly_rows = fetch_weekly_digests(weeks=8, limit=12)
    daily_rows = fetch_daily_digests(days=35, limit=20)

    if not weekly_rows and not daily_rows:
        raise RuntimeError("No daily or weekly digest history available for monthly fallback mode")

    history_context = _build_text_history_context(weekly_rows, daily_rows)
    system_prompt = """
You are a senior portfolio strategy analyst writing a monthly AI review from prior daily and weekly advisor briefs.
Use plain text only. Be concise, analytical, and investment-oriented. Do not invent facts beyond the supplied material.
"""
    user_prompt = f"""
Write the monthly AI signal review for {report_month} using the historical daily and weekly digest content below.

Requirements:
- Use these exact section headers:
  EXECUTIVE SUMMARY
  STRUCTURAL WINNERS
  RISING THEMES
  BREAKING DOWN
  PORTFOLIO IMPLICATIONS
- Under EXECUTIVE SUMMARY, provide 3 to 5 bullets.
- Under STRUCTURAL WINNERS, RISING THEMES, and BREAKING DOWN, provide 2 to 4 numbered items each.
- Under PORTFOLIO IMPLICATIONS, provide 3 to 5 bullets.
- Focus on recurring themes, shifts in emphasis, and portfolio-relevant implications.
- Plain text only.

SOURCE MATERIAL:
{history_context}
"""

    return call_chat_model(
        client,
        system_prompt,
        user_prompt,
        temperature=0.2,
        max_completion_tokens=1800,
    )


def generate_monthly_brief(summary_df, report_month, client):
    if summary_df.empty:
        return "\n".join([
            "No monthly theme data is available yet.",
        ]).strip()

    summary_df = normalize_cluster_df(summary_df)
    conviction_median = summary_df["conviction_score"].median()

    structural = summary_df[
        (summary_df["persistence"] >= 3) &
        (summary_df["conviction_score"] > conviction_median)
    ].sort_values(
        ["conviction_score", "persistence", "avg_velocity"],
        ascending=[False, False, False],
    ).head(5)

    rising = summary_df[
        ((summary_df["velocity"] if "velocity" in summary_df.columns else 0) > 0) |
        (summary_df["avg_velocity"] > 0) |
        (summary_df["conviction_score"] > conviction_median)
    ].sort_values(
        ["avg_velocity", "conviction_score", "persistence"],
        ascending=[False, False, False],
    ).head(5)

    breaking_down = summary_df[
        ((summary_df["velocity"] if "velocity" in summary_df.columns else 0) < 0) |
        (summary_df["avg_velocity"] < 0) |
        (summary_df["conviction_score"] < conviction_median)
    ].sort_values(
        ["avg_velocity", "conviction_score"],
        ascending=[True, False],
    ).head(5)

    def _fallback_relevance(row):
        relevance = str(row.get("latest_relevance") or "").strip()
        if relevance:
            return relevance
        return (
            f"{row['theme_name']} remains relevant because conviction and persistence indicate "
            "the theme is still shaping AI-related capital allocation."
        )

    def _render_theme_block(row):
        pm_take = _generate_pm_take(client, row).strip()
        why_it_matters = _fallback_relevance(row)
        return [
            str(row["theme_name"]),
            "",
            f"Conviction: {float(row['conviction_score']):.1f}",
            f"Velocity: {float(row.get('avg_velocity', 0.0)):+.1f}",
            f"Persistence: {int(row['persistence'])} weeks",
            "",
            "Why It Matters:",
            why_it_matters,
            "",
            "PM Takeaway:",
            pm_take or "Sustained AI infrastructure buildout supports utilities, grid equipment, and power semis exposure.",
            "",
        ]

    lines = [
        "STRUCTURAL WINNERS",
        "",
    ]

    if structural.empty:
        lines.extend(["No structural winners cleared the conviction threshold this month.", ""])
    else:
        for _, row in structural.iterrows():
            lines.extend(_render_theme_block(row))

    lines.extend(["RISING THEMES", ""])
    if rising.empty:
        lines.extend(["No rising themes stood out this month.", ""])
    else:
        for _, row in rising.iterrows():
            lines.extend(_render_theme_block(row))

    lines.extend(["BREAKING DOWN", ""])
    if breaking_down.empty:
        lines.extend(["No themes showed a meaningful breakdown in momentum.", ""])
    else:
        for _, row in breaking_down.iterrows():
            lines.extend(_render_theme_block(row))

    return "\n".join(str(line) for line in lines if line is not None).strip()


def main():
    load_dotenv()
    init_db()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")

    history_df = _load_recent_cluster_history(weeks=5)
    report_month = datetime.now(_CENTRAL_TZ).strftime("%Y-%m")
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
