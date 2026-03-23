def generate_daily_digest():
    import os
    from datetime import datetime, timedelta
    import re
    from sqlalchemy import create_engine, text

    from app.fetch_rss_articles import _get_theme_key, _get_source_weight

    DB_PATH = "sqlite:///data/ai_research.db"

    # -----------------------------
    # GET ARTICLES
    # -----------------------------
    def get_recent_articles(limit=60):
        engine = create_engine(DB_PATH)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT title, source, summary, url, ai_score
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

            # Skip empty/incomplete content per your rule
            if not title or not summary:
                continue

            articles.append({
                "title": title,
                "source": source,
                "summary": summary,
                "url": url,
                "ai_score": float(ai_score or 0),
            })

        return articles

    def _short_anchor(text, limit=8):
        words = [word for word in re.split(r"\s+", str(text or "").strip()) if word]
        return " ".join(words[:limit]).strip(" ,:-")

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

    def _coverage_categories(articles):
        categories = set()
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            if any(keyword in text for keyword in ["tesla", "nvidia", "microsoft", "amazon", "softbank", "musk"]):
                categories.add("company_event")
            if any(keyword in text for keyword in ["factory", "data center", "fab", "power", "grid"]):
                categories.add("infrastructure_project")
            if any(keyword in text for keyword in ["policy", "regulation", "white house", "mas", "california"]):
                categories.add("policy_regulation")
            if any(keyword in text for keyword in ["investment", "funding", "valuation", "capital", "market"]):
                categories.add("capital_markets")
        return categories

    def _extract_anchor_events(theme_name, articles):
        anchor_events = []
        for article in articles[:3]:
            title = article.get("title", "")
            summary = article.get("summary", "")
            proper_nouns = re.findall(r"\b(?:[A-Z][a-zA-Z0-9&\-]+(?:\s+[A-Z][a-zA-Z0-9&\-]+)*)", title)
            anchor = proper_nouns[0] if proper_nouns else _short_anchor(title)

            if any(keyword in title.lower() for keyword in ["framework", "model", "study", "approach"]):
                anchor = ""
            if anchor and "," in anchor:
                anchor = ""
            if anchor and not re.search(r"[A-Z]", anchor):
                anchor = ""

            if theme_name == "physical_ai":
                physical_terms = re.findall(
                    r"(robotics|robot|autonomous|humanoid|factory automation|industrial automation|uav|drone|vehicle)",
                    f"{title} {summary}",
                    flags=re.IGNORECASE,
                )
                if physical_terms:
                    anchor = f"{anchor} {physical_terms[0]}".strip()

            if anchor and anchor not in anchor_events:
                anchor_events.append(anchor)
            if len(anchor_events) >= 3:
                break
        return anchor_events

    def build_article_fallback_output(articles):
        section_map = [
            ("TOP THEMES", ["other", "emerging", "semis"]),
            ("ENTERPRISE AND LABOR", ["enterprise", "labor"]),
            ("INFRASTRUCTURE AND POWER", ["infrastructure", "semis"]),
            ("CAPITAL MARKETS AND INVESTMENT", ["capital_markets"]),
            ("REGULATION AND POLICY", ["policy"]),
            ("PHYSICAL AI AND ROBOTICS", ["physical_ai"]),
        ]

        theme_dict = {}
        for article in articles[:15]:
            theme_dict.setdefault(_get_theme_key(article), []).append(article)

        lines = []
        for section_title, themes in section_map:
            lines.append(section_title)
            section_written = 0
            for theme in themes:
                for article in theme_dict.get(theme, [])[:3]:
                    lines.append(
                        f"- {article['title']} ({article['source']})"
                    )
                    section_written += 1
                    if section_written >= 2:
                        break
                if section_written >= 2:
                    break
            if section_written == 0:
                lines.append("Nothing to report today.")
            lines.append("")
        return "\n".join(lines).strip()

    def synthesize_theme(theme_name, articles):
        sources = sorted({article["source"] for article in articles if article.get("source")})
        source_label = f"(Sources: {', '.join(sources[:4])})" if sources else "(Sources: Mixed)"
        confirmation_word = "reinforces" if len(sources) >= 2 else "suggests"
        anchors = _extract_anchor_events(theme_name, articles)
        anchor_text = ", ".join(anchors[:2]) if anchors else _short_anchor(articles[0].get("title", "AI catalyst"))

        templates = {
            "physical_ai": (
                f"{anchor_text} put physical AI into a concrete deployment context, and those developments {confirmation_word} that robotics and autonomous systems are moving into real operating environments. "
                "The theme is broadening beyond software into sensors, embedded compute, controls, and industrial automation platforms tied to factories, logistics, vehicles, and defense. "
                "That makes physical AI a real ecosystem buildout rather than a concept narrative. "
                "The investment implication is broader exposure across robotics enablers, industrial automation vendors, edge compute, and component suppliers. "
                f"{source_label}"
            ),
            "infrastructure": (
                f"{anchor_text} highlighted how AI infrastructure demand is colliding with real-world power, data center, and hardware constraints. "
                "Those developments expand into a broader theme in which AI scaling is increasingly constrained by physical infrastructure rather than model ambition alone. "
                "Cross-source coverage confirms that bottlenecks are showing up in energy, permitting, cooling, and hardware capacity at the same time. "
                "The investment implication is sustained demand for utilities, grid equipment, cooling, and compute infrastructure suppliers. "
                f"{source_label}"
            ),
            "enterprise": (
                f"{anchor_text} showed enterprise AI moving from experimentation toward workflow integration, productivity, and operating leverage. "
                "That expands into a broader adoption theme in which software spending is starting to favor practical deployment and measurable return on investment. "
                "Multiple catalysts now point to implementation discipline rather than AI theater. "
                "The investment implication is stronger support for application software, services, and workflow vendors that can translate AI into revenue or margin impact. "
                f"{source_label}"
            ),
            "capital_markets": (
                f"{anchor_text} brought AI capital formation and competitive positioning back into focus across public and private markets. "
                "That broadens into a wider financing and valuation theme in which leadership is moving beyond model builders into infrastructure, tools, and adjacent beneficiaries. "
                "Named catalysts in funding, project finance, or strategic buildout now confirm that AI exposure is spreading across the capital stack. "
                "The investment implication is a wider opportunity set across capital equipment, semis, private funding channels, and second-order AI beneficiaries. "
                f"{source_label}"
            ),
            "policy": (
                f"{anchor_text} made policy a live catalyst rather than a background risk. "
                "That expands into a more durable governance theme in which compliance, export controls, standards, and public-sector positioning shape adoption speed and competitive advantage. "
                "Specific agencies and policy bodies now confirm that regulatory timing matters to commercial winners and losers. "
                "The investment implication is higher sensitivity around globally exposed AI supply chains, platform providers, and regulated end markets. "
                f"{source_label}"
            ),
            "labor": (
                f"{anchor_text} put workforce change into concrete terms by linking AI adoption to hiring, productivity, and operating model redesign. "
                "That expands into a broader labor theme in which AI is reshaping how enterprises allocate work and capture efficiency gains. "
                "Specific catalysts now show that labor leverage is becoming one of the clearest channels through which AI affects margins. "
                "The investment implication is stronger focus on companies that can convert AI adoption into measurable productivity gains. "
                f"{source_label}"
            ),
            "other": (
                f"{anchor_text} showed that AI catalysts are widening beyond a narrow set of model and chip headlines. "
                "That expands into a broader market theme in which adjacent suppliers, adopters, and infrastructure players are becoming more relevant to the AI buildout. "
                "The named events in this cluster confirm that real-world adoption is spreading unevenly but meaningfully across the stack. "
                "The investment implication is a broader and more diversified set of AI-linked beneficiaries. "
                f"{source_label}"
            ),
        }

        return templates.get(theme_name, templates["other"])

    def build_theme_output(articles):
        theme_dict = {}
        for article in articles:
            theme = _get_theme_key(article)
            theme_dict.setdefault(theme, []).append(article)

        for theme_articles in theme_dict.values():
            theme_articles.sort(key=lambda article: article.get("ai_score", 0), reverse=True)

        print("Themes:", list(theme_dict.keys()))
        print("Physical AI present:", "physical_ai" in theme_dict)
        print("Articles per theme:", {k: len(v) for k, v in theme_dict.items()})
        if "physical_ai" not in theme_dict:
            print("No physical AI signals today")

        theme_scores = {}
        for theme, theme_articles in theme_dict.items():
            avg_score = sum(article.get("ai_score", 0) for article in theme_articles) / max(len(theme_articles), 1)
            unique_sources = len({article.get("source") for article in theme_articles if article.get("source")})
            theme_scores[theme] = avg_score + unique_sources * 0.5

        top_themes = [
            theme for theme, _ in sorted(
                theme_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]
        ]

        section_map = [
            ("TOP THEMES", [theme for theme in top_themes[:2]]),
            ("ENTERPRISE AND LABOR", ["enterprise", "labor"]),
            ("INFRASTRUCTURE AND POWER", ["infrastructure", "semis"]),
            ("CAPITAL MARKETS AND INVESTMENT", ["capital_markets"]),
            ("REGULATION AND POLICY", ["policy"]),
            ("PHYSICAL AI AND ROBOTICS", ["physical_ai"]),
        ]

        lines = []
        used_themes = set()
        for section_title, themes in section_map:
            lines.append(section_title)
            section_written = 0
            for theme in themes:
                if theme not in theme_dict or theme in used_themes:
                    continue
                lines.append(synthesize_theme(theme, theme_dict[theme][:4]))
                lines.append("")
                section_written += 1
                used_themes.add(theme)
            if section_written == 0:
                lines.append("Nothing to report today.")
                lines.append("")

        return "\n".join(lines).strip()

    articles = get_recent_articles()
    today = datetime.utcnow().strftime("%B %d, %Y")

    if not articles:
        return f"""Daily Riffs from the Gen AI Songbook
{today}

No relevant articles found in the last 24 hours.
"""
    high_signal_articles = [article for article in articles if _is_high_quality_signal(article)]
    fallback_triggered = (
        len(high_signal_articles) < 5
        or len(_coverage_categories(high_signal_articles)) < 2
    )
    print("High-quality signals:", len(high_signal_articles))
    print("Fallback triggered:", fallback_triggered)

    if fallback_triggered:
        content = build_article_fallback_output(articles)
    else:
        content = build_theme_output(high_signal_articles)

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return f"""Daily Riffs from the Gen AI Songbook
{today}

{content}
"""
