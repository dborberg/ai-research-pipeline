
import hashlib
import os
from datetime import timedelta

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

from app.cluster_schema import normalize_cluster_df
from app.db import get_articles_by_ids, get_cluster_history, get_weekly_clusters, save_weekly_clusters
from app.reporting import get_openai_client, get_week_start
from run_weekly_pipeline import cluster_articles, get_weekly_articles

try:
    from plotly import express as px
except ImportError:  # pragma: no cover - optional dependency
    px = None


st.set_page_config(page_title="AI Signal Dashboard", layout="wide")


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_cluster_strength(avg_score, high_signal_ratio, article_count):
    return round(
        (0.5 * avg_score) +
        (0.3 * high_signal_ratio * 10) +
        (0.2 * article_count),
        2,
    )


def _generate_theme_id(theme_name, representative_summary=None):
    theme_name = (theme_name or "").strip().lower()
    summary = (representative_summary or "").strip().lower()
    hash_input = f"{theme_name}|{summary}" if summary else theme_name
    return hashlib.md5(hash_input.encode()).hexdigest()[:10]


def _prepare_clusters(clusters):
    for cluster in clusters:
        cluster["theme_id"] = str(
            cluster.get("theme_id") or _generate_theme_id(
                cluster.get("theme_name"),
                cluster.get("representative_summary"),
            )
        )
        cluster["cluster_strength"] = _compute_cluster_strength(
            _safe_float(cluster.get("avg_score")),
            _safe_float(cluster.get("high_signal_ratio")),
            int(cluster.get("article_count") or len(cluster.get("articles", []))),
        )
    return clusters


def _get_theme_key(row):
    text = f"{row.get('theme_name', '')} {row.get('investment_relevance', '')}".lower()

    if any(keyword in text for keyword in ["nvidia", "gpu", "chip", "semiconductor", "semis"]):
        return "semis"
    if any(keyword in text for keyword in ["data center", "power", "grid", "electricity", "infrastructure"]):
        return "infrastructure"
    if any(keyword in text for keyword in ["enterprise", "software", "roi", "productivity", "automation"]):
        return "enterprise"
    if any(keyword in text for keyword in ["regulation", "policy", "government", "compliance"]):
        return "policy"
    if any(keyword in text for keyword in ["labor", "jobs", "hiring", "workforce"]):
        return "labor"
    return "other"


def _get_velocity_symbol(value):
    if value > 0:
        return "\u2191"
    if value < 0:
        return "\u2193"
    return "\u2192"


def _get_strength_label(value):
    if value > 8:
        return "High conviction"
    if value > 6:
        return "Watch closely"
    return "Early signal"


def _render_strength_badge(column, cluster_strength):
    label = _get_strength_label(cluster_strength)
    if cluster_strength > 8:
        column.success(label)
    elif cluster_strength > 6:
        column.warning(label)
    else:
        column.info(label)


def _ensure_display_fields(cluster_df):
    if cluster_df is None or cluster_df.empty:
        return cluster_df

    cluster_df = cluster_df.copy()
    if "persistence" not in cluster_df.columns:
        cluster_df["persistence"] = 1
    cluster_df["persistence"] = cluster_df["persistence"].fillna(1).astype(int)
    return cluster_df


@st.cache_data
def load_articles(week_start):
    _ = week_start
    article_data = get_weekly_articles()
    return article_data.get("articles", [])


@st.cache_data
def load_articles_by_ids(article_ids):
    return get_articles_by_ids(list(article_ids))


def build_cluster_dataframe(clusters, week_start):
    rows = []

    for cluster in clusters:
        avg_score = round(_safe_float(cluster.get("avg_score")), 2)
        article_count = int(cluster.get("article_count") or len(cluster.get("articles", [])))
        high_signal_ratio = round(_safe_float(cluster.get("high_signal_ratio")), 2)
        cluster_strength = round(
            _safe_float(cluster.get("cluster_strength"), _compute_cluster_strength(avg_score, high_signal_ratio, article_count)),
            2,
        )
        signal_quality = round(avg_score * high_signal_ratio, 2)
        velocity = int(cluster.get("velocity") or 0)
        conviction_score = (
            (cluster_strength * 0.5) +
            (signal_quality * 0.3) +
            (max(velocity, 0) * 0.2)
        )

        rows.append(
            {
                "week_start": str(week_start),
                "theme_id": str(cluster.get("theme_id") or _generate_theme_id(
                    cluster.get("theme_name"),
                    cluster.get("representative_summary"),
                )),
                "theme_name": str(cluster.get("theme_name") or "Untitled Theme").strip(),
                "theme": str(cluster.get("theme") or ""),
                "avg_score": avg_score,
                "article_count": article_count,
                "high_signal_ratio": high_signal_ratio,
                "cluster_strength": cluster_strength,
                "velocity": velocity,
                "signal_quality": signal_quality,
                "conviction_score": round(conviction_score, 2),
                "investment_relevance": str(cluster.get("investment_relevance") or "").strip(),
                "representative_summary": str(cluster.get("representative_summary") or "").strip(),
                "article_ids": cluster.get("article_ids", []),
                "articles": cluster.get("articles", []),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if "theme" not in df.columns or df["theme"].replace("", pd.NA).isna().all():
        df["theme"] = df.apply(lambda row: _get_theme_key(row), axis=1)

    return df.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


@st.cache_data
def load_runtime_clusters(week_start, api_key):
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set to compute runtime clusters.")

    articles = load_articles(week_start)
    if not articles:
        return build_cluster_dataframe([], week_start)

    client = get_openai_client(api_key)
    clusters = _prepare_clusters(cluster_articles(client, articles))
    save_weekly_clusters(week_start, clusters)
    return build_cluster_dataframe(clusters, week_start)


@st.cache_data
def load_stored_clusters(week_start):
    stored_rows = get_weekly_clusters(week_start)
    if not stored_rows:
        return build_cluster_dataframe([], week_start)
    hydrated_clusters = []
    for row in stored_rows:
        article_ids = tuple(row.get("article_ids", []))
        articles = load_articles_by_ids(article_ids) if article_ids else []
        hydrated_clusters.append(
            {
                **dict(row),
                "articles": articles,
            }
        )
    return build_cluster_dataframe(hydrated_clusters, week_start)


def load_clusters(week_start, api_key):
    stored_df = load_stored_clusters(week_start)
    if not stored_df.empty:
        return stored_df
    return load_runtime_clusters(week_start, api_key)


def compute_velocity(current_df, previous_df):
    columns = ["theme_id", "theme_name", "article_count", "previous_article_count", "velocity"]
    if current_df.empty:
        return pd.DataFrame(columns=columns)

    current_counts = current_df[["theme_id", "theme_name", "article_count"]].copy()
    current_counts = current_counts.rename(columns={"article_count": "current_article_count"})

    if previous_df.empty:
        velocity_df = current_counts.copy()
        velocity_df["previous_article_count"] = 0
        velocity_df["velocity"] = velocity_df["current_article_count"]
    else:
        previous_counts = previous_df[["theme_id", "article_count"]].copy()
        previous_counts = previous_counts.rename(columns={"article_count": "previous_article_count"})
        velocity_df = current_counts.merge(previous_counts, on="theme_id", how="left")
        velocity_df["previous_article_count"] = velocity_df["previous_article_count"].fillna(0).astype(int)
        velocity_df["velocity"] = (
            velocity_df["current_article_count"] - velocity_df["previous_article_count"]
        )

        previous_only = previous_df[~previous_df["theme_id"].isin(current_df["theme_id"])]

        if not previous_only.empty:
            decay_rows = previous_only.copy()
            decay_rows["current_article_count"] = 0
            decay_rows["velocity"] = -decay_rows["article_count"]

            decay_rows = decay_rows.rename(columns={
                "article_count": "previous_article_count"
            })

            velocity_df = pd.concat([velocity_df, decay_rows], ignore_index=True)

    velocity_df = velocity_df.rename(columns={"current_article_count": "article_count"})
    velocity_df = velocity_df.sort_values(
        ["velocity", "article_count"],
        ascending=[False, False],
    ).reset_index(drop=True)
    return velocity_df[columns]


def apply_velocity_metrics(cluster_df, velocity_df):
    if cluster_df.empty:
        return cluster_df

    merged = cluster_df.merge(
        velocity_df[["theme_id", "velocity", "previous_article_count"]],
        on="theme_id",
        how="left",
        suffixes=("", "_velocity"),
    )
    merged = normalize_cluster_df(merged)
    if "velocity_velocity" in merged.columns and "velocity" in merged.columns:
        merged["velocity"] = merged["velocity_velocity"].fillna(merged["velocity"]).fillna(0).astype(int)
    elif "velocity_velocity" in merged.columns:
        merged["velocity"] = merged["velocity_velocity"].fillna(0).astype(int)
    elif "velocity" in merged.columns:
        merged["velocity"] = merged["velocity"].fillna(0).astype(int)
    else:
        merged["velocity"] = 0
    merged["previous_article_count"] = merged["previous_article_count"].fillna(0).astype(int)
    merged["conviction_score"] = (
        (merged["cluster_strength"] * 0.5) +
        (merged["signal_quality"] * 0.3) +
        (merged["velocity"].clip(lower=0) * 0.2)
    ).round(2)
    if "theme" not in merged.columns or merged["theme"].replace("", pd.NA).isna().all():
        merged["theme"] = merged.apply(lambda row: _get_theme_key(row), axis=1)
    if "velocity_velocity" in merged.columns:
        merged = merged.drop(columns=["velocity_velocity"])
    return merged.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def render_top_clusters(cluster_df, velocity_df):
    st.subheader("Top Themes By Conviction")

    if cluster_df.empty:
        st.info("No clusters were generated for the selected week.")
        return

    velocity_lookup = velocity_df.set_index("theme_id")["velocity"].to_dict() if not velocity_df.empty else {}
    top_clusters = cluster_df.head(5)
    columns = st.columns(5)

    for column, (_, row) in zip(columns, top_clusters.iterrows()):
        velocity = int(velocity_lookup.get(row["theme_id"], 0))
        delta_text = f"{_get_velocity_symbol(velocity)} {velocity:+d} vs prior week"
        column.metric("Cluster Strength", f"{row['cluster_strength']:.2f}", delta_text)
        column.markdown(f"**{row['theme_name']}**")
        column.caption(f"Persistence: {int(row.get('persistence', 1))} weeks")
        column.caption(f"Signal Quality: {row['signal_quality']:.2f}")
        column.caption(f"Avg Score: {row['avg_score']:.2f}")
        column.caption(f"Articles: {int(row['article_count'])}")
        _render_strength_badge(column, row["cluster_strength"])


def render_attention_section(cluster_df, velocity_df):
    st.subheader("Where PMs Should Focus")

    if cluster_df.empty or velocity_df.empty:
        st.info("No cluster momentum data is available yet.")
        return

    attention_df = cluster_df[
        (cluster_df["conviction_score"] > 6)
    ].sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).head(5)

    if attention_df.empty:
        st.info("No themes currently clear the conviction threshold.")
        return

    for _, row in attention_df.iterrows():
        st.markdown(f"### {row['theme_name']}")
        st.caption(f"Theme: {row['theme']}")
        st.write(row["investment_relevance"] or "No investment relevance summary was generated.")
        st.caption(
            f"Conviction: {row['conviction_score']:.2f} | "
            f"Velocity: {int(row['velocity']):+d} | "
            f"Persistence: {int(row.get('persistence', 1))} weeks | "
            f"Strength: {row['cluster_strength']:.2f}"
        )


def render_signal_buckets(cluster_df):
    if cluster_df.empty:
        return

    conviction_median = cluster_df["conviction_score"].median()
    structural = cluster_df[
        (cluster_df["persistence"] >= 3) &
        (cluster_df["conviction_score"] >= conviction_median)
    ].head(3)
    rising = cluster_df[cluster_df["velocity"] > 0].head(3)
    breaking_down = cluster_df[cluster_df["velocity"] < 0].sort_values("velocity").head(3)

    bucket_columns = st.columns(3)
    buckets = [
        ("Structural Winners", structural, "No structural winners are standing out yet."),
        ("Rising Themes", rising, "No rising themes are breaking out yet."),
        ("Breaking Down", breaking_down, "No themes are clearly breaking down this week."),
    ]

    for column, (title, bucket_df, empty_message) in zip(bucket_columns, buckets):
        column.markdown(f"**{title}**")
        if bucket_df.empty:
            column.caption(empty_message)
            continue
        for _, row in bucket_df.iterrows():
            column.markdown(f"**{row['theme_name']}**")
            column.caption(
                f"Conviction {row['conviction_score']:.2f} | "
                f"{_get_velocity_symbol(int(row['velocity']))} {int(row['velocity']):+d} | "
                f"{int(row.get('persistence', 1))} weeks"
            )


def render_theme_explorer(cluster_df, velocity_df):
    st.subheader("Theme Explorer")

    if cluster_df.empty:
        st.info("No theme data is available.")
        return

    selected_theme = st.selectbox("Theme", cluster_df["theme_name"].tolist())
    selected_row = cluster_df[cluster_df["theme_name"] == selected_theme].iloc[0]
    velocity_lookup = velocity_df.set_index("theme_id")["velocity"].to_dict() if not velocity_df.empty else {}
    velocity = int(velocity_lookup.get(selected_row["theme_id"], 0))

    metric_columns = st.columns(4)
    metric_columns[0].metric("Average Score", f"{selected_row['avg_score']:.2f}")
    metric_columns[1].metric("Article Count", int(selected_row["article_count"]))
    metric_columns[2].metric("Persistence", f"{int(selected_row.get('persistence', 1))} weeks")
    metric_columns[3].metric("Signal Quality", f"{selected_row['signal_quality']:.2f}", f"{_get_velocity_symbol(velocity)} {velocity:+d}")

    st.markdown("**Investment Relevance**")
    st.write(selected_row["investment_relevance"] or "No investment relevance summary was generated.")

    if selected_row["representative_summary"]:
        st.markdown("**Cluster Summary**")
        st.write(selected_row["representative_summary"])

    trend_window = st.selectbox("Trend Window", [4, 8, 12], index=1)
    render_trend_chart(selected_row["theme_id"], trend_window)

    st.markdown("**Top Articles**")
    articles = selected_row["articles"][:5]
    if not articles:
        st.info("No stored articles were found for this cluster.")
        return

    for article in articles:
        title = article.get("title") or "Untitled Article"
        source = article.get("source") or "Unknown Source"
        summary = article.get("summary") or "No summary available."
        st.markdown(f"**{title}**")
        st.caption(source)
        st.write(summary)


def render_trend_chart(theme_id, limit=12):
    st.markdown("**Trend Chart**")

    history = get_cluster_history(theme_id, limit=limit)
    if not history:
        st.info("Not enough history is available for this theme yet.")
        return

    history_df = pd.DataFrame([dict(row) for row in history])
    history_df["week_start"] = pd.to_datetime(history_df["week_start"], errors="coerce")
    history_df = history_df.sort_values("week_start")
    history_df["smoothed"] = history_df["article_count"].rolling(2).mean()

    if px is not None:
        chart = px.line(
            history_df,
            x="week_start",
            y=["article_count", "smoothed"],
            markers=True,
            title="Theme Momentum (Smoothed)",
        )
        chart.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.dataframe(
            history_df[["week_start", "article_count", "avg_score", "high_signal_ratio"]],
            use_container_width=True,
            hide_index=True,
        )


def render_signal_velocity(velocity_df):
    st.subheader("Signal Velocity")

    if velocity_df.empty:
        st.info("No week-over-week velocity data is available yet.")
        return

    rising = velocity_df.sort_values(
        ["velocity", "article_count"],
        ascending=[False, False],
    ).head(5)

    st.markdown("**Top Rising Themes**")
    st.dataframe(
        rising[["theme_name", "article_count", "previous_article_count", "velocity"]],
        use_container_width=True,
        hide_index=True,
    )

    if px is not None:
        chart = px.bar(
            rising.sort_values("velocity", ascending=True),
            x="velocity",
            y="theme_name",
            orientation="h",
            title="Top Rising Themes",
        )
        chart.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(chart, use_container_width=True)


def main():

    # Auto-refresh every 5 minutes (300,000 ms)
    st_autorefresh(interval=300000, key="auto-refresh")
    load_dotenv()

    st.title("AI Signal Command Center")
    st.caption("Weekly AI signal detection and thematic momentum")

    api_key = os.getenv("OPENAI_API_KEY")
    current_week = get_week_start()
    previous_week = current_week - timedelta(days=7)

    try:
        cluster_df = load_clusters(current_week.isoformat(), api_key)
        previous_cluster_df = load_stored_clusters(previous_week.isoformat())
    except Exception as exc:
        st.error(f"Unable to load cluster data: {exc}")
        st.stop()

    if cluster_df.empty:
        st.warning("No weekly article clusters were generated. Check whether the article pipeline has recent scored content.")
        st.stop()

    cluster_df = normalize_cluster_df(cluster_df)
    velocity_df = compute_velocity(cluster_df, previous_cluster_df)
    print("Normalized columns:", list(cluster_df.columns))
    cluster_df = apply_velocity_metrics(cluster_df, velocity_df)
    cluster_df = _ensure_display_fields(cluster_df)
    cluster_df["theme"] = cluster_df.apply(lambda row: _get_theme_key(row), axis=1)
    cluster_df = cluster_df.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    selected_theme = st.selectbox(
        "Filter by Theme",
        ["All"] + sorted(cluster_df["theme"].unique())
    )

    if selected_theme != "All":
        cluster_df = cluster_df[cluster_df["theme"] == selected_theme].reset_index(drop=True)

    if cluster_df.empty:
        st.warning("No clusters matched the selected theme filter.")
        st.stop()

    top_theme_name = cluster_df.iloc[0]["theme_name"]
    positive_velocity = velocity_df[velocity_df["velocity"] > 0]
    if positive_velocity.empty:
        top_velocity_theme = "No rising theme"
    else:
        top_velocity_theme = positive_velocity.iloc[0]["theme_name"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Top Theme", top_theme_name)
    col2.metric(
        "Highest Conviction",
        f"{cluster_df['conviction_score'].max():.2f}"
    )
    col3.metric(
        "Strongest Momentum",
        top_velocity_theme
    )
    col4.metric(
        "Themes Active",
        cluster_df["theme"].nunique()
    )

    theme_df = cluster_df.groupby("theme", as_index=False).agg(
        total_articles=("article_count", "sum"),
        avg_conviction=("conviction_score", "mean"),
        avg_velocity=("velocity", "mean"),
        strongest_theme=("theme_name", "first")
    )

    theme_df = theme_df.sort_values(
        ["avg_conviction", "avg_velocity"],
        ascending=[False, False]
    )

    st.divider()
    if px is not None and not theme_df.empty:
        fig = px.bar(
            theme_df,
            x="theme",
            y="avg_conviction",
            color="avg_velocity",
            title="Conviction by Theme",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
    render_top_clusters(cluster_df, velocity_df)
    st.divider()
    render_signal_buckets(cluster_df)
    st.divider()
    render_attention_section(cluster_df, velocity_df)
    st.divider()
    render_theme_explorer(cluster_df, velocity_df)
    st.divider()
    render_signal_velocity(velocity_df)


if __name__ == "__main__":
    main()
