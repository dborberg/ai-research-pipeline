import os
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

from app.db import get_weekly_clusters, init_db, upsert_weekly_digest
from app.reporting import call_chat_model, get_openai_client, get_week_start, save_text_output
from app.send_email import send_report


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

    return pd.DataFrame(rows)


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

    return summary_df.sort_values(
        ["conviction_score", "latest_strength", "avg_velocity"],
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


def generate_monthly_brief(summary_df, report_month, client):
    top_three = summary_df.head(3)
    high_conviction = summary_df[summary_df["priority"] == "HIGH"].head(5)
    emerging = summary_df[
        (summary_df["avg_velocity"] > 0) &
        (summary_df["persistence"] < 3)
    ].sort_values(
        ["avg_velocity", "conviction_score"],
        ascending=[False, False],
    ).head(4)
    fading = summary_df[summary_df["avg_velocity"] < 0].sort_values(
        ["avg_velocity", "conviction_score"],
        ascending=[True, False],
    ).head(4)

    executive_summary = _generate_executive_summary(client, summary_df, report_month)
    portfolio_implications = _generate_portfolio_implications(client, summary_df)

    lines = [
        "AI SIGNAL COMMAND REVIEW - MONTHLY",
        f"Month: {report_month}",
        "",
        "EXECUTIVE SUMMARY",
        "",
        "Top Themes By Conviction:",
    ]

    for _, row in top_three.iterrows():
        lines.append(
            f"{row['theme_name']} | Conviction {row['conviction_score']:.2f} | Regime {row['regime']}"
        )

    lines.extend(["", executive_summary.strip(), "", "HIGH CONVICTION THEMES", ""])

    if high_conviction.empty:
        lines.append("No themes qualified for the high-conviction tier this month.")
        lines.append("")
    else:
        for _, row in high_conviction.iterrows():
            pm_take = _generate_pm_take(client, row)
            lines.extend(
                [
                    str(row["theme_name"]),
                    f"Conviction Score: {row['conviction_score']:.2f}",
                    f"Regime: {row['regime']}",
                    f"Why It Matters: {row['latest_relevance'] or 'No relevance summary available.'}",
                    f"PM Take: {pm_take.strip()}",
                    "",
                ]
            )

    lines.extend(["EMERGING THEMES", ""])
    if emerging.empty:
        lines.append("No emerging themes stood out beyond the established leaders.")
        lines.append("")
    else:
        for _, row in emerging.iterrows():
            lines.extend(
                [
                    str(row["theme_name"]),
                    f"Conviction Score: {row['conviction_score']:.2f}",
                    f"Regime: {row['regime']}",
                    f"Why It Matters: {row['latest_relevance'] or 'Momentum is building from a smaller base.'}",
                    "",
                ]
            )

    lines.extend(["THEMES LOSING MOMENTUM", ""])
    if fading.empty:
        lines.append("No themes showed meaningful loss of momentum this month.")
        lines.append("")
    else:
        for _, row in fading.iterrows():
            lines.extend(
                [
                    str(row["theme_name"]),
                    f"Conviction Score: {row['conviction_score']:.2f}",
                    f"Regime: {row['regime']}",
                    f"Why It Matters: {row['latest_relevance'] or 'Interest is fading or being displaced by adjacent themes.'}",
                    "",
                ]
            )

    lines.extend(["PORTFOLIO IMPLICATIONS", "", portfolio_implications.strip()])
    return "\n".join(lines).strip()


def main():
    load_dotenv()
    init_db()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")

    history_df = _load_recent_cluster_history(weeks=5)
    if history_df.empty:
        raise RuntimeError("No weekly cluster history available for the monthly pipeline")

    report_month = datetime.utcnow().strftime("%Y-%m")
    month_anchor = datetime.utcnow().strftime("%Y-%m-01")
    summary_df = _compute_theme_summary(history_df)
    client = get_openai_client(api_key)
    monthly_content = generate_monthly_brief(summary_df, report_month, client)

    upsert_weekly_digest(month_anchor, "monthly", monthly_content)
    save_text_output("outputs/monthly", f"{report_month}.txt", monthly_content)
    send_report(f"[MONTHLY] AI Signal Review - {report_month}", monthly_content)


if __name__ == "__main__":
    main()
