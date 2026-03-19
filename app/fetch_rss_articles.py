import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

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
    "https://arxiv.org/rss/cs.LG"
]


def fetch_rss_articles(feed_urls: List[str]) -> List[Dict[str, Any]]:
    articles = {}
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    print("=== RSS INGESTION START ===")
    print(f"Cutoff time (UTC): {cutoff}")

    for url in feed_urls:
        print(f"\nParsing feed: {url}")

        try:
            parsed = feedparser.parse(url)

            if not parsed.entries:
                print("  → No entries found")
                continue

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

                summary = entry.get("summary", "")
                if not summary and "content" in entry:
                    summary = entry["content"][0].get("value", "")

                article = {
                    "title": entry.get("title", ""),
                    "link": link,
                    "published": published_dt.isoformat(),
                    "summary": summary,
                    "source": source,
                }

                articles[link] = article

        except Exception as e:
            logging.error(f"Error parsing feed {url}: {e}")

    print(f"\n=== TOTAL NEW ARTICLES: {len(articles)} ===\n")

    return list(articles.values())


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