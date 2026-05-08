import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta

from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import text

from app.cluster_schema import normalize_cluster_df
from app.branding import WEEKLY_THEMATIC_TITLE, WEEKLY_WHOLESALER_TITLE
from app.db import fetch_daily_digests, fetch_weekly_digests, get_engine, get_weekly_clusters, init_db, save_weekly_clusters, upsert_weekly_digest
from app.reporting import (
    call_chat_model,
    get_month_bounds,
    get_openai_client,
    get_latest_completed_friday,
    get_weekly_window_bounds,
    save_text_output,
)
from app.send_email import send_report
from app.velocity import apply_velocity_metrics, compute_velocity

WHOLESALER_TYPE = "wholesaler"
THEMATIC_TYPE = "thematic"
WHOLESALER_TITLE = WEEKLY_WHOLESALER_TITLE
THEMATIC_TITLE = WEEKLY_THEMATIC_TITLE
HIGH_SIGNAL_THRESHOLD = 8
DEFAULT_SCORE_THRESHOLD = 6
HIGH_SIGNAL_LIMIT = 25
MEDIUM_SIGNAL_LIMIT = 15
MAX_CLUSTERS = 10
PRACTICE_TIP_WORKFLOW_ROTATION = [
    "prospecting",
    "client communication",
    "meeting prep",
    "behavioral coaching",
    "practice management",
    "portfolio review",
    "client onboarding",
    "referral follow-up",
]
PRACTICE_TIP_CONCEPT_ROTATION = [
    "prospecting",
    "client messaging",
    "meeting prep",
    "practice operations",
    "client discovery",
    "portfolio exposure mapping",
    "behavioral coaching",
]
PRACTICE_TIP_CONCEPT_KEYWORDS = {
    "behavioral coaching": [
        "behavioral", "coaching", "fomo", "recency bias", "decision premortem",
        "pause script", "calm opening", "if this goes wrong", "if we do nothing",
        "buy, sell, or hold", "buy/sell/hold",
    ],
    "portfolio exposure mapping": [
        "portfolio review", "holdings", "sector weights", "concentration", "allocation",
        "exposure map", "exposure", "top 10 holdings", "portfolio", "review meeting",
    ],
    "client messaging": [
        "email", "follow-up", "followup", "talking point", "headline", "client-friendly",
        "script", "soundbite", "update", "conversation",
    ],
    "meeting prep": [
        "meeting prep", "meeting brief", "agenda", "prep notes", "discussion map",
        "review agenda", "call prep",
    ],
    "practice operations": [
        "crm", "workflow", "operations", "task", "staff", "practice management",
        "process", "operating", "checklist",
    ],
    "prospecting": [
        "prospect", "prospecting", "lead", "outreach", "prospective", "referral",
        "introduction", "center of influence", "coi", "network",
    ],
    "client discovery": [
        "discovery", "question", "questions", "first meeting", "onboarding", "new client",
        "discovery script",
    ],
}
GENERIC_THEME_TERMS = {
    "ai", "artificial", "intelligence", "theme", "themes", "trend", "trends",
    "innovation", "innovations", "technology", "technologies", "market", "markets",
    "signal", "signals", "weekly", "development", "developments", "update", "updates",
}
THEME_NOISE_TERMS = {
    "about", "after", "again", "also", "amid", "analyst", "analysts", "bbva",
    "because", "before", "being", "could", "fool", "from", "into", "made",
    "more", "over", "says", "than", "that", "their", "there", "these", "they",
    "this", "those", "what", "when", "where", "which", "while", "with", "would",
}

PRACTICE_TIP_WORKFLOW_KEYWORDS = {
    "prospecting": ["prospect", "prospecting", "lead", "outreach", "prospective"],
    "client communication": ["client-friendly", "follow-up", "followup", "update", "email", "talking point", "headline"],
    "meeting prep": ["meeting prep", "meeting brief", "review meeting", "prep sheet", "discussion map"],
    "behavioral coaching": ["behavioral", "coaching", "confidence", "panic", "decision", "risk tolerance"],
    "practice management": ["crm", "workflow", "operations", "task", "staff", "practice management"],
    "portfolio review": ["portfolio review", "holdings", "sector weights", "concentration", "exposure map", "exposure", "allocation"],
    "client onboarding": ["onboarding", "new client", "discovery", "welcome", "first meeting"],
    "referral follow-up": ["referral", "introduction", "center of influence", "coi", "network"],
}
REAL_WORLD_THEME_TERMS = {
    "adoption", "automation", "autonomous", "buildout", "capex", "chip", "chips",
    "cloud", "compliance", "data", "deployment", "electricity", "enterprise", "factory",
    "funding", "government", "grid", "inference", "infrastructure", "investment",
    "labor", "model", "nuclear", "policy", "power", "productivity", "regulation",
    "robot", "robotics", "semiconductor", "software", "spending", "supply", "tariff",
}


def _compute_cluster_strength(cluster):
    total_signal = float(cluster.get("total_signal") or 0)
    avg_signal = float(cluster.get("avg_signal") or 0)
    article_count = int(cluster.get("article_count") or len(cluster.get("articles", [])))
    return round(
        (total_signal * 0.6) +
        (avg_signal * 0.3) +
        (article_count * 0.1),
        2,
    )


def _generate_theme_id(theme_name, representative_summary=None):
    theme_name = (theme_name or "").strip().lower()
    summary = (representative_summary or "").strip().lower()
    hash_input = f"{theme_name}|{summary}" if summary else theme_name
    return hashlib.md5(hash_input.encode()).hexdigest()[:10]


def _extract_theme_terms(articles):
    token_counts = {}
    for article in articles:
        title = article.get("title") or ""
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", title.lower()):
            if len(token) < 3 or token in GENERIC_THEME_TERMS or token in THEME_NOISE_TERMS:
                continue
            token_counts[token] = token_counts.get(token, 0) + 1
    ranked_tokens = sorted(token_counts.items(), key=lambda item: (-item[1], item[0]))
    return [token.title() for token, _ in ranked_tokens[:4]]


def _extract_cluster_companies(articles):
    company_counts = {}
    for article in articles:
        for company in article.get("companies", []):
            normalized = str(company or "").strip()
            if not normalized:
                continue
            company_counts[normalized] = company_counts.get(normalized, 0) + 1
    ranked_companies = sorted(company_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    return [company for company, _ in ranked_companies[:4]]


def _theme_tokens(text):
    return [
        token for token in re.findall(r"[A-Za-z][A-Za-z0-9&\-]+", str(text or "").lower())
        if len(token) >= 3 and token not in GENERIC_THEME_TERMS and token not in THEME_NOISE_TERMS
    ]


def _cluster_support_terms(articles):
    support = set()
    repeated_title_terms = set()
    title_term_counts = {}

    for article in articles:
        title = article.get("title") or ""
        summary = article.get("summary") or ""
        advisor_relevance = article.get("advisor_relevance") or ""

        support.update(_theme_tokens(title))
        support.update(_theme_tokens(summary))
        support.update(_theme_tokens(advisor_relevance))

        for token in _theme_tokens(title):
            title_term_counts[token] = title_term_counts.get(token, 0) + 1

        for company in article.get("companies", []):
            support.update(_theme_tokens(company))

    repeated_title_terms = {token for token, count in title_term_counts.items() if count >= 2}
    return support, repeated_title_terms


def _is_valid_theme_name(theme_name, articles):
    cleaned_name = str(theme_name or "").strip()
    if not cleaned_name:
        return False

    tokens = _theme_tokens(cleaned_name)
    if not tokens:
        return False
    if len(tokens) < 2:
        return False

    support_terms, repeated_title_terms = _cluster_support_terms(articles)
    token_set = set(tokens)
    if not token_set & support_terms:
        return False

    has_company_anchor = any(
        token in token_set
        for company in _extract_cluster_companies(articles)
        for token in _theme_tokens(company)
    )
    has_repeated_anchor = bool(token_set & repeated_title_terms)
    has_real_world_anchor = bool(token_set & REAL_WORLD_THEME_TERMS)

    return has_company_anchor or has_repeated_anchor or has_real_world_anchor


def _select_best_theme_name(raw_name, articles):
    candidates = []

    raw_name = str(raw_name or "").strip()
    if raw_name:
        cleaned_words = [
            word for word in re.findall(r"[A-Za-z0-9&\-]+", raw_name)
            if word.lower() not in GENERIC_THEME_TERMS and word.lower() not in THEME_NOISE_TERMS
        ]
        if cleaned_words:
            candidates.append(" ".join(cleaned_words[:6]))

    companies = _extract_cluster_companies(articles)
    if len(companies) >= 2:
        candidates.append(" / ".join(companies[:2]))
    if companies:
        candidates.append(f"{companies[0]} Deployment")

    theme_terms = _extract_theme_terms(articles)
    if len(theme_terms) >= 2:
        candidates.append(" ".join(theme_terms[:4]))

    top_article = max(articles, key=lambda article: article.get("signal_score", 0), default={})
    title_words = [
        word for word in re.findall(r"[A-Za-z0-9&\-]+", top_article.get("title") or "")
        if word.lower() not in GENERIC_THEME_TERMS and word.lower() not in THEME_NOISE_TERMS
    ]
    if len(title_words) >= 2:
        candidates.append(" ".join(title_words[:4]))

    for candidate in candidates:
        if _is_valid_theme_name(candidate, articles):
            return candidate

    return ""


def _derive_theme_name(raw_name, articles):
    selected_name = _select_best_theme_name(raw_name, articles)
    if selected_name:
        return selected_name
    return ""


def _dedupe_and_relabel_clusters(clusters):
    deduped_clusters = []
    seen_names = set()
    seen_article_sets = []

    for cluster in clusters:
        articles = cluster.get("articles", [])
        article_ids = {article.get("id") for article in articles if article.get("id") is not None}
        if not article_ids:
            continue

        duplicate = False
        for prior_ids in seen_article_sets:
            overlap = len(article_ids & prior_ids) / max(1, min(len(article_ids), len(prior_ids)))
            if overlap >= 0.6:
                duplicate = True
                break
        if duplicate:
            continue

        cluster["theme_name"] = _derive_theme_name(cluster.get("theme_name"), articles)
        if not cluster["theme_name"]:
            continue
        normalized_name = cluster["theme_name"].lower()
        if normalized_name in seen_names:
            differentiators = _extract_theme_terms(articles)
            if differentiators:
                cluster["theme_name"] = f"{cluster['theme_name']} {differentiators[0]}"
            else:
                cluster["theme_name"] = f"{cluster['theme_name']} {len(deduped_clusters) + 1}"
            normalized_name = cluster["theme_name"].lower()

        if not _is_valid_theme_name(cluster["theme_name"], articles):
            continue

        seen_names.add(normalized_name)
        seen_article_sets.append(article_ids)
        deduped_clusters.append(cluster)

    return deduped_clusters


def _enrich_clusters(clusters):
    clusters = _dedupe_and_relabel_clusters(clusters)
    for cluster in clusters:
        cluster["theme_id"] = _generate_theme_id(
            cluster.get("theme_name"),
            cluster.get("representative_summary"),
        )
        cluster["total_signal"] = round(
            sum(float(article.get("signal_score") or 0) for article in cluster.get("articles", [])),
            2,
        )
        cluster["avg_signal"] = round(
            cluster["total_signal"] / max(len(cluster.get("articles", [])), 1),
            2,
        )
        cluster["weighted_article_count"] = round(
            sum(min(float(article.get("signal_score") or 0), 5) for article in cluster.get("articles", [])),
            2,
        )
        cluster["representative_article"] = max(
            cluster.get("articles", []),
            key=lambda article: article.get("signal_score", 0),
            default={},
        )
        cluster["top_articles"] = sorted(
            cluster.get("articles", []),
            key=lambda article: article.get("signal_score", 0),
            reverse=True,
        )[:5]
        cluster["cluster_strength"] = _compute_cluster_strength(cluster)
        trend = compute_conviction_trend(
            theme_id=cluster["theme_id"],
            current_article_count=int(cluster.get("article_count") or len(cluster.get("articles", []))),
            current_cluster_strength=cluster["cluster_strength"],
        )
        cluster["velocity"] = trend["velocity"]
        cluster["persistence"] = trend["persistence"]
        cluster["conviction_trend"] = trend["conviction_trend"]
        cluster["conviction_score"] = round(
            (cluster["cluster_strength"] * 0.5) +
            (float(cluster.get("avg_score") or 0) * 0.2) +
            (float(cluster.get("high_signal_ratio") or 0) * 10 * 0.2) +
            (max(int(cluster.get("velocity") or 0), 0) * 0.1),
            2,
        )
        if cluster["persistence"] >= 3 and cluster["conviction_score"] > 7:
            cluster["theme_type"] = "STRUCTURAL"
        elif cluster["velocity"] > 0 and cluster["conviction_score"] > 6:
            cluster["theme_type"] = "EMERGING"
        elif cluster["velocity"] < 0:
            cluster["theme_type"] = "FADING"
        else:
            cluster["theme_type"] = "TRANSIENT"
    return sorted(
        clusters,
        key=lambda cluster: (
            cluster["conviction_score"],
            cluster["velocity"],
            cluster["cluster_strength"],
        ),
        reverse=True,
    )


def compute_conviction_trend(theme_id, current_article_count=0, current_cluster_strength=None):
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("""
                SELECT week_start, article_count, avg_score, cluster_strength
                FROM weekly_clusters
                WHERE theme_id = :theme_id
                ORDER BY week_start DESC
                LIMIT 8
            """),
            {"theme_id": theme_id},
        ).mappings().all()

    if not rows:
        return {
            "velocity": int(current_article_count or 0),
            "persistence": 1 if current_article_count else 0,
            "conviction_trend": 0.0,
        }

    previous_article_count = int(rows[0].get("article_count") or 0)
    persistence = len(rows) + (1 if current_article_count else 0)

    strengths = [float(row.get("cluster_strength") or 0) for row in reversed(rows)]
    if current_cluster_strength is not None:
        strengths.append(float(current_cluster_strength))
    if len(strengths) >= 2:
        conviction_trend = round((strengths[-1] - strengths[0]) / (len(strengths) - 1), 2)
    else:
        conviction_trend = 0.0

    return {
        "velocity": current_article_count - previous_article_count,
        "persistence": persistence,
        "conviction_trend": conviction_trend,
    }


def _parse_json_response(raw_text, fallback):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw_text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return fallback


def _parse_companies(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [part.strip() for part in str(raw_value).split(",") if part.strip()]


def _dedupe_preserve_order(items, limit=None):
    result = []
    seen = set()
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if limit is not None and len(result) >= limit:
            break
    return result


def _with_weekly_report_header(title, week_start, content):
    if not content or not str(content).strip():
        return f"{title}\nWeek Ending {week_start.strftime('%B %d, %Y')}"
    return "\n".join([
        title,
        f"Week Ending {week_start.strftime('%B %d, %Y')}",
        "",
        str(content).strip(),
    ]).strip()


def get_weekly_articles(week_start, score_threshold=DEFAULT_SCORE_THRESHOLD):
    window_start, window_end = get_weekly_window_bounds(week_start)

    with get_engine().connect() as conn:
        high_signal_rows = conn.execute(
            text("""
                SELECT
                    id,
                    title,
                    source,
                    url,
                    published_at,
                    summary,
                    advisor_relevance,
                    ai_score,
                    companies
                FROM articles
                WHERE ai_score >= :high_signal_threshold
                                    AND published_at >= :window_start
                                    AND published_at < :window_end
                ORDER BY ai_score DESC, published_at DESC
                LIMIT :limit
            """),
            {
                "high_signal_threshold": HIGH_SIGNAL_THRESHOLD,
                                "window_start": window_start,
                                "window_end": window_end,
                "limit": HIGH_SIGNAL_LIMIT,
            },
        ).mappings().all()

        medium_signal_rows = conn.execute(
            text("""
                SELECT
                    id,
                    title,
                    source,
                    url,
                    published_at,
                    summary,
                    advisor_relevance,
                    ai_score,
                    companies
                FROM articles
                WHERE ai_score >= :score_threshold
                  AND ai_score < :high_signal_threshold
                                    AND published_at >= :window_start
                                    AND published_at < :window_end
                ORDER BY ai_score DESC, published_at DESC
                LIMIT :limit
            """),
            {
                "score_threshold": score_threshold,
                "high_signal_threshold": HIGH_SIGNAL_THRESHOLD,
                                "window_start": window_start,
                                "window_end": window_end,
                "limit": MEDIUM_SIGNAL_LIMIT,
            },
        ).mappings().all()

    high_signal = []
    for row in high_signal_rows:
        article = dict(row)
        article["signal_tier"] = "HIGH SIGNAL (PRIORITY - FOCUS HERE)"
        article["companies"] = _parse_companies(article.get("companies"))
        article["signal_score"] = float(article.get("signal_score") or article.get("ai_score") or 0)
        article["priority_score"] = float(article.get("priority_score") or 0)
        article["source_weight"] = float(article.get("source_weight") or 1)
        article["content_quality"] = float(article.get("content_quality") or len(article.get("summary") or ""))
        article["theme_hint"] = article.get("theme_hint") or " ".join((article.get("title") or "").split()[:5])
        high_signal.append(article)

    medium_signal = []
    for row in medium_signal_rows:
        article = dict(row)
        article["signal_tier"] = "MEDIUM SIGNAL"
        article["companies"] = _parse_companies(article.get("companies"))
        article["signal_score"] = float(article.get("signal_score") or article.get("ai_score") or 0)
        article["priority_score"] = float(article.get("priority_score") or 0)
        article["source_weight"] = float(article.get("source_weight") or 1)
        article["content_quality"] = float(article.get("content_quality") or len(article.get("summary") or ""))
        article["theme_hint"] = article.get("theme_hint") or " ".join((article.get("title") or "").split()[:5])
        medium_signal.append(article)

    articles = high_signal + medium_signal

    print(f"HIGH SIGNAL articles: {len(high_signal)}")
    print(f"MEDIUM SIGNAL articles: {len(medium_signal)}")
    print(
        f"Weekly pipeline using {len(articles)} high-quality articles "
        f"(score >= {score_threshold})"
    )

    return {
        "articles": articles,
        "high_signal": high_signal,
        "medium_signal": medium_signal,
    }


def _weekly_has_real_world_signal(article):
    text = f"{article.get('title') or ''} {article.get('summary') or ''} {article.get('advisor_relevance') or ''}"
    lowered = text.lower()
    proper_nouns = re.findall(r"\b(?:[A-Z][a-zA-Z0-9&\-]+(?:\s+[A-Z][a-zA-Z0-9&\-]+)*)", text)

    if any(term in lowered for term in ["framework", "study", "approach", "benchmark"]) and not any(
        term in lowered for term in ["deployment", "launch", "factory", "policy", "funding", "data center", "enterprise"]
    ):
        return False

    return (
        bool(proper_nouns)
        or any(term in lowered for term in [
            "capex", "funding", "buildout", "data center", "power", "chip", "fab", "grid",
            "policy", "regulation", "government", "lawmakers", "enterprise", "workflow",
            "productivity", "robot", "robotics", "autonomous", "drone", "deployment",
        ])
    )


def _weekly_event_priority(article):
    text = f"{article.get('title') or ''} {article.get('summary') or ''} {article.get('advisor_relevance') or ''}".lower()
    score = float(article.get("signal_score") or article.get("ai_score") or 0)

    if any(term in text for term in [
        "tesla", "nvidia", "microsoft", "amazon", "google", "meta", "openai", "softbank",
        "white house", "mas", "california",
    ]):
        score += 5
    if any(term in text for term in [
        "capex", "funding", "buildout", "investment", "factory", "fab", "data center", "campus",
        "power", "grid", "chip", "semiconductor",
    ]):
        score += 4
    if any(term in text for term in [
        "policy", "regulation", "government", "lawmakers", "compliance", "export controls",
    ]):
        score += 4
    if any(term in text for term in [
        "enterprise", "workflow", "productivity", "adoption", "deployment",
    ]):
        score += 3
    if any(term in text for term in [
        "robot", "robotics", "autonomous", "humanoid", "drone", "factory automation",
    ]):
        score += 3

    return score


def _build_wholesaler_event_context(article_data):
    articles = article_data.get("articles") or []
    selected = []
    seen_titles = set()

    ranked_articles = sorted(
        articles,
        key=lambda article: (
            _weekly_event_priority(article),
            article.get("published_at") or "",
        ),
        reverse=True,
    )

    for article in ranked_articles:
        if not _weekly_has_real_world_signal(article):
            continue
        normalized_title = re.sub(r"[^a-z0-9 ]+", "", (article.get("title") or "").lower())
        dedupe_key = " ".join(normalized_title.split()[:10])
        if not dedupe_key or dedupe_key in seen_titles:
            continue
        seen_titles.add(dedupe_key)
        selected.append(article)
        if len(selected) >= 18:
            break

    if not selected:
        return ""

    blocks = []
    for article in selected:
        blocks.append(
            "\n".join(
                [
                    f"TITLE: {article.get('title') or ''}",
                    f"SOURCE: {article.get('source') or ''}",
                    f"PUBLISHED_AT: {article.get('published_at') or ''}",
                    f"SIGNAL_SCORE: {article.get('signal_score') or article.get('ai_score') or ''}",
                    f"ADVISOR_RELEVANCE: {article.get('advisor_relevance') or ''}",
                    f"SUMMARY: {article.get('summary') or ''}",
                    f"COMPANIES: {', '.join(article.get('companies') or [])}",
                    f"EVENT_PRIORITY: {_weekly_event_priority(article):.2f}",
                ]
            )
        )

    return "\n\n".join(
        [
            "PRIMARY INPUT: CURATED REAL-WORLD WEEKLY EVENTS",
            "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks),
        ]
    )


def cluster_articles(client, articles):
    if not articles:
        return []

    article_lines = []
    for article in articles:
        article_lines.append(
            "\n".join(
                [
                    f"ARTICLE_ID: {article['id']}",
                    f"SIGNAL_TIER: {article['signal_tier']}",
                    f"AI_SCORE: {article.get('ai_score')}",
                    f"TITLE: {article.get('title') or ''}",
                    f"SUMMARY: {article.get('summary') or ''}",
                    f"ADVISOR_RELEVANCE: {article.get('advisor_relevance') or ''}",
                    f"COMPANIES: {', '.join(article.get('companies') or [])}",
                    f"SOURCE: {article.get('source') or ''}",
                ]
            )
        )

    system_prompt = """
You are an AI research clustering engine.
Group articles into 5–10 DISTINCT, NON-OVERLAPPING THEMES based on underlying economic or technological drivers.

Each theme must represent a real-world force such as:
- infrastructure constraints
- enterprise adoption shifts
- labor/productivity changes
- regulatory developments
- capital allocation trends

Avoid vague names like "AI trends" or "innovation".
Do not create clusters with fewer than 2 articles unless the signal is extremely strong.
At least 60% of the articles used to define each cluster must be HIGH SIGNAL when available.
Prioritize HIGH SIGNAL articles when determining cluster structure. Use MEDIUM SIGNAL only for supporting context.
Focus on patterns across multiple articles, not individual summaries.
Emphasize second-order effects and economic implications such as infrastructure demand, labor shifts, enterprise deployment, cost changes, supply chains, regulation, pricing power, and industry formation.
For each cluster, include a short investment_relevance explaining why this matters for markets, sectors, or advisors.
Return valid JSON only.
"""

    user_prompt = f"""
Cluster the following weekly AI research articles into 5 to 10 distinct themes.

Return JSON with this exact structure:
{{
  "clusters": [
    {{
      "theme_name": "short theme name",
      "article_ids": [1, 2, 3],
      "representative_summary": "2-3 sentence synthesis of the cluster",
      "key_companies": ["Company A", "Company B"],
      "investment_relevance": "1-2 sentence explanation of why this matters for markets, sectors, or advisors"
    }}
  ]
}}

Rules:
- Each article may appear in at most one cluster.
- Favor high-signal articles when assigning the core of a cluster.
- Use medium-signal articles only if they materially strengthen the same theme.
- Do not create vague umbrella themes.
- Do not create clusters with fewer than 2 articles unless the signal is extremely strong.
- At least 60% of the articles used to define each cluster must be HIGH SIGNAL when available.
- Theme names should be concise, specific, and useful for business readers.

ARTICLES:
{chr(10).join(article_lines)}
"""

    raw_response = call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=2600,
    )
    parsed = _parse_json_response(raw_response, {"clusters": []})
    raw_clusters = parsed.get("clusters", []) if isinstance(parsed, dict) else []

    article_map = {article["id"]: article for article in articles}
    assigned_ids = set()
    clusters = []

    for raw_cluster in raw_clusters:
        if not isinstance(raw_cluster, dict):
            continue

        article_ids = []
        for article_id in raw_cluster.get("article_ids", []):
            try:
                normalized = int(article_id)
            except Exception:
                continue
            if normalized in article_map and normalized not in assigned_ids and normalized not in article_ids:
                article_ids.append(normalized)

        cluster_articles_list = [article_map[article_id] for article_id in article_ids]
        if not cluster_articles_list:
            continue

        high_signal_count = sum(
            1 for article in cluster_articles_list
            if "HIGH SIGNAL" in article["signal_tier"]
        )
        article_count = len(cluster_articles_list)
        high_signal_ratio = round(high_signal_count / article_count, 2)

        if article_count < 2 and high_signal_ratio < 1.0:
            continue
        if article_count >= 2 and high_signal_ratio < 0.6 and len(article_map) >= article_count:
            continue

        avg_score = sum(article.get("ai_score") or 0 for article in cluster_articles_list) / article_count

        key_companies = raw_cluster.get("key_companies") or []
        if not isinstance(key_companies, list):
            key_companies = []
        if not key_companies:
            key_companies = _dedupe_preserve_order(
                [
                    company
                    for article in cluster_articles_list
                    for company in article.get("companies", [])
                ],
                limit=6,
            )

        cluster = {
            "theme_name": str(raw_cluster.get("theme_name") or "Untitled Theme").strip(),
            "articles": cluster_articles_list,
            "representative_summary": str(raw_cluster.get("representative_summary") or "").strip(),
            "key_companies": _dedupe_preserve_order(key_companies, limit=6),
            "investment_relevance": str(raw_cluster.get("investment_relevance") or "").strip(),
            "avg_score": round(avg_score, 2),
            "article_count": article_count,
            "high_signal_ratio": high_signal_ratio,
        }

        cluster["theme_name"] = _derive_theme_name(cluster.get("theme_name"), cluster_articles_list)
        if not cluster["theme_name"]:
            continue

        clusters.append(cluster)
        assigned_ids.update(article_ids)

    clusters = _dedupe_and_relabel_clusters(clusters)

    if not clusters:
        sorted_articles = sorted(
            articles,
            key=lambda article: (
                (article.get("signal_score") or 0),
                (article.get("ai_score") or 0),
                article.get("published_at") or "",
            ),
            reverse=True,
        )
        fallback_clusters = []
        index = 0
        while index < len(sorted_articles) and len(fallback_clusters) < MAX_CLUSTERS:
            cluster_slice = sorted_articles[index:index + 2]
            if len(cluster_slice) < 2:
                break
            article_count = len(cluster_slice)
            high_signal_count = sum(
                1 for article in cluster_slice
                if "HIGH SIGNAL" in article["signal_tier"]
            )
            high_signal_ratio = round(high_signal_count / article_count, 2)
            avg_score = sum(article.get("ai_score") or 0 for article in cluster_slice) / article_count
            fallback_clusters.append(
                {
                    "theme_name": _derive_theme_name("", cluster_slice),
                    "articles": cluster_slice,
                    "representative_summary": "Fallback cluster built from the strongest nearby weekly signals.",
                    "key_companies": _dedupe_preserve_order(
                        [
                            company
                            for article in cluster_slice
                            for company in article.get("companies", [])
                        ],
                        limit=6,
                    ),
                    "investment_relevance": "This cluster groups a concentrated set of weekly high-signal developments with potential implications for sectors, capital spending, or advisor conversations.",
                    "avg_score": round(avg_score, 2),
                    "article_count": article_count,
                    "high_signal_ratio": high_signal_ratio,
                }
            )
            index += 2
        clusters = _dedupe_and_relabel_clusters(
            [cluster for cluster in fallback_clusters if cluster.get("theme_name")]
        )

    clusters = clusters[:MAX_CLUSTERS]

    print(f"Clusters created: {len(clusters)}")
    return clusters


def extract_patterns(client, clusters):
    if not clusters:
        return {
            "emerging_trends": [],
            "converging_signals": [],
            "second_order_effects": [],
        }

    cluster_lines = []
    for index, cluster in enumerate(clusters, start=1):
        article_titles = [article.get("title") or "" for article in cluster["articles"][:5]]
        cluster_lines.append(
            "\n".join(
                [
                    f"THEME {index}: {cluster['theme_name']}",
                    f"AVG_SCORE: {cluster['avg_score']}",
                    f"ARTICLE_COUNT: {cluster['article_count']}",
                    f"HIGH_SIGNAL_RATIO: {cluster['high_signal_ratio']}",
                    f"SUMMARY: {cluster['representative_summary']}",
                    f"INVESTMENT_RELEVANCE: {cluster['investment_relevance']}",
                    f"KEY_COMPANIES: {', '.join(cluster['key_companies'])}",
                    f"REPRESENTATIVE_TITLES: {' | '.join(article_titles)}",
                ]
            )
        )

    system_prompt = """
You are an AI research pattern extraction engine.
Identify cross-cluster signals from weekly AI themes.
Prioritize high-signal clusters, focus on patterns across multiple articles, and emphasize second-order effects and economic implications.
Rank outputs by importance. The first item in each list must represent the most important signal for investors.
Avoid generic observations. Each pattern must reflect a real economic or strategic shift.
Return valid JSON only.
"""

    user_prompt = f"""
Review these weekly AI theme clusters and extract the strongest patterns.

Return JSON with this exact structure:
{{
  "emerging_trends": ["trend 1", "trend 2", "trend 3"],
  "converging_signals": ["signal 1", "signal 2", "signal 3"],
  "second_order_effects": ["effect 1", "effect 2", "effect 3"]
}}

Rules:
- Rank each list by importance for investors.
- The first item in each list must be the strongest signal.
- Avoid generic observations.
- Each item should describe a real economic or strategic shift.

CLUSTERS:
{chr(10).join(cluster_lines)}
"""

    raw_response = call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=1200,
    )
    parsed = _parse_json_response(
        raw_response,
        {
            "emerging_trends": [],
            "converging_signals": [],
            "second_order_effects": [],
        },
    )

    if not isinstance(parsed, dict):
        return {
            "emerging_trends": [],
            "converging_signals": [],
            "second_order_effects": [],
        }

    return {
        "emerging_trends": parsed.get("emerging_trends", []) or [],
        "converging_signals": parsed.get("converging_signals", []) or [],
        "second_order_effects": parsed.get("second_order_effects", []) or [],
    }


def _format_daily_digest_context(week_start):
    week_window_start = week_start - timedelta(days=6)
    digests = fetch_daily_digests(days=14, limit=14)
    digests = [
        digest for digest in digests
        if week_window_start.isoformat() <= str(digest["date"]) <= week_start.isoformat()
    ]
    if not digests:
        return ""

    digest_blocks = []
    for digest in reversed(digests):
        digest_blocks.append(
            "\n".join(
                [
                    f"DATE: {digest['date']}",
                    "DIGEST:",
                    digest["content"].strip(),
                ]
            )
        )

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(digest_blocks)


def _format_cluster_context(clusters, patterns):
    if not clusters:
        return ""

    sections = ["CLUSTERED THEMATIC INPUT:", ""]
    for index, cluster in enumerate(clusters, start=1):
        article_lines = []
        for article in cluster["articles"][:6]:
            article_lines.append(
                "\n".join(
                    [
                        f"  SIGNAL_TIER: {article['signal_tier']}",
                        f"  AI_SCORE: {article.get('ai_score')}",
                        f"  TITLE: {article.get('title') or ''}",
                        f"  SOURCE: {article.get('source') or ''}",
                        f"  SUMMARY: {article.get('summary') or ''}",
                    ]
                )
            )

        sections.extend(
            [
                f"THEME {index}: {cluster['theme_name']}",
                f"Theme Summary: {cluster['representative_summary']}",
                f"Investment Relevance: {cluster['investment_relevance']}",
                f"Average Score: {cluster['avg_score']}",
                f"Article Count: {cluster['article_count']}",
                f"High Signal Ratio: {cluster['high_signal_ratio']}",
                f"Key Companies: {', '.join(cluster['key_companies']) if cluster['key_companies'] else 'None noted'}",
                "Key Articles:",
                "\n\n".join(article_lines),
                "",
            ]
        )

    if any(patterns.values()):
        sections.append("CROSS-CLUSTER PATTERNS:")
        for label, items in [
            ("Emerging Trends", patterns.get("emerging_trends", [])),
            ("Converging Signals", patterns.get("converging_signals", [])),
            ("Second-Order Effects", patterns.get("second_order_effects", [])),
        ]:
            if not items:
                continue
            sections.append(label + ":")
            for index, item in enumerate(items, start=1):
                sections.append(f"{index}. {item}")
            sections.append("")

    return "\n".join(sections).strip()


def build_weekly_source_context(client, week_start, score_threshold=DEFAULT_SCORE_THRESHOLD):
    return _build_weekly_cluster_bundle(
        client,
        week_start,
        score_threshold=score_threshold,
    )["source_context"]


def _build_weekly_cluster_bundle(client, week_start, score_threshold=DEFAULT_SCORE_THRESHOLD):
    article_data = get_weekly_articles(week_start, score_threshold=score_threshold)
    clusters = _enrich_clusters(cluster_articles(client, article_data["articles"]))
    patterns = extract_patterns(client, clusters)
    clustered_context = _format_cluster_context(clusters, patterns)
    digest_context = _format_daily_digest_context(week_start)

    if clustered_context and digest_context:
        source_context = (
            "PRIMARY INPUT: CLUSTERED THEMES (HIGH SIGNAL PRIORITIZED)\n"
            f"{clustered_context}\n\n"
            "SUPPLEMENTAL INPUT: DAILY DIGESTS\n"
            f"{digest_context}"
        )
    elif clustered_context:
        source_context = f"PRIMARY INPUT: CLUSTERED THEMES (HIGH SIGNAL PRIORITIZED)\n{clustered_context}"
    elif digest_context:
        source_context = f"SUPPLEMENTAL INPUT: DAILY DIGESTS\n{digest_context}"
    else:
        source_context = ""

    return {
        "article_data": article_data,
        "clusters": clusters,
        "patterns": patterns,
        "source_context": source_context,
    }


def generate_wholesaler_weekly(client, source_context, week_start, article_data=None):
    curated_event_context = _build_wholesaler_event_context(article_data or {})
    primary_context = curated_event_context or source_context
    supplemental_context = ""
    if curated_event_context and source_context:
        supplemental_context = f"\n\nSUPPLEMENTAL INPUT: CLUSTERED THEMES AND DAILY DIGESTS\n{source_context}"

    recent_tip_history = _get_recent_practice_tip_history(week_start)
    required_workflow = _choose_practice_tip_workflow(week_start, recent_tip_history)
    required_concept = _choose_practice_tip_concept(week_start, recent_tip_history)
    recent_tip_constraints = _build_recent_practice_tip_constraints(recent_tip_history)
    if recent_tip_history:
        recent_tip_context = "\n".join(
            f"- {item['week_start']}: workflow={item['workflow']}; concept={item.get('concept', 'general')}; what={item['what']}"
            for item in recent_tip_history
        )
    else:
        recent_tip_context = "- No recent practice tips available."

    main_system_prompt = """
You are a senior AI research analyst writing a weekly AI digest for mutual fund wholesalers. The output must be immediately usable in advisor conversations.

Write in plain text only. No markdown. No bullet symbols. Numbered items are allowed where requested.

Use ONLY developments from the last 7 days. Anchor every point to a real-world event such as a company move, policy action, funding round, enterprise deployment, infrastructure buildout, or robotics deployment.

Do not write abstract summaries like:
AI continues to expand
AI demand suggests
This reflects a broader trend

Prefer this structure inside each item:
What happened
Why it matters for advisors
Implied takeaway

Keep interpretation concise and clearly tied to facts in the source material. Avoid performance claims, product recommendations, and unverified numbers.
"""

    main_user_prompt = f"""
Use the curated weekly source material below to produce a wholesaler-ready weekly digest.

Select only stories that meet at least one of these:
- named company or institution
- capital deployment such as capex, funding, or buildout
- policy or regulatory development
- enterprise adoption with measurable implication
- infrastructure expansion in power, chips, or data centers
- physical AI or robotics deployment

Reject vague or purely research-driven items unless they are tied to a real-world deployment or business decision.

Produce EXACTLY these sections in this exact order:

TOP 5 STORIES THIS WEEK
Write exactly 5 numbered items.
Each item must be 2 to 3 sentences.
Each item must include a specific event, why it matters for advisors, and source attribution in parentheses.

BEYOND THE MAG 7
Write 2 to 3 numbered items.
Each item must name a company, sector, or theme outside the obvious mega-cap AI names and explain why it matters now.

WHAT IS BEING DISRUPTED
Write exactly 3 numbered items.
One sentence each.
Each must reference a real signal from the week.

REGULATORY RADAR
Write 2 to 3 numbered items.
Reference only actual policy or regulatory developments from the week.
No speculation.

READY TO USE SOUNDBITES
Write exactly 5 numbered statements.
Use plain English, conversational tone, and make each one specific and timely.

QUESTIONS TO BRING TO YOUR CLIENTS
Write exactly 3 numbered questions.
Frame them as opportunities tied directly to this week's developments.

Do NOT include the AI PRACTICE TIP OF THE WEEK section in this response.

CONTENT:
{primary_context}{supplemental_context}
"""

    main_digest = call_chat_model(
        client,
        main_system_prompt,
        main_user_prompt,
        max_completion_tokens=1800,
    )

    tip_system_prompt = """
You are generating only the final section of a weekly AI digest for mutual fund wholesalers.
Write plain text only. Keep it practical, low-friction, and advisor-friendly.
Base the tip on the week's actual developments and the draft digest provided.
Do not repeat the rest of the digest.
"""

    tip_user_prompt = f"""
AI PRACTICE TIP OF THE WEEK

You are designing ONE highly practical, differentiated AI use case for financial advisors that a wholesaler can suggest in a client conversation.

CRITICAL REQUIREMENTS:
- Do NOT repeat common use cases like summarizing articles or writing basic emails
- Rotate across different advisor workflows each week such as prospecting, portfolio review, client communication, meeting prep, behavioral coaching, or practice management
- Also rotate across different idea families. If recent tips covered behavioral coaching, portfolio exposure mapping, client messaging, or meeting prep, do not return another close variant of that same concept
- The idea must feel specific, actionable, and new, not generic
- It should be something an advisor could actually try within 10 minutes
- Tie the use case loosely to this week's themes when relevant, but do not force it
- REQUIRED WORKFLOW FOR THIS WEEK: {required_workflow}
- REQUIRED IDEA FAMILY FOR THIS WEEK: {required_concept}
- Do NOT reuse or closely mimic any recent practice tip ideas listed below
- If a recent tip covered portfolio review, holdings review, concentration mapping, or exposure mapping, do not return another variant of that same concept
- If a recent tip covered behavioral coaching, pause scripts, premortems, FOMO control, or decision framing, do not return another variant of that same concept
- Prefer a different advisor job-to-be-done than the last 3 tips, even if the wording would be different

OUTPUT FORMAT:
Return exactly this section structure and labels:

AI PRACTICE TIP OF THE WEEK
What: <one-sentence description of the use case>

Why: <2 to 3 sentences explaining why this is useful for advisors specifically>

How to:
1. <one short, practical step>
2. <one short, practical step>
3. <one short, practical step>

Copy prompt: <a clean, ready-to-use prompt the advisor can paste into ChatGPT>
Guardrail: <1 to 2 sentences on compliance, accuracy, or appropriate use>

STYLE:
- Plain English
- Advisor-friendly, not technical
- Avoid hype
- Focus on usefulness and differentiation
- The How to section must use numbered steps, not plain paragraphs

Use the weekly digest draft below for context. Return only the section content in the format above.

WEEK START: {week_start}

RECENT PRACTICE TIP HISTORY TO AVOID:
{recent_tip_context}

RECENT PRACTICE TIP CONSTRAINTS:
{recent_tip_constraints}

DRAFT DIGEST:
{main_digest}
"""

    practice_tip = call_chat_model(
        client,
        tip_system_prompt,
        tip_user_prompt,
        max_completion_tokens=500,
    )

    return "\n\n".join([main_digest.strip(), practice_tip.strip()]).strip()


def _clean_thematic_output(content):
    cleaned = str(content or "").strip()
    replacements = [
        r"(?im)^\s*theme statement:\s*",
        r"(?im)^\s*mechanism of change:\s*",
        r"(?im)^\s*implication for advisors and their clients:\s*",
        r"(?im)^\s*implication:\s*",
    ]
    for pattern in replacements:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_practice_tip_text(content):
    text = str(content or "")
    if "AI PRACTICE TIP OF THE WEEK" not in text:
        return ""
    return text.split("AI PRACTICE TIP OF THE WEEK", 1)[1].strip()


def _extract_practice_tip_what(content):
    tip_text = _extract_practice_tip_text(content)
    if not tip_text:
        return ""

    match = re.search(r"(?im)^What:\s*(.+)$", tip_text)
    if match:
        return match.group(1).strip()

    first_line = tip_text.splitlines()[0].strip() if tip_text.splitlines() else ""
    return first_line


def _infer_practice_tip_workflow(text):
    normalized = str(text or "").lower()
    if not normalized:
        return "general"

    for workflow, keywords in PRACTICE_TIP_WORKFLOW_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return workflow

    return "general"


def _infer_practice_tip_concept(text):
    normalized = str(text or "").lower()
    if not normalized:
        return "general"

    for concept, keywords in PRACTICE_TIP_CONCEPT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return concept

    return "general"


def _get_recent_practice_tip_history(week_start, limit=4):
    rows = fetch_weekly_digests(digest_type=WHOLESALER_TYPE, limit=12)
    history = []

    for row in rows:
        if str(row["week_start"]) == week_start.isoformat():
            continue

        what_line = _extract_practice_tip_what(row["content"])
        if not what_line:
            continue

        history.append(
            {
                "week_start": str(row["week_start"]),
                "what": what_line,
                "workflow": _infer_practice_tip_workflow(what_line),
                "concept": _infer_practice_tip_concept(_extract_practice_tip_text(row["content"])),
            }
        )

        if len(history) >= limit:
            break

    return history


def _choose_practice_tip_workflow(week_start, recent_tip_history):
    recent_workflows = [item["workflow"] for item in recent_tip_history[:3] if item.get("workflow")]
    start_index = week_start.isocalendar().week % len(PRACTICE_TIP_WORKFLOW_ROTATION)
    rotated_workflows = (
        PRACTICE_TIP_WORKFLOW_ROTATION[start_index:] +
        PRACTICE_TIP_WORKFLOW_ROTATION[:start_index]
    )

    for workflow in rotated_workflows:
        if workflow not in recent_workflows:
            return workflow

    return rotated_workflows[0]


def _choose_practice_tip_concept(week_start, recent_tip_history):
    recent_concepts = [item["concept"] for item in recent_tip_history[:3] if item.get("concept")]
    start_index = week_start.isocalendar().week % len(PRACTICE_TIP_CONCEPT_ROTATION)
    rotated_concepts = (
        PRACTICE_TIP_CONCEPT_ROTATION[start_index:] +
        PRACTICE_TIP_CONCEPT_ROTATION[:start_index]
    )

    for concept in rotated_concepts:
        if concept not in recent_concepts:
            return concept

    return rotated_concepts[0]


def _build_recent_practice_tip_constraints(recent_tip_history):
    recent_workflows = [item["workflow"] for item in recent_tip_history[:3] if item.get("workflow")]
    recent_concepts = [item["concept"] for item in recent_tip_history[:3] if item.get("concept")]
    recent_what_lines = [item["what"] for item in recent_tip_history[:3] if item.get("what")]

    lines = []
    if recent_workflows:
        lines.append("- Avoid these recent workflow lanes: " + ", ".join(dict.fromkeys(recent_workflows)))
    if recent_concepts:
        lines.append("- Avoid these recent idea families: " + ", ".join(dict.fromkeys(recent_concepts)))
    if recent_what_lines:
        lines.append("- Do not reuse or lightly rephrase these recent tip ideas:")
        lines.extend(f"  - {item}" for item in recent_what_lines)

    if not lines:
        lines.append("- No recent workflow or idea-family constraints available.")

    return "\n".join(lines)


def generate_thematic_weekly(client, source_context):
    system_prompt = """
You are a senior AI research analyst condensing a week of daily AI briefings into a concise weekly thematic digest for mutual fund wholesalers. Your output will be sent as an email. Use plain text only, no markdown. Do not use bullet symbols such as hyphens, asterisks, or bullet characters. Numbered lists (1, 2, 3) are allowed.

Access the daily briefings by date. Use ONLY entries dated within the last 7 days. Ignore everything older than that.

Keep the tone professional but conversational, suitable for a busy wholesaler to read in under 5 minutes and immediately use in advisor meetings.

Do not simply summarize individual articles. Identify underlying economic or technological patterns that connect multiple stories, emphasizing mechanisms of change such as productivity improvements, cost reductions, infrastructure requirements, labor displacement, and new industry formation. Prefer second-order effects such as infrastructure demand, supply chain restructuring, regulatory reactions, labor shifts, pricing impacts, and competitive dynamics.

Compliance guardrails: avoid performance claims, avoid product-specific recommendations unless explicitly stated in the input, avoid unverified numbers, and clearly distinguish fact from interpretation.

Prioritize HIGH SIGNAL clusters when determining themes and insights.
Focus on patterns across multiple articles, not individual summaries.
Emphasize second-order effects such as:
- infrastructure demand
- pricing power shifts
- labor displacement
- capital allocation changes
- regulatory reactions
"""

    user_prompt = f"""
Use the output from the last 7 days of daily digests and synthesize it further into a thematic briefing. Do not simply summarize articles. Identify underlying economic or technological patterns that connect multiple stories. Focus on mechanisms of change such as productivity improvements, cost reductions, new infrastructure requirements, labor displacement, or new industry formation. When possible, synthesize multiple related articles into a single numbered item that explains the broader pattern rather than listing individual stories. Prefer insights that reveal second-order effects (infrastructure demand, industry restructuring, new supply chains, regulatory reactions, labor changes). Avoid speculative financial recommendations; keep commentary general and fact-based.

For each numbered item:
- weave together the core theme, mechanism of change, and advisor implication in normal prose
- do not prepend labels such as "Theme Statement:", "Mechanism of Change:", or "Implication:"
- write each item as a clean, natural paragraph or 2 to 3 connected sentences

Output the following sections exactly:

THE MOST IMPORTANT SHIFT THIS WEEK
Provide 2 to 3 numbered items.

WHERE AI IS QUIETLY EXPANDING
Provide 3 to 5 numbered items.

INFRASTRUCTURE SIGNALS
Provide 3 to 5 numbered items.

EARLY PRODUCTIVITY SIGNALS
Provide 3 to 4 numbered items.

SURPRISING OR UNDERAPPRECIATED DEVELOPMENT
Provide one short paragraph describing a development that could become a future Beyond the Horizon case study.

EMERGING BUSINESS MODELS
Provide 1 to 3 numbered items.

Prioritize HIGH SIGNAL clusters when determining themes and insights.
Focus on patterns across multiple articles, not individual summaries.
Emphasize second-order effects such as:
- infrastructure demand
- pricing power shifts
- labor displacement
- capital allocation changes
- regulatory reactions

CONTENT:
{source_context}
"""

    response = call_chat_model(
        client,
        system_prompt,
        user_prompt,
        max_completion_tokens=2200,
    )
    return _clean_thematic_output(response)


def generate_signal_command_brief(cluster_df, week_start):
    header = "\n".join(
        [
            "AI SIGNAL COMMAND BRIEF - Conviction & Momentum Report",
            f"Week Ending {week_start.isoformat()}",
            "",
            "Purpose:",
            "This report highlights the highest-conviction AI themes based on signal strength, momentum, and persistence.",
        ]
    )

    top_conviction = cluster_df.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).head(5)

    top_signal_lines = ["TOP CONVICTION SIGNALS", ""]
    for _, row in top_conviction.iterrows():
        top_signal_lines.extend(
            [
                str(row["theme_name"]),
                f"Conviction: {row['conviction_score']:.2f}",
                f"Strength: {row['cluster_strength']:.2f}",
                f"Momentum: {row['velocity_pct']:.0%}",
                f"Velocity: {int(row['velocity']):+d} article change",
                "Why It Matters:",
                str(row["investment_relevance"] or "No investment relevance summary was generated."),
                "",
            ]
        )

    breakouts = cluster_df[cluster_df["velocity_pct"] > 0.5].sort_values(
        ["velocity_pct", "velocity", "conviction_score"],
        ascending=[False, False, False],
    ).head(3)
    if breakouts.empty:
        breakouts = cluster_df.sort_values(
            ["velocity_pct", "velocity", "conviction_score"],
            ascending=[False, False, False],
        ).head(3)

    breakout_lines = [
        "ACCELERATING THEMES (BREAKOUTS)",
        "",
        "These themes are accelerating fastest relative to prior week.",
        "",
    ]
    for _, row in breakouts.iterrows():
        breakout_lines.append(
            f"{row['theme_name']}: Momentum {row['velocity_pct']:.0%}, velocity {int(row['velocity']):+d}. "
            f"{str(row['investment_relevance'] or 'Signal is strengthening against the prior-week base.').split('. ')[0].strip()}"
        )
    breakout_lines.append("")

    fading = cluster_df[cluster_df["velocity"] < 0].sort_values(
        ["velocity", "conviction_score"],
        ascending=[True, False],
    ).head(3)
    fading_lines = ["FADING SIGNALS", ""]
    if fading.empty:
        fading_lines.extend(
            [
                "No major theme showed week-over-week deterioration in this run.",
                "",
            ]
        )
    else:
        for _, row in fading.iterrows():
            fading_lines.extend(
                [
                    str(row["theme_name"]),
                    f"Velocity: {int(row['velocity']):+d}",
                    f"Previous Articles: {int(row['previous_article_count'])}",
                    "Interpretation:",
                    "Signal is weakening or being replaced.",
                    "",
                ]
            )

    structural = cluster_df.sort_values(
        ["conviction_score", "cluster_strength"],
        ascending=[False, False],
    ).head(2)["theme_name"].tolist()
    cyclical = cluster_df[
        (cluster_df["velocity_pct"] > 0) &
        (cluster_df["cluster_strength"] < cluster_df["cluster_strength"].median())
    ]["theme_name"].head(2).tolist()
    increasing = cluster_df[cluster_df["velocity"] > 0]["theme_name"].head(2).tolist()
    fading_names = fading["theme_name"].tolist()
    fading_label = ", ".join(fading_names) if fading_names else "last week's weaker themes"

    portfolio_lines = [
        "PORTFOLIO IMPLICATIONS",
        "",
        f"Structural strengthening is concentrated in {', '.join(structural) if structural else 'the top-ranked themes'}, where conviction and signal quality are both holding up.",
        f"Cyclical noise looks more likely in {', '.join(cyclical) if cyclical else 'lower-strength breakouts'}, where momentum is improving faster than underlying strength.",
        f"Conviction is increasing most clearly in {', '.join(increasing) if increasing else 'the current leaders'}, supported by rising article volume against the prior week.",
        f"Risk appears to be fading in {fading_label}, where attention is rolling off and replacement risk is increasing.",
        "",
    ]

    highest_conviction = top_conviction.iloc[0]["theme_name"] if not top_conviction.empty else "None"
    strongest_new_signal = breakouts.iloc[0]["theme_name"] if not breakouts.empty else "None"
    biggest_acceleration = breakouts.sort_values("velocity_pct", ascending=False).iloc[0]["theme_name"] if not breakouts.empty else "None"
    key_risk = fading.iloc[0]["theme_name"] if not fading.empty else "No material fading area"

    bottom_line = [
        "BOTTOM LINE",
        "",
        f"1. Highest conviction theme: {highest_conviction}",
        f"2. Most important new signal: {strongest_new_signal}",
        f"3. Biggest acceleration: {biggest_acceleration}",
        f"4. Key risk / fading area: {key_risk}",
    ]

    return "\n".join(
        [
            header,
            "",
            "\n".join(top_signal_lines).strip(),
            "",
            "\n".join(breakout_lines).strip(),
            "",
            "\n".join(fading_lines).strip(),
            "",
            "\n".join(portfolio_lines).strip(),
            "",
            "\n".join(bottom_line).strip(),
        ]
    ).strip()


def _generate_and_store_weekly_reports(client, week_start):
    weekly_bundle = _build_weekly_cluster_bundle(client, week_start, score_threshold=DEFAULT_SCORE_THRESHOLD)
    source_context = weekly_bundle["source_context"]

    if not source_context.strip():
        raise RuntimeError("No daily digests or scored articles available for the weekly pipeline")

    wholesaler_content = generate_wholesaler_weekly(
        client,
        source_context,
        week_start,
        article_data=weekly_bundle["article_data"],
    )
    thematic_content = generate_thematic_weekly(client, source_context)
    wholesaler_content = _with_weekly_report_header(WHOLESALER_TITLE, week_start, wholesaler_content)
    thematic_content = _with_weekly_report_header(THEMATIC_TITLE, week_start, thematic_content)
    save_weekly_clusters(week_start, weekly_bundle["clusters"])

    current_cluster_rows = get_weekly_clusters(week_start)
    previous_cluster_rows = get_weekly_clusters(week_start - timedelta(days=7))
    current_cluster_df = normalize_cluster_df(pd.DataFrame(current_cluster_rows))
    previous_cluster_df = normalize_cluster_df(pd.DataFrame(previous_cluster_rows))

    velocity_df = compute_velocity(current_cluster_df, previous_cluster_df)
    current_cluster_df = normalize_cluster_df(apply_velocity_metrics(current_cluster_df, velocity_df))
    signal_command_brief = generate_signal_command_brief(current_cluster_df, week_start)

    upsert_weekly_digest(week_start, WHOLESALER_TYPE, wholesaler_content)
    upsert_weekly_digest(week_start, THEMATIC_TYPE, thematic_content)
    upsert_weekly_digest(week_start, "signal_command_brief", signal_command_brief)

    save_text_output(
        "outputs/weekly",
        f"{week_start.isoformat()}_{WHOLESALER_TYPE}.txt",
        wholesaler_content,
    )
    save_text_output(
        "outputs/weekly",
        f"{week_start.isoformat()}_{THEMATIC_TYPE}.txt",
        thematic_content,
    )
    save_text_output(
        "outputs/weekly",
        f"{week_start.isoformat()}_signal_command_brief.txt",
        signal_command_brief,
    )

    return {
        WHOLESALER_TYPE: wholesaler_content,
        THEMATIC_TYPE: thematic_content,
        "signal_command_brief": signal_command_brief,
    }


def _get_stored_weekly_digest_content(week_start, digest_type):
    rows = fetch_weekly_digests(digest_type=digest_type, limit=12)
    for row in rows:
        if str(row["week_start"]) == week_start.isoformat():
            return row["content"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    args = parser.parse_args()

    load_dotenv()
    init_db()

    week_start = get_latest_completed_friday()
    digest_type_map = {
        "WHOLESALER": WHOLESALER_TYPE,
        "THEMATIC": THEMATIC_TYPE,
        "SIGNAL": "signal_command_brief",
    }
    subject_map = {
        "WHOLESALER": WHOLESALER_TITLE,
        "THEMATIC": THEMATIC_TITLE,
        "SIGNAL": f"[WEEKLY - SIGNAL] AI Signal Command Brief - Week Ending {week_start.isoformat()}",
    }

    if args.mode not in digest_type_map:
        raise RuntimeError("--mode must be one of WHOLESALER, THEMATIC, SIGNAL")

    content = None

    if args.mode == "WHOLESALER":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set")
        client = get_openai_client(api_key)
        generated_reports = _generate_and_store_weekly_reports(client, week_start)
        content = generated_reports[WHOLESALER_TYPE]
    else:
        digest_type = digest_type_map[args.mode]
        content = _get_stored_weekly_digest_content(week_start, digest_type)

        if content is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY must be set")
            client = get_openai_client(api_key)
            generated_reports = _generate_and_store_weekly_reports(client, week_start)
            content = generated_reports[digest_type]

    send_report(subject_map[args.mode], content)

    print(f"Saved weekly wholesaler digest for {week_start.isoformat()}")
    print(f"Saved weekly thematic digest for {week_start.isoformat()}")


if __name__ == "__main__":
    main()
