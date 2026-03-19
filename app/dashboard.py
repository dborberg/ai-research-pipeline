import json
import os
import sys
import subprocess
from collections import Counter
from datetime import datetime

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

from ai_synthesis import generate_ai_insights

st.set_page_config(layout="wide")

engine = create_engine("sqlite:///data/articles.db")


def list_daily_digests(digest_dir="outputs/daily"):
    """Return daily digest files grouped by month."""
    if not os.path.isdir(digest_dir):
        return {}

    digests = []
    for fname in sorted(os.listdir(digest_dir), reverse=True):
        if not fname.endswith(".txt"):
            continue
        # Expect filename like YYYY-MM-DD.txt
        try:
            date_part = fname.split(".txt")[0]
            date_obj = datetime.fromisoformat(date_part)
        except Exception:
            continue
        month_label = date_obj.strftime("%B %Y")
        digests.append((month_label, date_obj, os.path.join(digest_dir, fname)))

    grouped = {}
    for month_label, date_obj, path in digests:
        grouped.setdefault(month_label, []).append((date_obj, path))

    # Sort each month by date descending
    for month_label in grouped:
        grouped[month_label].sort(key=lambda x: x[0], reverse=True)

    return grouped


st.title("AI Research Dashboard")

# Daily digest links (sidebar)
if "selected_digest" not in st.session_state:
    st.session_state.selected_digest = None

with st.sidebar:
    st.header("Daily Digest")
    digests_by_month = list_daily_digests()
    if not digests_by_month:
        st.write("No digests available yet.")
    else:
        for month, items in digests_by_month.items():
            with st.expander(month, expanded=False):
                for date_obj, path in items:
                    label = date_obj.strftime("%Y-%m-%d")
                    cols = st.columns([2, 1])
                    with cols[0]:
                        st.write(label)
                    with cols[1]:
                        if st.button("View", key=f"view-{path}"):
                            st.session_state.selected_digest = path
                    with st.expander("Download", expanded=False):
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.download_button(
                            "Download",
                            data=content,
                            file_name=os.path.basename(path),
                            mime="text/plain",
                        )

    # Optional: Show last AI synthesis raw response for debugging
    synthesis_log = "logs/ai_synthesis_response.txt"
    if os.path.exists(synthesis_log):
        with st.expander("Last synthesis response (debug)", expanded=False):
            with open(synthesis_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
            st.text("".join(lines[:50]))

# Display selected digest if set
if st.session_state.selected_digest:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Selected Daily Digest")
    with col2:
        if st.button("Close Digest", key="close_digest"):
            st.session_state.selected_digest = None
            st.rerun()  # Refresh to hide the digest

    try:
        with open(st.session_state.selected_digest, "r", encoding="utf-8") as f:
            digest_text = f.read()
        st.text_area("", digest_text, height=500)
    except Exception as e:
        st.error(f"Failed to load digest: {e}")

# --- Refresh ingestion + enrichment button ----------------------------------
if st.button("Refresh ingestion"):
    from app.fetch_rss_articles import fetch_rss_articles, RSS_FEEDS
    from sqlalchemy import create_engine, text
    import time
    with st.spinner("Refreshing articles from RSS feeds..."):
        articles = fetch_rss_articles(RSS_FEEDS)
        engine = create_engine("sqlite:///data/ai_research.db")
        inserted = 0
        with engine.connect() as conn:
            for article in articles:
                conn.execute(text("""
                    INSERT OR IGNORE INTO articles (feedly_id, title, source, url, published_at, created_at)
                    VALUES (:feedly_id, :title, :source, :url, :published_at, :created_at)
                """), {
                    'feedly_id': article.get('link'),
                    'title': article.get('title'),
                    'source': article.get('source'),
                    'url': article.get('link'),
                    'published_at': article.get('published'),
                    'created_at': datetime.utcnow().isoformat()
                })
                inserted += 1
            conn.commit()
        st.success(f"Ingestion complete. {inserted} articles inserted.")
        st.success("Ingestion completed")
        st.text(ingest_result.stdout)

        with st.spinner("Enriching articles (AI summaries + metadata)..."):
            enrich_result = subprocess.run(
                [sys.executable, enrich_path],
                capture_output=True,
                text=True,
            )

        if enrich_result.returncode == 0:
            st.success("Enrichment completed")
            st.text(enrich_result.stdout)
        else:
            st.error("Enrichment failed")
            st.text(enrich_result.stderr)

st.markdown("---")

# Display last refresh time
try:
    with open("data/.last_refresh", "r") as f:
        last_refresh = f.read().strip()
    if last_refresh:
        from datetime import datetime
        dt = datetime.fromisoformat(last_refresh)
        st.caption(f"Last refreshed: {dt.strftime('%B %d, %Y at %I:%M %p')}")
except FileNotFoundError:
    st.caption("No refresh data available")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def parse_json_field(raw_value):
    """Safely parse JSON field; return list or empty list."""
    if pd.isna(raw_value) or not str(raw_value).strip():
        return []
    try:
        result = json.loads(str(raw_value))
        return result if isinstance(result, list) else []
    except Exception:
        return []


def list_daily_digests(digest_dir="outputs/daily"):
    """Return daily digest files grouped by month."""
    if not os.path.isdir(digest_dir):
        return {}

    digests = []
    for fname in sorted(os.listdir(digest_dir), reverse=True):
        if not fname.endswith(".txt"):
            continue
        # Expect filename like YYYY-MM-DD.txt
        try:
            date_part = fname.split(".txt")[0]
            date_obj = datetime.fromisoformat(date_part)
        except Exception:
            continue
        month_label = date_obj.strftime("%B %Y")
        digests.append((month_label, date_obj, os.path.join(digest_dir, fname)))

    grouped = {}
    for month_label, date_obj, path in digests:
        grouped.setdefault(month_label, []).append((date_obj, path))

    # Sort each month by date descending
    for month_label in grouped:
        grouped[month_label].sort(key=lambda x: x[0], reverse=True)

    return grouped


def get_score_icon(score):
    """Return icon/score for header based on ai_score."""
    if pd.isna(score):
        return "—"
    try:
        score_int = int(score)
    except Exception:
        return "—"

    if score_int >= 8:
        return f"🔥 {score_int}"
    elif score_int >= 5:
        return f"⚡ {score_int}"
    else:
        return f"• {score_int}"


def render_card(row):
    """Render a single article card (collapsed by default)."""
    title = row.get("title", "Untitled")
    score = row.get("ai_score")

    header_icon = get_score_icon(score)
    score_label = f"AI Score: {int(score)}/10" if pd.notna(score) else "AI Score: N/A"
    expander_label = f"{header_icon}  {title} — {score_label}"

    with st.expander(expander_label, expanded=False):
        summary = row.get("summary")
        if pd.notna(summary) and str(summary).strip():
            st.write(summary)

        themes_list = parse_json_field(row.get("themes"))
        if themes_list:
            st.markdown("**Themes**")
            st.markdown("\n".join(f"- {t}" for t in themes_list))

        companies_list = parse_json_field(row.get("companies"))
        if companies_list:
            st.markdown("**Companies**")
            st.markdown("\n".join(f"- {c}" for c in companies_list))

    st.divider()


# ============================================================================
# MAIN PAGE
# ============================================================================

try:
    df = pd.read_sql_query(
        """
        SELECT *
        FROM articles
        ORDER BY (ai_score IS NULL), ai_score DESC, id DESC
        """,
        engine,
    )

    # Ensure ai_score is numeric
    df["ai_score"] = pd.to_numeric(df["ai_score"], errors="coerce")

    st.write(f"**Total Articles:** {len(df)}")

    # ========================================================================
    # TOP AI INSIGHTS (Full Width)
    # ========================================================================

    st.header("Top AI Insights")

    ai_df = df[df["ai_score"].notna()].copy()
    ai_df["ai_score"] = pd.to_numeric(ai_df["ai_score"], errors="coerce")
    ai_df = ai_df.sort_values(["ai_score", "id"], ascending=[False, False])

    # Generate AI synthesis
    synthesis = generate_ai_insights(ai_df)
    # Dump synthesis result for debugging
    os.makedirs("logs", exist_ok=True)
    with open("logs/last_synthesis.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(synthesis, indent=2))

    # Display synthesized insights
    if synthesis.get("themes"):
        st.subheader("🎯 Top AI Themes This Week")
        for theme in synthesis["themes"]:
            st.markdown(f"- {theme}")

    if synthesis.get("top_stories"):
        st.subheader("📰 Top Stories")
        for story in synthesis["top_stories"]:
            if isinstance(story, dict) and "title" in story and "summary" in story:
                st.markdown(f"**{story['title']}**")
                st.write(story["summary"])
                st.markdown("---")

    if synthesis.get("soundbites"):
        st.subheader("💬 Key Soundbites")
        for bite in synthesis["soundbites"]:
            st.markdown(f"> {bite}")

    if synthesis.get("client_questions"):
        st.subheader("❓ Client Questions")
        for question in synthesis["client_questions"]:
            st.markdown(f"- {question}")

    st.markdown("---")

    # ========================================================================
    # TWO-COLUMN CARD GRID
    # ========================================================================

    st.header("All Articles")

    if len(df) > 0:
        col1, col2 = st.columns(2)

        for idx, (_, row) in enumerate(df.iterrows()):
            target_col = col1 if idx % 2 == 0 else col2

            with target_col:
                render_card(row)

    else:
        st.write("No articles yet")

except Exception as e:
    st.error(f"Error: {e}")
