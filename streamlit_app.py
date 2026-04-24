import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

from app.cluster_schema import normalize_cluster_df
from app.db import fetch_weekly_digests, get_articles_by_ids, get_cluster_history, get_database_state_token, get_weekly_clusters, save_weekly_clusters
from app.reporting import get_openai_client, get_week_start
from app.velocity import apply_velocity_metrics, compute_velocity
from run_weekly_pipeline import cluster_articles, get_weekly_articles
from scripts.generate_sector_report import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    generate_with_chat_completions,
    generate_with_responses_api,
    normalize_html_output,
    normalize_markdown_output,
)
from scripts.render_prompt import build_prompt_package, get_report_mode_options, normalize_sector_name
from scripts.resolve_sector_focus import SECTOR_FOCUS_OPTIONS, build_focus_instruction

try:
    from plotly import express as px
except ImportError:  # pragma: no cover - optional dependency
    px = None


st.set_page_config(page_title="AI Signal Dashboard", layout="wide")
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
STREAMLIT_OUTPUT_DIR = REPO_ROOT / "out" / "streamlit"
STREAMLIT_STATE_PATH = REPO_ROOT / "data" / "streamlit_ui_state.json"
DEFAULT_AUDIENCE = "financial advisors and investment professionals"
DEFAULT_TIME_HORIZON = "1-3 years and 3-7 years"


def _get_db_version():
    return get_database_state_token()


def _load_streamlit_ui_state() -> dict[str, str]:
    try:
        return json.loads(STREAMLIT_STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _save_streamlit_ui_state(updates: dict[str, str]):
    current_state = _load_streamlit_ui_state()
    current_state.update(updates)
    STREAMLIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STREAMLIT_STATE_PATH.write_text(json.dumps(current_state, indent=2, sort_keys=True), encoding="utf-8")


def _restore_widget_value(widget_key: str, default_value: str, allowed_values: list[str] | None = None):
    if widget_key in st.session_state:
        return

    restored_value = _load_streamlit_ui_state().get(widget_key, default_value)
    if allowed_values is not None and restored_value not in allowed_values:
        restored_value = default_value
    st.session_state[widget_key] = restored_value


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


@st.cache_data(ttl=300)
def load_articles(week_start, db_version):
    _ = week_start
    _ = db_version
    article_data = get_weekly_articles()
    return article_data.get("articles", [])


@st.cache_data(ttl=300)
def load_articles_by_ids(article_ids, db_version):
    _ = db_version
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
    # Only use theme names as provided by the pipeline output; do not relabel or synthesize themes
    return df.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


@st.cache_data(ttl=300)
def load_runtime_clusters(week_start, api_key, db_version):
    _ = db_version
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set to compute runtime clusters.")

    articles = load_articles(week_start, db_version)
    if not articles:
        return build_cluster_dataframe([], week_start)

    client = get_openai_client(api_key)
    clusters = _prepare_clusters(cluster_articles(client, articles))
    save_weekly_clusters(week_start, clusters)
    return build_cluster_dataframe(clusters, week_start)


@st.cache_data(ttl=300)
def load_stored_clusters(week_start, db_version):
    _ = db_version
    stored_rows = get_weekly_clusters(week_start)
    if not stored_rows:
        return build_cluster_dataframe([], week_start)
    hydrated_clusters = []
    for row in stored_rows:
        article_ids = tuple(row.get("article_ids", []))
        articles = load_articles_by_ids(article_ids, db_version) if article_ids else []
        hydrated_clusters.append(
            {
                **dict(row),
                "articles": articles,
            }
        )
    return build_cluster_dataframe(hydrated_clusters, week_start)


@st.cache_data(ttl=300)
def load_weekly_digest(week_start, digest_type, db_version):
    _ = db_version
    rows = fetch_weekly_digests(digest_type=digest_type, limit=12)
    for row in rows:
        if str(row["week_start"]) == str(week_start):
            return row.get("content") or ""
    return ""


def load_clusters(week_start, api_key, db_version):
    # Only load stored clusters from the daily pipeline output; do not run runtime clustering
    return load_stored_clusters(week_start, db_version)


def _sector_labels() -> dict[str, str]:
    return {
        sector_key: str(sector_config["label"])
        for sector_key, sector_config in SECTOR_FOCUS_OPTIONS.items()
    }


def _industry_options(sector_key: str) -> list[tuple[str, str]]:
    industries = SECTOR_FOCUS_OPTIONS[sector_key]["industries"]
    options = [("Balanced", "balanced")]
    options.extend(
        (str(industry_config["label"]), industry_key)
        for industry_key, industry_config in industries.items()
    )
    return options


def _combine_special_instructions(focus_instruction: str, user_instructions: str) -> str:
    user_text = user_instructions.strip()
    if focus_instruction and user_text:
        return f"{focus_instruction} {user_text}"
    return focus_instruction or user_text


def _build_sector_report_output_paths(sector_key: str, report_mode: str, output_format: str) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    STREAMLIT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = STREAMLIT_OUTPUT_DIR / f"prompt_{sector_key}_{report_mode}_{timestamp}.md"
    extension = "html" if output_format == "html" else "md"
    report_path = STREAMLIT_OUTPUT_DIR / f"report_{sector_key}_{report_mode}_{timestamp}.{extension}"
    return prompt_path, report_path


def generate_sector_report_package(
    api_key: str,
    sector_key: str,
    industry_focus_key: str,
    report_mode: str,
    audience: str,
    time_horizon: str,
    style_notes: str,
    user_special_instructions: str,
    model: str,
    output_format: str,
) -> dict[str, object]:
    focus_instruction = build_focus_instruction(sector_key, industry_focus_key)
    effective_special_instructions = _combine_special_instructions(
        focus_instruction,
        user_special_instructions,
    )
    prompt_package = build_prompt_package(
        sector=sector_key,
        industry_focus=industry_focus_key,
        report_mode=report_mode,
        audience=audience,
        time_horizon=time_horizon,
        style_notes=style_notes,
        special_instructions=effective_special_instructions,
    )

    client = get_openai_client(api_key)
    generation_errors: list[str] = []

    try:
        report = generate_with_responses_api(
            client=client,
            prompt_package=prompt_package,
            model=model,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            output_format=output_format,
        )
    except Exception as exc:
        generation_errors.append(f"Responses API failed: {exc}")
        try:
            report = generate_with_chat_completions(
                client=client,
                prompt_package=prompt_package,
                model=model,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                output_format=output_format,
            )
        except Exception as fallback_exc:
            generation_errors.append(f"Chat Completions fallback failed: {fallback_exc}")
            raise RuntimeError("\n".join(generation_errors)) from fallback_exc

    if output_format == "html":
        report = normalize_html_output(report)
    else:
        report = normalize_markdown_output(report)

    prompt_path, report_path = _build_sector_report_output_paths(sector_key, report_mode, output_format)
    prompt_path.write_text(prompt_package, encoding="utf-8")
    report_path.write_text(report.rstrip() + "\n", encoding="utf-8")

    return {
        "prompt_package": prompt_package,
        "report": report,
        "prompt_path": prompt_path,
        "report_path": report_path,
        "effective_special_instructions": effective_special_instructions,
    }


def render_sector_report_launcher(api_key: str):
    st.subheader("Sector Report Launcher")
    st.caption("This launcher runs against your local repo checkout and writes prompt and report artifacts under out/streamlit.")

    sector_label_lookup = _sector_labels()
    sector_keys = list(sector_label_lookup.keys())
    _restore_widget_value("sector_report_sector", sector_keys[0], sector_keys)
    sector_key = st.selectbox(
        "Sector",
        options=sector_keys,
        format_func=lambda value: sector_label_lookup[value],
        key="sector_report_sector",
    )
    _save_streamlit_ui_state({"sector_report_sector": sector_key})

    industry_options = _industry_options(sector_key)
    industry_values = [value for _, value in industry_options]
    _restore_widget_value("sector_report_industry", "balanced", industry_values)
    industry_key = st.selectbox(
        "Industry Focus",
        options=industry_values,
        format_func=lambda value: next(label for label, option_value in industry_options if option_value == value),
        key="sector_report_industry",
    )
    _save_streamlit_ui_state({"sector_report_industry": industry_key})

    report_mode_options = get_report_mode_options()
    report_mode_values = list(report_mode_options.keys())
    _restore_widget_value("sector_report_mode", report_mode_values[0], report_mode_values)

    with st.form("sector_report_launcher_form"):
        report_mode = st.selectbox(
            "Report Mode",
            options=report_mode_values,
            format_func=lambda value: report_mode_options[value],
            key="sector_report_mode",
        )
        audience = st.text_input("Audience", value=DEFAULT_AUDIENCE)
        time_horizon = st.text_input("Time Horizon", value=DEFAULT_TIME_HORIZON)
        style_notes = st.text_area("Style Notes", value="", height=80)
        special_instructions = st.text_area("Additional Special Instructions", value="", height=120)

        controls_left, controls_right = st.columns(2)
        model = controls_left.text_input("Model", value=DEFAULT_MODEL)
        output_format = controls_right.selectbox(
            "Output Format",
            options=["html", "markdown"],
            index=0,
        )

        submit = st.form_submit_button("Generate Sector Report")

    if not submit:
        return

    if not api_key:
        st.error("OPENAI_API_KEY must be set in your local environment before generating a sector report.")
        return

    with st.spinner("Generating sector report from your local checkout..."):
        try:
            result = generate_sector_report_package(
                api_key=api_key,
                sector_key=sector_key,
                industry_focus_key=industry_key,
                report_mode=report_mode,
                audience=audience,
                time_horizon=time_horizon,
                style_notes=style_notes,
                user_special_instructions=special_instructions,
                model=model,
                output_format=output_format,
            )
            _save_streamlit_ui_state({"sector_report_mode": report_mode})
        except Exception as exc:
            st.error(f"Unable to generate the sector report: {exc}")
            return

    st.success("Sector report generated locally.")
    st.caption(f"Prompt saved to {result['prompt_path']}")
    st.caption(f"Report saved to {result['report_path']}")

    with st.expander("Effective Special Instructions", expanded=False):
        st.write(result["effective_special_instructions"] or "None provided.")

    with st.expander("Rendered Prompt Package", expanded=False):
        st.code(str(result["prompt_package"]), language="markdown")

    st.markdown("**Generated Report**")
    if output_format == "html":
        components.html(str(result["report"]), height=900, scrolling=True)
        mime_type = "text/html"
        download_name = f"sector_report_{normalize_sector_name(sector_key)}_{report_mode}.html"
    else:
        st.markdown(str(result["report"]))
        mime_type = "text/markdown"
        download_name = f"sector_report_{normalize_sector_name(sector_key)}_{report_mode}.md"

    st.download_button(
        "Download Generated Report",
        data=str(result["report"]),
        file_name=download_name,
        mime=mime_type,
    )


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

    st.title("AI Signal Command Center")
    st.caption("Weekly AI signal detection, thematic momentum, and sector report generation")

    api_key = os.getenv("OPENAI_API_KEY")
    workspace_options = ["Signal Dashboard", "Sector Report Launcher"]
    _restore_widget_value("workspace_view", workspace_options[0], workspace_options)
    view = st.radio(
        "Workspace",
        options=workspace_options,
        horizontal=True,
        key="workspace_view",
    )
    _save_streamlit_ui_state({"workspace_view": view})

    if view == "Sector Report Launcher":
        render_sector_report_launcher(api_key)
        return

    current_week = get_week_start()
    previous_week = current_week - timedelta(days=7)
    db_version = _get_db_version()

    try:
        cluster_df = load_clusters(current_week.isoformat(), api_key, db_version)
        previous_cluster_df = load_stored_clusters(previous_week.isoformat(), db_version)
        thematic_digest = load_weekly_digest(current_week.isoformat(), "thematic", db_version)
        wholesaler_digest = load_weekly_digest(current_week.isoformat(), "wholesaler", db_version)
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
    # Use only the theme as provided by the pipeline output; do not relabel or synthesize themes
    cluster_df = cluster_df.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    theme_options = ["All"] + sorted(cluster_df["theme_name"].dropna().astype(str).unique())
    _restore_widget_value("dashboard_theme_filter", "All", theme_options)
    selected_theme = st.selectbox(
        "Filter by Theme",
        theme_options,
        key="dashboard_theme_filter",
    )
    _save_streamlit_ui_state({"dashboard_theme_filter": selected_theme})

    if selected_theme != "All":
        cluster_df = cluster_df[cluster_df["theme_name"] == selected_theme].reset_index(drop=True)

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
        cluster_df["theme_name"].nunique()
    )

    theme_df = cluster_df.groupby("theme_name", as_index=False).agg(
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
            x="theme_name",
            y="avg_conviction",
            color="avg_velocity",
            title="Conviction by Theme",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    with st.expander("Latest Weekly Outputs", expanded=False):
        if thematic_digest:
            st.markdown("**Stored Thematic Digest**")
            st.text(thematic_digest)
        if wholesaler_digest:
            st.markdown("**Stored Wholesaler Digest**")
            st.text(wholesaler_digest)
        if not thematic_digest and not wholesaler_digest:
            st.caption("No stored weekly digest output found for the selected week yet.")

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
