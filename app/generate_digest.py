def generate_daily_digest():
    import os
    from datetime import datetime, timedelta
    import re
    from sqlalchemy import create_engine, text

    from app.fetch_rss_articles import _get_theme_key, _get_source_weight

    DB_PATH = "sqlite:///data/ai_research.db"
    COVERAGE_BUCKETS = {
        "infrastructure": ["data center", "power", "chip", "fab", "grid"],
        "enterprise": ["enterprise", "software", "workflow", "productivity"],
        "policy": ["policy", "regulation", "government", "lawmakers"],
        "capital_markets": ["investment", "ipo", "funding", "valuation"],
        "physical_ai": ["robot", "robotics", "autonomous", "drone", "factory automation"],
    }

    # -----------------------------
    # GET ARTICLES
    # -----------------------------
    def get_recent_articles(limit=60):
        engine = create_engine(DB_PATH)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT title, source, summary, url, ai_score, published_at
                FROM articles
                WHERE published_at >= :cutoff
                ORDER BY ai_score DESC, published_at DESC
                LIMIT :limit
            """), {"cutoff": cutoff, "limit": limit})

            rows = result.fetchall()

        articles = []
        for row in rows:
            title = row[0] or ""
            source = row[1] or ""
            summary = row[2] or ""
            url = row[3] or ""
            ai_score = row[4] or 0
            published_at = row[5] or ""

            # Skip empty/incomplete content per your rule
            if not title or not summary:
                continue

            articles.append({
                "title": title,
                "source": source,
                "summary": summary,
                "url": url,
                "ai_score": float(ai_score or 0),
                "published_at": published_at,
            })

        return articles

    def _short_anchor(text, limit=8):
        words = [word for word in re.split(r"\s+", str(text or "").strip()) if word]
        return " ".join(words[:limit]).strip(" ,:-")

    def compute_event_priority(article):
        score = 0
        text = f"{article['title']} {article['summary']}".lower()

        if any(k in text for k in [
            "tesla", "nvidia", "microsoft", "amazon",
            "google", "meta", "openai", "softbank"
        ]):
            score += 5

        if any(k in text for k in [
            "factory", "fab", "data center", "campus",
            "gigawatt", "power", "grid", "plant"
        ]):
            score += 4

        if any(k in text for k in [
            "white house", "government", "lawmakers",
            "regulation", "policy", "framework"
        ]):
            score += 4

        if any(k in text for k in [
            "investment", "funding", "ipo", "capex"
        ]):
            score += 3

        return score

    def classify_article_role(article):
        text = f"{article['title']} {article['summary']}".lower()

        if any(k in text for k in [
            "tesla", "nvidia", "microsoft", "amazon",
            "data center", "factory", "fab", "campus",
            "policy", "lawmakers", "government",
            "investment", "funding", "capex",
            "launch", "build", "deal"
        ]):
            return "EVENT"

        if any(k in (article.get("source") or "").lower() for k in [
            "arxiv", "research", "blog"
        ]):
            return "SUPPORTING"

        return "NOISE"

    def _is_high_quality_signal(article):
        title = (article.get("title") or "").lower()
        source_weight = _get_source_weight(article.get("source") or "")
        company_or_event_keywords = [
            "tesla", "nvidia", "microsoft", "amazon",
            "factory", "data center", "policy", "investment",
        ]
        return (
            source_weight >= 2
            or any(keyword in title for keyword in company_or_event_keywords)
        )

    def _is_bad_anchor(article):
        title = article.get("title", "") or ""
        lowered = title.lower()
        proper_nouns = re.findall(r"\b(?:[A-Z][a-zA-Z0-9&\-]+(?:\s+[A-Z][a-zA-Z0-9&\-]+)*)", title)
        return (
            len(title.split()) < 5
            or not proper_nouns
            or any(keyword in lowered for keyword in ["framework", "study", "approach", "model"])
        )

    def _article_has_specificity(article):
        text = f"{article.get('title', '')} {article.get('summary', '')}"
        proper_nouns = re.findall(r"\b(?:[A-Z][a-zA-Z0-9&\-]+(?:\s+[A-Z][a-zA-Z0-9&\-]+)*)", text)
        return bool(proper_nouns)

    def _article_sort_key(article):
        return (
            article.get("final_score", article.get("ai_score", 0)),
            article.get("published_at", ""),
        )

    def _dedupe_articles(articles):
        deduped = []
        seen = set()
        for article in articles:
            title = re.sub(r"[^a-z0-9 ]+", "", (article.get("title") or "").lower())
            key = " ".join(title.split()[:10])
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(article)
        return deduped

    def _rewrite_article_bullet(article):
        title = (article.get("title") or "").strip().rstrip(".")
        summary = (article.get("summary") or "").strip()
        source = article.get("source") or "Unknown"
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        detail = ""
        banned_phrases = [
            "ai demand suggests",
            "ai continues to",
            "ai developments indicate",
            "this reflects a broader trend",
        ]
        for sentence in sentences:
            cleaned = sentence.strip()
            lowered = cleaned.lower()
            if not cleaned:
                continue
            if any(phrase in lowered for phrase in banned_phrases):
                continue
            detail = cleaned.rstrip(".")
            break
        if not detail:
            detail = "This matters because the development creates a tangible AI-linked catalyst for investors"
        return f"• {title}\n→ {detail} (Source: {source})"

    def build_section_output(section_title, articles, min_items=3, max_items=5):
        lines = [section_title]
        selected = _dedupe_articles(sorted(articles, key=_article_sort_key, reverse=True))
        selected = [
            article for article in selected
            if _article_has_specificity(article) and not _is_bad_anchor(article)
        ][:max_items]
        if len(selected) < 1:
            lines.append("Nothing to report today.")
            lines.append("")
            return "\n".join(lines)
        for article in selected:
            lines.append(_rewrite_article_bullet(article))
        lines.append("")
        return "\n".join(lines)

    def build_article_output(articles, low_confidence=False):
        section_map = [
            ("TOP STORIES", ["EVENT", "SUPPORTING", "NOISE"]),
            ("ENTERPRISE AND LABOR", ["enterprise", "labor"]),
            ("INFRASTRUCTURE AND POWER", ["infrastructure", "semis"]),
            ("CAPITAL MARKETS AND INVESTMENT", ["capital_markets"]),
            ("REGULATION AND POLICY", ["policy"]),
            ("PHYSICAL AI AND ROBOTICS", ["physical_ai"]),
        ]

        theme_dict = {}
        top_story_candidates = []
        for article in articles[:20]:
            theme = _get_theme_key(article)
            theme_dict.setdefault(theme, []).append(article)
            top_story_candidates.append(article)

        lines = []
        if low_confidence:
            lines.extend([
                "LOW-CONFIDENCE MODE",
                "Real-world event coverage was thin today, so this view is article-driven.",
                "",
            ])
        lines.append(build_section_output("TOP STORIES", top_story_candidates[:8], max_items=5))
        for section_title, themes in section_map[1:]:
            section_articles = []
            for theme in themes:
                section_articles.extend(theme_dict.get(theme, []))
            lines.append(build_section_output(section_title, section_articles))
        return "\n".join(lines).strip()

    articles = get_recent_articles()
    today = datetime.utcnow().strftime("%B %d, %Y")

    if not articles:
        return f"""Daily Riffs from the Gen AI Songbook
{today}

No relevant articles found in the last 24 hours.
"""
    prepared_articles = []
    for article in articles:
        article = article.copy()
        article["source_weight"] = _get_source_weight(article.get("source") or "")
        article["event_priority"] = compute_event_priority(article)
        article["final_score"] = article["ai_score"] + article["event_priority"]
        article["role"] = classify_article_role(article)
        prepared_articles.append(article)

    event_articles = [
        article for article in prepared_articles
        if article["role"] == "EVENT" and not _is_bad_anchor(article)
    ]
    supporting_articles = [
        article for article in prepared_articles
        if article["role"] == "SUPPORTING"
    ]
    candidate_articles = event_articles + supporting_articles
    top_events = sorted(
        candidate_articles,
        key=_article_sort_key,
        reverse=True,
    )[:8]

    coverage_status = {}
    for bucket, keywords in COVERAGE_BUCKETS.items():
        matched = any(
            any(keyword in f"{article['title']} {article['summary']}".lower() for keyword in keywords)
            for article in top_events
        )
        if not matched:
            for article in sorted(
                candidate_articles,
                key=_article_sort_key,
                reverse=True,
            ):
                text = f"{article['title']} {article['summary']}".lower()
                if any(keyword in text for keyword in keywords) and article not in top_events:
                    top_events.append(article)
                    matched = True
                    break
        coverage_status[bucket] = "OK" if matched else "MISSING"
        if not matched:
            print("Missing coverage:", bucket)

    fallback_triggered = (
        len(event_articles) == 0
        or all(article.get("role") == "SUPPORTING" for article in top_events)
        or len(top_events) == 0
    )
    fallback_articles = sorted(
        prepared_articles,
        key=_article_sort_key,
        reverse=True,
    )[:15]
    fallback_low_confidence = (
        len(event_articles) == 0
        or all(article.get("role") != "EVENT" for article in top_events)
    )
    print("Event articles:", len(event_articles))
    print("Supporting articles:", len(supporting_articles))
    print("Fallback triggered:", fallback_triggered)
    print("Top story roles:", [article["role"] for article in top_events or fallback_articles[:8]])
    print("Top events selected:")
    for article in top_events:
        print(article["title"], article["final_score"])
    print("Coverage check:")
    for bucket in COVERAGE_BUCKETS:
        print(bucket, coverage_status[bucket])

    selected_articles = fallback_articles if fallback_triggered else top_events + [
        article for article in candidate_articles if article not in top_events
    ]
    content = build_article_output(selected_articles, low_confidence=fallback_low_confidence)

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return f"""Daily Riffs from the Gen AI Songbook
{today}

{content}
"""
