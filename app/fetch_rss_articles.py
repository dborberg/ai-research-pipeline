import feedparser
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import time

logging.basicConfig(level=logging.INFO)

# High-signal + higher-frequency feeds (important)
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence",
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://www.marktechpost.com/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://arxiv.org/rss/cs.AI",
    "https://arxiv.org/rss/cs.LG",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.ft.com/technology?format=rss",
    "https://www.ft.com/companies?format=rss",
    "https://www.economist.com/science-and-technology/rss.xml",
    "https://www.economist.com/business/rss.xml",
    "https://www.therobotreport.com/feed/",
    "https://spectrum.ieee.org/rss/robotics/fulltext",
    "https://www.automate.org/rss",
    "https://roboticsandautomationnews.com/feed/",
    "https://www.designnews.com/rss.xml",
    "https://www.eetimes.com/feed/",
    # Company blogs
    "https://aws.amazon.com/blogs/aws/feed/",  # AWS Official Blog
    "https://blogs.nvidia.com/feed/",          # NVIDIA Blog
    "https://www.tesla.com/blog/feed",         # Tesla Blog
    "https://www.spacex.com/updates.xml",      # SpaceX Updates
    "https://blogs.microsoft.com/feed/",       # Microsoft Official Blog
    "https://www.semiconductors.org/feed/",
]

MAX_ENRICHED_ARTICLES = 20
MAX_RETURNED_ARTICLES = 40
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
    "The Economist": 3,
    "TechCrunch": 2,
    "VentureBeat": 2,
    "The Verge": 2,
    "arXiv": 2,
}
SOURCE_WEIGHT_ALIASES = {
    "ft.com": 3,
    "economist": 3,
    "reuters": 3,
    "techcrunch": 2,
    "venturebeat": 2,
    "the verge": 2,
    "arxiv": 2,
}


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


def fetch_rss_articles(feed_urls: List[str]) -> List[Dict[str, Any]]:
    articles = {}
    scraped_urls = set()
    enrichment_candidates = []
    total_feeds = len(feed_urls)
    successful_feeds = 0
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    print("=== RSS INGESTION START ===")
    print(f"Cutoff time (UTC): {cutoff}")

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

            # Filter for last 24 hours
            if published_dt < cutoff:
                continue

            title = entry.get("title", "")
            summary = _extract_summary(entry)
            priority_score = _compute_priority_score(title, summary)

            article = {
                "title": title,
                "link": link,
                "published": published_dt.isoformat(),
                "summary": summary,
                "content": "",
                "text": summary,
                "source": source,
                "source_weight": _get_source_weight(source),
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
            article.get("published", ""),
            len(article.get("summary", "")),
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
        unique_sources = len({article.get("source", "unknown") for article in theme_articles})
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
        selected_articles.extend(theme_articles[:2])

    MAX_PER_SOURCE = 3
    source_buckets = {}
    diversified_articles = []

    for article in selected_articles:
        source = article.get("source", "unknown")

        if source not in source_buckets:
            source_buckets[source] = []

        if len(source_buckets[source]) < MAX_PER_SOURCE:
            source_buckets[source].append(article)
            diversified_articles.append(article)
    sources = set(a["source"] for a in diversified_articles)
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
    print("Source distribution:")
    print(Counter(a["source"] for a in diversified_articles))
    print("Top 10 articles by signal_score:")
    for article in diversified_articles[:10]:
        print(article["title"], round(article["signal_score"], 2), article["source"])
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
        print(f"   Source: {article['source']}")
        print(f"   Published: {article['published']}")
        print(f"   Link: {article['link']}")
        print(f"   Summary: {article['summary'][:200]}...\n")


if __name__ == "__main__":
    main()
