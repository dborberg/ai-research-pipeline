import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_OUTPUT_DIR = REPO_ROOT / "outputs" / "daily"
DAILY_SNAPSHOT_DIR = DAILY_OUTPUT_DIR / "source_snapshots"

_ARCHIVED_ARTICLE_FIELDS = [
    "id",
    "title",
    "source",
    "original_publisher",
    "summary",
    "url",
    "published_at",
    "companies",
    "advisor_relevance",
    "ai_score",
    "signal_score",
    "signal_tier",
    "priority_score",
    "source_weight",
    "content_quality",
    "theme_hint",
    "is_space_economy_related",
    "space_relevance",
    "space_ai_connection",
    "space_time_horizon",
    "space_investment_layer",
]


def _normalize_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _daily_snapshot_path(snapshot_date):
    return DAILY_SNAPSHOT_DIR / f"{_normalize_date(snapshot_date)}.json"


def _daily_digest_path(snapshot_date):
    return DAILY_OUTPUT_DIR / f"{_normalize_date(snapshot_date)}.txt"


def _archived_article_dedupe_key(article):
    return (
        str(article.get("url") or "").strip().lower(),
        str(article.get("title") or "").strip().lower(),
        str(article.get("published_at") or "").strip(),
    )


def _fallback_article_id(article):
    digest_source = "|".join(_archived_article_dedupe_key(article))
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()
    return -int(digest[:15], 16)


def _normalize_archived_article(article):
    archived = {field: article.get(field) for field in _ARCHIVED_ARTICLE_FIELDS}
    if archived.get("id") is None:
        archived["id"] = _fallback_article_id(archived)
    companies = archived.get("companies")
    if isinstance(companies, tuple):
        archived["companies"] = list(companies)
    return archived


def save_daily_source_snapshot(snapshot_date, articles):
    DAILY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": _normalize_date(snapshot_date),
        "article_count": len(articles or []),
        "articles": [_normalize_archived_article(article) for article in (articles or [])],
    }
    path = _daily_snapshot_path(snapshot_date)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def load_daily_source_snapshot(snapshot_date):
    path = _daily_snapshot_path(snapshot_date)
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return []
    return [_normalize_archived_article(article) for article in articles]


def load_daily_digest_file(snapshot_date):
    path = _daily_digest_path(snapshot_date)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_daily_digests_from_files(week_ending):
    digests = []
    for offset in range(6, -1, -1):
        snapshot_date = week_ending - timedelta(days=offset)
        content = load_daily_digest_file(snapshot_date)
        if content:
            digests.append({"date": snapshot_date.isoformat(), "content": content})
    return digests


def load_weekly_articles_from_daily_snapshots(week_ending):
    deduped_articles = []
    seen_keys = set()

    for offset in range(6, -1, -1):
        snapshot_date = week_ending - timedelta(days=offset)
        for article in load_daily_source_snapshot(snapshot_date):
            dedupe_key = _archived_article_dedupe_key(article)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            deduped_articles.append(article)

    return deduped_articles