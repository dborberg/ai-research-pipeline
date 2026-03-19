import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)

RSS_FEEDS = [
    'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
    'https://feeds.bbci.co.uk/news/technology/rss.xml',
    'https://www.theverge.com/rss/index.xml',
    'https://www.wired.com/feed/rss',
    'https://www.sciencedaily.com/rss/mind_brain/artificial_intelligence.xml',
    'https://www.technologyreview.com/feed/',
    'https://www.nature.com/subjects/artificial-intelligence/rss',
    'https://www.axios.com/feeds/artificial-intelligence.xml'
]

def fetch_rss_articles(feed_urls: List[str]) -> List[Dict[str, Any]]:
    articles = {}
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
            source = parsed.feed.get('title', url)
            for entry in parsed.entries:
                link = entry.get('link')
                if not link or link in articles:
                    continue
                published = entry.get('published_parsed')
                if published:
                    published_dt = datetime(*published[:6])
                else:
                    published_dt = now
                if published_dt < cutoff:
                    continue
                article = {
                    'title': entry.get('title', ''),
                    'link': link,
                    'published': published_dt.isoformat(),
                    'summary': entry.get('summary', entry.get('content', [{}])[0].get('value', '')),
                    'source': source
                }
                articles[link] = article
        except Exception as e:
            logging.error(f"Error parsing feed {url}: {e}")
    return list(articles.values())

def main():
    articles = fetch_rss_articles(RSS_FEEDS)
    for i, article in enumerate(articles[:5]):
        print(f"{i+1}. {article['title']} ({article['source']})")
        print(f"   Link: {article['link']}")
        print(f"   Published: {article['published']}")
        print(f"   Summary: {article['summary'][:200]}...\n")

if __name__ == "__main__":
    main()
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

# Reddit RSS feeds
REDDIT_URLS = [
    'https://www.reddit.com/r/artificial/new/.rss',
    'https://www.reddit.com/r/MachineLearning/new/.rss'
]

# NewsAPI endpoint
NEWSAPI_ENDPOINT = 'https://newsapi.org/v2/everything'

def fetch_rss_articles(feed_urls: List[str]) -> List[Dict[str, Any]]:
    articles = {}
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
            source = parsed.feed.get('title', url)
            for entry in parsed.entries:
                link = entry.get('link')
                if not link or link in articles:
                    continue
                published = entry.get('published_parsed')
                if published:
                    published_dt = datetime(*published[:6])
                else:
                    published_dt = now
                if published_dt < cutoff:
                    continue
                article = {
                    'title': entry.get('title', ''),
                    'link': link,
                    'published': published_dt.isoformat(),
                    'summary': entry.get('summary', entry.get('content', [{}])[0].get('value', '')),
                    'source': source
                }
                articles[link] = article
        except Exception as e:
            logging.error(f"Error parsing feed {url}: {e}")
    return list(articles.values())

def fetch_reddit_articles() -> List[Dict[str, Any]]:
    return fetch_rss_articles(REDDIT_URLS)

def fetch_newsapi_articles(api_key: Optional[str]) -> List[Dict[str, Any]]:
    if not api_key:
        return []
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    params = {
        'q': 'artificial intelligence OR machine learning',
        'from': cutoff.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sortBy': 'publishedAt',
        'language': 'en',
        'pageSize': 100,
        'apiKey': api_key
    }
    try:
        resp = requests.get(NEWSAPI_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get('articles', []):
            published_str = item.get('publishedAt')
            try:
                published_dt = datetime.strptime(published_str, '%Y-%m-%dT%H:%M:%SZ') if published_str else now
            except Exception:
                published_dt = now
            if published_dt < cutoff:
                continue
            article = {
                'title': item.get('title', ''),
                'link': item.get('url'),
                'published': published_dt.isoformat(),
                'summary': item.get('description', ''),
                'source': item.get('source', {}).get('name', 'NewsAPI')
            }
            articles.append(article)
        return articles
    except Exception as e:
        logging.error(f"Error fetching NewsAPI articles: {e}")
        return []

def fetch_all_articles(feed_urls: List[str], newsapi_key: Optional[str] = None) -> List[Dict[str, Any]]:
    all_articles = []
    seen_links = set()
    sources = [
        fetch_rss_articles(feed_urls),
        fetch_reddit_articles(),
        fetch_newsapi_articles(newsapi_key)
    ]
    for source_articles in sources:
        for article in source_articles:
            link = article.get('link')
            if link and link not in seen_links:
                all_articles.append(article)
                seen_links.add(link)
    return all_articles

def test_fetch_all_articles():
    sample_feeds = [
        'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
        'https://feeds.bbci.co.uk/news/technology/rss.xml',
        'https://www.theverge.com/rss/index.xml'
    ]
    newsapi_key = os.environ.get('NEWSAPI_KEY')
    articles = fetch_all_articles(sample_feeds, newsapi_key)
    for i, article in enumerate(articles[:5]):
        print(f"{i+1}. {article['title']} ({article['source']})")
        print(f"   Link: {article['link']}")
        print(f"   Published: {article['published']}")
        print(f"   Summary: {article['summary'][:200]}...\n")

if __name__ == "__main__":
    test_fetch_all_articles()
