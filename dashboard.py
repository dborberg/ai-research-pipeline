from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.db import fetch_daily_digests, fetch_monthly_reports, fetch_weekly_digests, get_engine, init_db


st.set_page_config(page_title="AI Research Dashboard", layout="wide")
load_dotenv()


def load_articles():
    query = """
        SELECT
            id,
            title,
            source,
            url,
            published_at,
            created_at,
            summary,
            advisor_relevance,
            ai_score
        FROM articles
    """
    return pd.read_sql_query(query, get_engine())


def load_daily_digests():
    return pd.DataFrame(fetch_daily_digests())


def load_weekly_digests():
    return pd.DataFrame(fetch_weekly_digests())


def load_monthly_reports():
    return pd.DataFrame(fetch_monthly_reports())


def render_articles_page():
    st.header("Articles")
    df = load_articles()

    if df.empty:
        st.info("No articles available yet.")
        return

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df["ai_score"] = pd.to_numeric(df["ai_score"], errors="coerce")

    min_date = df["published_at"].dropna().min()
    max_date = df["published_at"].dropna().max()

    filter_cols = st.columns(4)

    with filter_cols[0]:
        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.date_input(
                "Date Range",
                value=(min_date.date(), max_date.date()),
                min_value=min_date.date(),
                max_value=max_date.date(),
            )
        else:
            date_range = ()

    with filter_cols[1]:
        score_min, score_max = st.slider("AI Score", 0, 10, (0, 10))

    with filter_cols[2]:
        sources = sorted([source for source in df["source"].dropna().unique().tolist() if source])
        selected_sources = st.multiselect("Source", sources, default=sources)

    with filter_cols[3]:
        sort_column = st.selectbox(
            "Sort By",
            ["published_at", "ai_score", "source", "title"],
            index=0,
        )

    filtered = df.copy()

    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            filtered["published_at"].dt.date.between(start_date, end_date, inclusive="both")
        ]

    filtered = filtered[
        filtered["ai_score"].fillna(-1).between(score_min, score_max, inclusive="both")
        | filtered["ai_score"].isna()
    ]

    if selected_sources:
        filtered = filtered[filtered["source"].isin(selected_sources)]

    ascending = sort_column == "source"
    filtered = filtered.sort_values(by=sort_column, ascending=ascending, na_position="last")

    display_df = filtered.copy()
    display_df["published_at"] = display_df["published_at"].dt.strftime("%Y-%m-%d %H:%M")

    st.caption(f"{len(display_df)} articles")
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("URL"),
            "ai_score": st.column_config.NumberColumn("AI Score", format="%d"),
        },
    )


def render_daily_digests_page():
    st.header("Daily Digests")
    df = load_daily_digests()

    if df.empty:
        st.info("No daily digests available yet.")
        return

    df = df.sort_values("date", ascending=False)
    options = df["date"].tolist()
    selected_date = st.selectbox("Digest Date", options)
    selected_row = df[df["date"] == selected_date].iloc[0]

    st.caption(f"Created at {selected_row['created_at']}")
    st.text_area("Content", selected_row["content"], height=600)


def render_weekly_reports_page():
    st.header("Weekly Reports")
    df = load_weekly_digests()

    if df.empty:
        st.info("No weekly reports available yet.")
        return

    report_type = st.radio("Report Type", ["wholesaler", "thematic"], horizontal=True)
    filtered = df[df["type"] == report_type].sort_values("week_start", ascending=False)

    if filtered.empty:
        st.info(f"No {report_type} reports available yet.")
        return

    selected_week = st.selectbox("Week Start", filtered["week_start"].tolist())
    selected_row = filtered[filtered["week_start"] == selected_week].iloc[0]

    st.caption(f"Created at {selected_row['created_at']}")
    st.text_area("Content", selected_row["content"], height=600)


def render_monthly_reports_page():
    st.header("Monthly Reports")
    df = load_monthly_reports()

    if df.empty:
        st.info("No monthly reports available yet.")
        return

    df = df.sort_values("month", ascending=False)
    selected_month = st.selectbox("Month", df["month"].tolist())
    selected_row = df[df["month"] == selected_month].iloc[0]

    st.caption(f"Created at {selected_row['created_at']}")
    st.text_area("Content", selected_row["content"], height=600)


def main():
    init_db()

    st.title("AI Research Dashboard")
    page = st.sidebar.radio(
        "Page",
        ["Articles", "Daily Digests", "Weekly Reports", "Monthly Reports"],
    )

    if page == "Articles":
        render_articles_page()
    elif page == "Daily Digests":
        render_daily_digests_page()
    elif page == "Weekly Reports":
        render_weekly_reports_page()
    else:
        render_monthly_reports_page()


if __name__ == "__main__":
    main()
