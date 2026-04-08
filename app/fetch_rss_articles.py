import feedparser
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import re
import time

from app.pipeline_window import get_pipeline_window

logging.basicConfig(level=logging.INFO)

FEED_BUCKETS = {
    "business_markets": [
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.ft.com/technology?format=rss",
        "https://www.ft.com/companies?format=rss",
        "https://www.economist.com/science-and-technology/rss.xml",
        "https://www.economist.com/business/rss.xml",
    ],
    "infrastructure_power": [
        "https://www.designnews.com/rss.xml",
        "https://www.eetimes.com/feed/",
        "https://www.semiconductors.org/feed/",
        "https://blogs.nvidia.com/feed/",
    ],
    "enterprise_labor": [
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.marktechpost.com/feed/",
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://blogs.microsoft.com/feed/",
    ],
    "policy_regulation": [
        "https://news.google.com/rss/search?q=AI+policy",
        "https://news.google.com/rss/search?q=AI+regulation",
        "https://news.google.com/rss/search?q=data+center+moratorium",
    ],
    "physical_ai_robotics": [
        "https://www.therobotreport.com/feed/",
        "https://spectrum.ieee.org/rss/robotics/fulltext",
        "https://www.automate.org/rss",
        "https://roboticsandautomationnews.com/feed/",
    ],
    "official_company": [
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://blogs.nvidia.com/feed/",
        "https://blogs.microsoft.com/feed/",
    ],
    "research": [
        "https://arxiv.org/rss/cs.AI",
    ],
    "google_gap_filler": [
        "https://news.google.com/rss/search?q=artificial+intelligence",
        "https://news.google.com/rss/search?q=AI+investment",
        "https://news.google.com/rss/search?q=AI+data+center",
        "https://news.google.com/rss/search?q=robotics+automation+AI",
    ],
}

RSS_FEEDS = []
for feed_urls in FEED_BUCKETS.values():
    for feed_url in feed_urls:
        if feed_url not in RSS_FEEDS:
            RSS_FEEDS.append(feed_url)

FEED_BUCKET_BY_URL = {
    feed_url: bucket_name
    for bucket_name, feed_urls in FEED_BUCKETS.items()
    for feed_url in feed_urls
}

MAX_ENRICHED_ARTICLES = 20
MAX_RETURNED_ARTICLES = 40
MAX_GOOGLE_GAP_FILLER_ARTICLES = 6
MAX_BUCKET_ARTICLES = {
    "policy_regulation": 10,
    "infrastructure_power": 10,
    "enterprise_labor": 10,
    "business_markets": 10,
    "physical_ai_robotics": 8,
    "official_company": 6,
    "research": 2,
    "google_gap_filler": MAX_GOOGLE_GAP_FILLER_ARTICLES,
}
REQUIRED_THEMES = [
    "infrastructure",
    "enterprise",
    "capital_markets",
    "policy",
    "physical_ai",
]
HIGH_QUALITY_SOURCES = {
    "Bloomberg": 3,
    "Reuters": 3,
    "Financial Times": 3,
    "Wall Street Journal": 3,
    "WSJ": 3,
    "The Economist": 3,
    "Data Center Dynamics": 3,
    "EE Times": 3,
    "The Robot Report": 3,
    "IEEE Spectrum": 3,
    "TechCrunch": 2,
    "VentureBeat": 2,
    "AI News": 2,
    "DesignNews": 2,
    "Robotics & Automation News": 2,
    "Business Wire": 2,
    "PR Newswire": 1,
    "arXiv": 1,
}
SOURCE_WEIGHT_ALIASES = {
    "bloomberg": 3,
    "reuters": 3,
    "ft.com": 3,
    "financial times": 3,
    "wsj": 3,
    "economist": 3,
    "data center dynamics": 3,
    "ee times": 3,
    "ieee spectrum": 3,
    "robot report": 3,
    "techcrunch": 2,
    "venturebeat": 2,
    "ai news": 2,
    "designnews": 2,
    "robotics & automation news": 2,
    "business wire": 2,
    "pr newswire": 1,
    "arxiv": 1,
}
STRONG_SOURCE_PATTERNS = [
    "bloomberg",
    "reuters",
    "financial times",
    "ft",
    "wsj",
    "wall street journal",
    "economist",
    "data center dynamics",
    "ee times",
    "ieee spectrum",
    "robot report",
]
MEDIUM_SOURCE_PATTERNS = [
    "techcrunch",
    "venturebeat",
    "ai news",
    "designnews",
    "robotics & automation news",
    "business wire",
    "globe and mail",
    "american banker",
    "mlex",
]
PRESS_RELEASE_PATTERNS = [
    "pr newswire",
    "business wire",
    "globenewswire",
    "newswire",
    "stock titan",
]
WEAK_AGGREGATOR_PATTERNS = [
    "benzinga",
    "tipranks",
    "yahoo finance",
    "investing.com",
    "news.futunn.com",
    "quiver quantitative",
    "simplywall.st",
]
LOCAL_SOURCE_PATTERNS = [
    "daily news",
    "daily herald",
    "gazette",
    "times",
    "post",
    "enterprise",
    "local",
    "wusf",
    "wsaz",
    "wpbf",
    "fox",
    "newscenter",
    "source",
    "independent",
]
OPINION_TITLE_PATTERNS = [
    r"\bopinion\b",
    r"\bviewpoint\b",
    r"\beditorial\b",
    r"\bguest essay\b",
    r"\bcolumn\b",
]


def _normalize_publisher_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _is_google_feed_source(source_name: str) -> bool:
    return "google news" in (source_name or "").lower()


def _matches_any_pattern(value: str, patterns: List[str]) -> bool:
    normalized_value = (value or "").lower()
    return any(pattern in normalized_value for pattern in patterns)


def _source_tier(source_name: str) -> str:
    normalized_source = (source_name or "").lower()
    if _matches_any_pattern(normalized_source, STRONG_SOURCE_PATTERNS):
        return "strong"
    if "arxiv" in normalized_source:
        return "research"
    if _matches_any_pattern(normalized_source, PRESS_RELEASE_PATTERNS):
        return "press_release"
    if _matches_any_pattern(normalized_source, WEAK_AGGREGATOR_PATTERNS):
        return "weak_aggregator"
    if _matches_any_pattern(normalized_source, MEDIUM_SOURCE_PATTERNS):
        return "medium"
    if _matches_any_pattern(normalized_source, LOCAL_SOURCE_PATTERNS):
        return "local"
    if _is_google_feed_source(source_name):
        return "google_feed"
    return "standard"


def _extract_original_publisher(entry: Dict[str, Any], feed_source: str) -> str:
    entry_source = entry.get("source")
    if hasattr(entry_source, "get"):
        source_title = _normalize_publisher_name(entry_source.get("title", ""))
        if source_title:
            return source_title

    title = entry.get("title", "") or ""
    if " - " in title:
        title_parts = [part.strip() for part in title.rsplit(" - ", 1)]
        if len(title_parts) == 2 and title_parts[1]:
            return _normalize_publisher_name(title_parts[1])

    summary = _extract_summary(entry)
    if "<font color=\"#6f6f6f\">" in summary:
        publisher_fragment = summary.split("<font color=\"#6f6f6f\">", 1)[1].split("</font>", 1)[0]
        publisher = _normalize_publisher_name(publisher_fragment)
        if publisher:
            return publisher

    return _normalize_publisher_name(feed_source)


def fetch_full_article(url):
    try:
        from newspaper import Article
    except ImportError as e:
        print("WARNING: newspaper3k dependency issue:", e)
        return ""

    try:
        article = Article(url)
        article.download()
        article.parse()

        text = article.text.strip()

        if len(text) < 500:
            return ""

        return text

    except Exception:
        return ""


def _extract_summary(entry: Dict[str, Any]) -> str:
    summary = entry.get("summary", "")
    if not summary and "content" in entry:
        summary = entry["content"][0].get("value", "")
    return summary or ""


def _compute_priority_score(title: str, summary: str) -> int:
    text = f"{title} {summary}".lower()
    score = 0

    # Core AI
    if "ai" in text:
        score += 1

    # Infrastructure (high value)
    if any(keyword in text for keyword in ["data center", "power", "grid", "electricity"]):
        score += 3

    # Semiconductors / hardware
    if any(keyword in text for keyword in ["nvidia", "semiconductor", "gpu", "chip"]):
        score += 2

    # Capex / buildout
    if any(keyword in text for keyword in ["capex", "spending", "investment", "buildout", "infrastructure"]):
        score += 2

    # Enterprise adoption / ROI
    if any(keyword in text for keyword in ["enterprise", "roi", "productivity", "automation"]):
        score += 2

    # Labor + macro impact
    if any(keyword in text for keyword in ["labor", "jobs", "hiring", "workforce"]):
        score += 1

    # Regulation / policy
    if any(keyword in text for keyword in ["regulation", "policy", "compliance", "governance"]):
        score += 2

    # Energy / utilities
    if any(keyword in text for keyword in ["utility", "energy demand", "nuclear", "grid capacity"]):
        score += 2

    if any(k in text for k in [
        "robot", "robotics", "autonomous", "humanoid",
        "factory automation", "industrial automation",
        "embodied ai", "edge ai", "sensor", "uav", "drone"
    ]):
        score += 2

    return score


def _get_source_weight(source_name: str) -> int:
    normalized_source = (source_name or "").lower()
    for source_key, weight in HIGH_QUALITY_SOURCES.items():
        if source_key.lower() in normalized_source:
            return weight
    for alias, weight in SOURCE_WEIGHT_ALIASES.items():
        if alias in normalized_source:
            return weight
    return 1


def _has_real_event_anchor(article: Dict[str, Any]) -> bool:
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return any(
        keyword in text for keyword in [
            "announced", "launch", "launched", "raised", "funding", "investment", "acquisition",
            "acquired", "approved", "bill", "senate", "house", "regulator", "lawsuit", "sued",
            "expands", "expansion", "signed", "deal", "partnership", "valuation", "bookings",
            "earnings", "capex", "$", "million", "billion",
        ]
    )


def _has_opinion_title(article: Dict[str, Any]) -> bool:
    title = article.get("title", "") or ""
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in OPINION_TITLE_PATTERNS)


def _source_quality_adjustment(article: Dict[str, Any]) -> float:
    original_publisher = article.get("original_publisher") or article.get("source") or ""
    source_name = article.get("source") or ""
    tier = _source_tier(original_publisher)
    theme = _get_theme_key(article)
    adjustment = 0.0

    if tier == "strong":
        adjustment += 1.25
    elif tier == "medium":
        adjustment += 0.5
    elif tier == "research":
        adjustment -= 0.35
    elif tier == "press_release":
        adjustment -= 0.4
        if _has_real_event_anchor(article):
            adjustment += 0.45
    elif tier == "weak_aggregator":
        adjustment -= 0.8
    elif tier == "local":
        adjustment -= 0.6
        if theme in {"infrastructure", "policy"} and _has_real_event_anchor(article):
            adjustment += 0.5
    elif tier == "google_feed":
        adjustment -= 0.35

    if _has_opinion_title(article):
        adjustment -= 0.25

    if _is_google_feed_source(source_name):
        adjustment -= 0.1

    return adjustment


def _compute_signal_score(article: Dict[str, Any]) -> float:
    signal_score = (
        article["priority_score"] * 0.5 +
        article["source_weight"] * 1.0 +
        min(article["content_quality"] / 1000, 2)
    )
    if len(article.get("text", "")) > 2000:
        signal_score += 1
    if "arxiv" in article.get("source", "").lower():
        signal_score *= 0.75
    signal_score += _source_quality_adjustment(article)
    return round(signal_score, 2)


def _normalize_title(title: str) -> str:
    return " ".join((title or "").lower().split())


def _get_theme_key(article):
    title = (article.get("title", "") or "").lower()
    text = f"{article.get('title','')} {article.get('summary','')}".lower()

    if any(k in title for k in [
        "robot", "robotics", "autonomous", "humanoid",
        "embodied ai", "drone", "uav", "factory automation"
    ]):
        return "physical_ai"

    if any(k in text for k in ["nvidia", "gpu", "chip", "semiconductor"]):
        return "semis"

    if any(k in text for k in ["data center", "power", "grid", "electricity"]):
        return "infrastructure"

    if any(k in text for k in ["enterprise", "software", "roi", "productivity", "automation"]):
        return "enterprise"

    if any(k in text for k in ["capex", "spending", "investment", "buildout", "markets", "valuation"]):
        return "capital_markets"

    if any(k in text for k in ["regulation", "policy", "government", "compliance"]):
        return "policy"

    if any(k in text for k in ["labor", "jobs", "hiring", "workforce"]):
        return "labor"

    if any(k in text for k in ["startup", "emerging", "agent", "foundation model", "launch"]):
        return "emerging"

    return "other"


def _is_similar_title(title_a: str, title_b: str) -> bool:
    normalized_a = _normalize_title(title_a)
    normalized_b = _normalize_title(title_b)
    if not normalized_a or not normalized_b:
        return False
    if normalized_a == normalized_b:
        return True

    tokens_a = set(normalized_a.split())
    tokens_b = set(normalized_b.split())
    overlap = len(tokens_a & tokens_b)
    shortest = max(1, min(len(tokens_a), len(tokens_b)))
    return overlap / shortest >= 0.8


def _dedupe_similar_titles(sorted_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped = []
    seen_titles = []

    for article in sorted_articles:
        title = article.get("title", "")
        if any(_is_similar_title(title, seen_title) for seen_title in seen_titles):
            continue
        deduped.append(article)
        seen_titles.append(title)

    return deduped


def fetch_rss_articles(feed_urls: List[str], window_start=None, window_end=None) -> List[Dict[str, Any]]:
    articles = {}
    scraped_urls = set()
    enrichment_candidates = []
    total_feeds = len(feed_urls)
    successful_feeds = 0
    resolved_window_start, resolved_window_end = get_pipeline_window(hours=24)
    if window_start is None:
        window_start = resolved_window_start
    if window_end is None:
        window_end = resolved_window_end
    now = window_end

    print("=== RSS INGESTION START ===")
    print(f"Window start (UTC): {window_start}")
    print(f"Window end (UTC): {window_end}")

    for url in feed_urls:
        print(f"\nParsing feed: {url}")

        parsed = None
        for attempt in range(2):
            try:
                parsed = feedparser.parse(url)
                break
            except Exception as e:
                if attempt == 1:
                    print(f"ERROR: Failed to parse {url}: {e}")
                else:
                    time.sleep(1)

        if parsed is None:
            continue

        if not parsed.entries:
            print(f"WARNING: No entries found for {url}")
            continue

        successful_feeds += 1
        source = parsed.feed.get("title", url)
        print(f"  → Feed title: {source}")
        print(f"  → Entries found: {len(parsed.entries)}")

        for entry in parsed.entries:
            link = entry.get("link")

            if not link or link in articles:
                continue

            # Handle published date safely
            published = entry.get("published_parsed")

            if published:
                published_dt = datetime(*published[:6])
            else:
                published_dt = now

            if published_dt < window_start or published_dt > window_end:
                continue

            title = entry.get("title", "")
            summary = _extract_summary(entry)
            priority_score = _compute_priority_score(title, summary)
            original_publisher = _extract_original_publisher(entry, source)

            article = {
                "title": title,
                "link": link,
                "published": published_dt.isoformat(),
                "summary": summary,
                "content": "",
                "text": summary,
                "source": source,
                "original_publisher": original_publisher,
                "feed_bucket": FEED_BUCKET_BY_URL.get(url, "other"),
                "source_weight": _get_source_weight(original_publisher or source),
                "priority_score": priority_score,
                "content_quality": len(summary),
                "signal_score": 0.0,
            }

            articles[link] = article
            if priority_score >= 1:
                enrichment_candidates.append(article)

    print(f"Feed health: {successful_feeds}/{total_feeds} feeds returned data")

    if len(articles) == 0:
        print("CRITICAL WARNING: No articles fetched across all feeds")
        return []

    sorted_candidates = sorted(
        enrichment_candidates,
        key=lambda article: (
            article.get("source_weight", 0),
            article.get("priority_score", 0),
            len(article.get("summary", "")),
            article.get("published", ""),
        ),
        reverse=True,
    )[:MAX_ENRICHED_ARTICLES]

    count_enriched = 0
    for article in sorted_candidates:
        link = article.get("link")
        if not link or link in scraped_urls:
            continue

        full_content = fetch_full_article(link)
        scraped_urls.add(link)
        time.sleep(1)

        if full_content:
            article["content"] = full_content
            article["text"] = full_content
            article["content_quality"] = len(article["text"])
            count_enriched += 1

    for article in articles.values():
        article["signal_score"] = _compute_signal_score(article)

    filtered_articles = []
    for article in articles.values():
        if len(article.get("text", "")) < 200:
            continue
        filtered_articles.append(article)

    if len(filtered_articles) < 5:
        print("WARNING: Low article count — proceeding but signal may be weak")

    sorted_articles = sorted(
        filtered_articles,
        key=lambda article: (
            article.get("signal_score", 0),
            article.get("priority_score", 0),
            article.get("source_weight", 0),
            article.get("content_quality", 0),
            article.get("published", ""),
        ),
        reverse=True,
    )
    sorted_articles = _dedupe_similar_titles(sorted_articles)

    theme_dict = {}
    for article in sorted_articles:
        theme = _get_theme_key(article)
        theme_dict.setdefault(theme, []).append(article)

    theme_scores = {}
    for theme, theme_articles in theme_dict.items():
        avg_signal_score = sum(article.get("signal_score", 0) for article in theme_articles) / max(len(theme_articles), 1)
        unique_sources = len({article.get("original_publisher") or article.get("source", "unknown") for article in theme_articles})
        theme_scores[theme] = avg_signal_score + unique_sources * 0.5

    ordered_themes = [theme for theme in REQUIRED_THEMES if theme in theme_dict]
    ordered_themes.extend(
        theme for theme, _ in sorted(
            theme_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        ) if theme not in ordered_themes
    )

    selected_articles = []
    for theme in ordered_themes:
        theme_articles = sorted(
            theme_dict.get(theme, []),
            key=lambda article: article.get("signal_score", 0),
            reverse=True,
        )
        selected_articles.extend(theme_articles)

    deduped_selected_articles = []
    seen_links = set()
    for article in sorted(
        selected_articles,
        key=lambda article: (
            article.get("signal_score", 0),
            article.get("priority_score", 0),
            article.get("source_weight", 0),
            article.get("content_quality", 0),
            article.get("published", ""),
        ),
        reverse=True,
    ):
        link = article.get("link")
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        deduped_selected_articles.append(article)

    MAX_PER_SOURCE = 2
    source_buckets = {}
    bucket_counts = Counter()
    diversified_articles = []

    for article in deduped_selected_articles:
        source = article.get("original_publisher") or article.get("source", "unknown")
        feed_bucket = article.get("feed_bucket", "other")

        if source not in source_buckets:
            source_buckets[source] = []

        bucket_limit = MAX_BUCKET_ARTICLES.get(feed_bucket)
        if bucket_limit is not None and bucket_counts[feed_bucket] >= bucket_limit:
            continue

        if len(source_buckets[source]) < MAX_PER_SOURCE and len(diversified_articles) < MAX_RETURNED_ARTICLES:
            source_buckets[source].append(article)
            diversified_articles.append(article)
            bucket_counts[feed_bucket] += 1
    sources = {a.get("original_publisher") or a.get("source", "unknown") for a in diversified_articles}
    if len(sources) < 3:
        print("WARNING: Low source diversity")

    print("Themes selected:", list(theme_dict.keys()))
    print("Physical AI present:", "physical_ai" in theme_dict)
    if "physical_ai" not in theme_dict:
        print("No physical AI signals today")
    print("Articles per theme:")
    print({k: len(v) for k, v in theme_dict.items()})
    print(f"Enriched articles: {count_enriched}")
    print(f"Total articles: {len(diversified_articles)}")
    print("Feed bucket distribution:")
    print(Counter(a.get("feed_bucket", "other") for a in diversified_articles))
    print("Source distribution:")
    print(Counter((a.get("original_publisher") or a["source"]) for a in diversified_articles))
    print("Top 10 articles by signal_score:")
    for article in diversified_articles[:10]:
        print(article["title"], round(article["signal_score"], 2), article.get("original_publisher") or article["source"])
    print(f"\n=== TOTAL NEW ARTICLES: {len(articles)} ===\n")

    return diversified_articles


def main():
    articles = fetch_rss_articles(RSS_FEEDS)

    print("\n=== SAMPLE OUTPUT ===\n")

    if not articles:
        print("NO ARTICLES RETURNED")
        return

    for i, article in enumerate(articles[:5]):
        print(f"{i+1}. {article['title']}")
        print(f"   Feed source: {article['source']}")
        print(f"   Original publisher: {article.get('original_publisher') or article['source']}")
        print(f"   Published: {article['published']}")
        print(f"   Link: {article['link']}")
        print(f"   Summary: {article['summary'][:200]}...\n")


if __name__ == "__main__":
    main()
