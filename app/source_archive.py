import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_OUTPUT_DIR = REPO_ROOT / "outputs" / "daily"
DAILY_SNAPSHOT_DIR = DAILY_OUTPUT_DIR / "source_snapshots"
WEEKLY_OUTPUT_DIR = REPO_ROOT / "outputs" / "weekly"

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


def _weekly_digest_path(week_start, digest_type):
    return WEEKLY_OUTPUT_DIR / f"{_normalize_date(week_start)}_{digest_type}.txt"


def _month_bounds(report_month):
    month_start = datetime.strptime(str(report_month), "%Y-%m").date().replace(day=1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month_start


def _iter_fridays_in_month(report_month):
    month_start, next_month_start = _month_bounds(report_month)
    first_friday_offset = (4 - month_start.weekday()) % 7
    current_friday = month_start + timedelta(days=first_friday_offset)

    while current_friday < next_month_start:
        yield current_friday
        current_friday += timedelta(days=7)


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


def load_weekly_digest_file(week_start, digest_type):
    path = _weekly_digest_path(week_start, digest_type)
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


def load_daily_digests_for_month(report_month):
    month_start, next_month_start = _month_bounds(report_month)
    digests = []
    snapshot_date = month_start
    while snapshot_date < next_month_start:
        content = load_daily_digest_file(snapshot_date)
        if content:
            digests.append({"date": snapshot_date.isoformat(), "content": content})
        snapshot_date += timedelta(days=1)
    return digests


def load_weekly_digests_from_files(report_month, digest_types=("wholesaler", "thematic")):
    digests = []
    for week_start in _iter_fridays_in_month(report_month):
        for digest_type in digest_types:
            content = load_weekly_digest_file(week_start, digest_type)
            if content:
                digests.append(
                    {
                        "week_start": week_start.isoformat(),
                        "type": digest_type,
                        "content": content,
                    }
                )
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