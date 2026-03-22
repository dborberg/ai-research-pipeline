def generate_daily_digest():
    import os
    from datetime import datetime, timedelta
    from sqlalchemy import create_engine, text
    from collections import Counter

    from app.fetch_rss_articles import _get_theme_key

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

    def synthesize_theme(theme_name, articles):
        sources = sorted({article["source"] for article in articles if article.get("source")})
        source_label = f"(Sources: {', '.join(sources[:4])})" if sources else "(Sources: Mixed)"
        confirmation_word = "reinforces" if len(sources) >= 2 else "suggests"

        templates = {
            "physical_ai": (
                f"Physical AI is moving closer to real-world deployment, with robotics, autonomous systems, and industrial automation signals {confirmation_word} a broader shift beyond software-only AI. "
                "This matters because AI demand is extending into sensors, embedded compute, controls, and automation platforms tied to factories, logistics, and defense. "
                "The investment implication is broader exposure across robotics enablers, industrial automation vendors, edge compute, and component suppliers. "
                f"{source_label}"
            ),
            "infrastructure": (
                f"AI infrastructure demand {confirmation_word} continued pressure on power, data center, and hardware capacity. "
                "This matters because AI scaling is increasingly constrained by physical infrastructure rather than model ambition alone. "
                "The investment implication is sustained demand for utilities, grid equipment, cooling, and compute infrastructure suppliers. "
                f"{source_label}"
            ),
            "enterprise": (
                f"Enterprise AI adoption {confirmation_word} a shift from experimentation toward workflow integration, productivity, and operating leverage. "
                "This matters because software spending is starting to favor practical deployment and measurable return on investment. "
                "The investment implication is stronger support for application software, services, and workflow vendors that can translate AI into revenue or margin impact. "
                f"{source_label}"
            ),
            "capital_markets": (
                f"AI-related capital formation and competitive positioning {confirmation_word} continued repricing across public and private markets. "
                "This matters because investment leadership is broadening beyond model builders into infrastructure, tools, and adjacent beneficiaries. "
                "The investment implication is a wider opportunity set across capital equipment, semis, private funding channels, and second-order AI beneficiaries. "
                f"{source_label}"
            ),
            "policy": (
                f"Policy and regulatory developments {confirmation_word} that AI governance is becoming a durable market variable rather than a headline risk. "
                "This matters because compliance, export controls, and public-sector positioning can shape adoption speed and competitive advantage. "
                "The investment implication is higher sensitivity around globally exposed AI supply chains, platform providers, and regulated end markets. "
                f"{source_label}"
            ),
            "labor": (
                f"AI-driven workforce and productivity signals {confirmation_word} pressure on how enterprises allocate labor, automate processes, and redesign knowledge work. "
                "This matters because labor leverage is becoming one of the clearest channels through which AI affects margins and operating models. "
                "The investment implication is stronger focus on companies that can convert AI adoption into measurable productivity gains. "
                f"{source_label}"
            ),
            "other": (
                f"Cross-market AI developments {confirmation_word} that the theme set is widening beyond a narrow group of model and chip headlines. "
                "This matters because adjacent suppliers, adopters, and infrastructure players are increasingly relevant to the AI buildout. "
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
        for section_title, themes in section_map:
            lines.append(section_title)
            section_written = 0
            for theme in themes:
                if theme not in theme_dict:
                    continue
                lines.append(synthesize_theme(theme, theme_dict[theme][:4]))
                lines.append("")
                section_written += 1
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
    content = build_theme_output(articles)

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return f"""Daily Riffs from the Gen AI Songbook
{today}

{content}
"""
