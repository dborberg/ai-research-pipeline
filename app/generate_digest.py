from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_PROMPTS_DIR = REPO_ROOT / "prompts" / "daily"
DAILY_PROMPT_PATHS = {
    "daily_digest_system": DAILY_PROMPTS_DIR / "daily_digest_system_prompt.md",
    "daily_digest_user": DAILY_PROMPTS_DIR / "daily_digest_user_prompt.md",
}


def _read_daily_prompt_template(name):
    path = DAILY_PROMPT_PATHS[name]
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required daily prompt file not found: {path}") from exc


def _load_daily_prompt(name, **replacements):
    prompt = _read_daily_prompt_template(name)
    for key, value in replacements.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
    return prompt


def generate_daily_digest(report_date=None):
    import json
    import os
    import re
    from collections import Counter
    from datetime import datetime, timedelta
    from html import unescape
    from zoneinfo import ZoneInfo
    from openai import APITimeoutError, OpenAI
    from sqlalchemy import text

    from app.branding import DAILY_TITLE
    from app.db import get_engine
    from app.pipeline_window import get_pipeline_window

    _CENTRAL_TZ = ZoneInfo("America/Chicago")
    digest_token_budget = 6000
    digest_request_timeout = float(os.getenv("OPENAI_DIGEST_TIMEOUT_SECONDS", "150"))
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=digest_request_timeout,
        max_retries=0,
    )

    # -----------------------------
    # GET ARTICLES
    # -----------------------------
    def is_big_story(article):
        text = f"{article.get('title') or ''} {article.get('summary') or ''}".lower()
        return any(term in text for term in [
            "nvidia", "microsoft", "amazon", "google", "tesla", "apple", "openai", "tsmc", "asml",
            "government", "policy", "regulation", "white house", "lawmakers",
            "upgrade", "earnings", "index", "investment", "capex", "valuation", "funding",
            "data center", "power", "grid", "fab", "fabs", "campus", "semiconductor",
            "cooling", "nuclear", "battery", "batteries", "interconnection", "fiber", "optical",
            "bond issuance", "private credit", "sovereign ai", "agentic", "robotics",
        ])

    def parse_companies(raw_companies):
        if not raw_companies:
            return []
        if isinstance(raw_companies, list):
            return [str(item).strip() for item in raw_companies if str(item).strip()]
        try:
            parsed = json.loads(raw_companies)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in str(raw_companies).split(",") if part.strip()]

    def has_policy_priority(article):
        text = f"{article.get('title') or ''} {article.get('summary') or ''} {article.get('advisor_relevance') or ''}".lower()
        return any(term in text for term in [
            "white house", "congress", "senate", "house of representatives", "lawmakers", "lawmaker",
            "regulator", "regulators", "regulation", "regulatory", "rulemaking", "antitrust",
            "export control", "export controls", "restriction", "restrictions", "ban", "tariff",
            "commission", "eu", "european union", "european commission", "ftc", "doj", "fcc",
            "legislation", "bill", "policy proposal", "executive order", "compliance",
            "sanders", "ocasio-cortez", "aoc", "senator", "representative",
        ])

    def has_named_event_anchor(article):
        if parse_companies(article.get("companies")):
            return True
        title = article.get("title") or ""
        return bool(re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", title))

    def source_quality_hint(article):
        source = (article.get("original_publisher") or article.get("source") or "").lower()
        if any(term in source for term in [
            "reuters", "bloomberg", "financial times", "ft.com", "wall street journal", "wsj",
            "associated press", "ap news", "sec", "federal register", "white house",
            "congress", "senate", "house.gov", "commerce department", "ftc", "doj",
            "company announcement", "press release", "investor relations", "filing",
            "google cloud", "aws", "microsoft azure", "oracle", "nvidia",
        ]):
            return "high_confidence"
        if any(term in source for term in [
            "mckinsey", "bain", "bcg", "gartner", "idc", "forrester", "s&p global",
            "semiconductor engineering", "data center dynamics", "utility dive",
            "eetimes", "digitimes", "converge digest", "the register", "ieee",
            "robot report", "design news",
        ]):
            return "credible_industry"
        if any(term in source for term in [
            "fortune", "the information", "morning brew", "local", "news",
        ]):
            return "useful_careful"
        if any(term in source for term in [
            "medium", "substack", "blog", "aggregator", "crypto", "coin",
        ]):
            return "lower_confidence"
        return "general_news"

    def investment_theme_score(article):
        text = " ".join(
            [
                article.get("title") or "",
                article.get("summary") or "",
                article.get("advisor_relevance") or "",
                " ".join(parse_companies(article.get("companies"))),
            ]
        ).lower()
        theme_terms = {
            "infrastructure_buildout": (
                18,
                [
                    "data center", "datacenter", "compute leasing", "gpu", "gpus", "asic", "asics",
                    "tpu", "tpus", "hbm", "memory", "advanced packaging", "semicap", "cloud infrastructure",
                    "sovereign ai", "networking", "interconnect", "accelerated computing",
                ],
            ),
            "power_physical_bottlenecks": (
                18,
                [
                    "grid capacity", "electricity demand", "power purchase agreement", "ppa", "battery",
                    "batteries", "backup power", "natural gas turbine", "fuel cell", "nuclear", "cooling",
                    "liquid cooling", "water use", "fiber", "optical", "transformer", "switchgear",
                    "permitting", "zoning", "interconnection queue", "moratorium",
                ],
            ),
            "capital_intensity_financing": (
                16,
                [
                    "capex", "capital expenditure", "bond issuance", "debt financing", "project finance",
                    "data center leasing", "infrastructure funding", "private credit", "sovereign funding",
                    "multi-year", "balance sheet", "financing",
                ],
            ),
            "enterprise_adoption_monetization": (
                14,
                [
                    "agentic", "agent", "copilot", "workflow automation", "saas", "pricing", "roi",
                    "customer adoption", "retention", "observability", "identity", "security", "governance",
                    "spend controls", "compliance tool", "professional services automation",
                ],
            ),
            "second_derivative_beneficiaries": (
                13,
                [
                    "electrical equipment", "power semiconductor", "analog semiconductor", "cooling supplier",
                    "fiber supplier", "networking", "industrial automation", "engineering firm", "utility",
                    "utilities", "specialty materials", "cybersecurity", "data infrastructure",
                    "validation", "governance software",
                ],
            ),
            "labor_redesign": (
                11,
                [
                    "white-collar", "workflow change", "ai-assisted coding", "junior talent",
                    "professional services", "quality control", "testing", "human-in-the-loop",
                    "augmentation", "replacement", "workforce",
                ],
            ),
            "regulation_governance_access": (
                15,
                [
                    "procurement standard", "model safety", "ai disclosure", "hiring rule", "privacy",
                    "auditability", "ip policy", "public-sector", "public sector", "risk control",
                    "export control", "antitrust",
                ],
            ),
            "physical_ai_robotics": (
                14,
                [
                    "robot", "robotics", "humanoid", "autonomous system", "industrial automation",
                    "warehouse automation", "evtol", "drone", "drones", "lab automation",
                    "surgical automation", "ai-enabled manufacturing", "embodied ai", "defense autonomy",
                ],
            ),
            "market_structure_competitive_advantage": (
                10,
                [
                    "scale economies", "data advantage", "supply constraint", "switching cost",
                    "ecosystem", "open-source pressure", "concentration risk", "platform advantage",
                    "margin durability",
                ],
            ),
        }
        score = 0
        for weight, terms in theme_terms.values():
            matches = sum(1 for term in terms if term in text)
            if matches:
                score += weight + min(matches - 1, 4) * 2
        return score

    def article_priority_score(article):
        score = float(article.get("ai_score") or 0)
        score += investment_theme_score(article)

        if has_policy_priority(article):
            score += 40
        if is_big_story(article):
            score += 20
        if has_named_event_anchor(article):
            score += 10

        source_hint = source_quality_hint(article)
        if source_hint == "high_confidence":
            score += 14
        elif source_hint == "credible_industry":
            score += 9
        elif source_hint == "useful_careful":
            score += 4
        elif source_hint == "lower_confidence":
            score -= 8

        companies = parse_companies(article.get("companies"))
        if companies:
            score += min(len(companies), 5)

        return score

    def extract_theme_tags(article):
        text = " ".join(
            [
                article.get("title") or "",
                article.get("summary") or "",
                article.get("advisor_relevance") or "",
            ]
        ).lower()
        theme_rules = {
            "infrastructure_and_power": [
                "data center", "datacenter", "power", "grid", "electricity", "utility", "utilities",
                "cooling", "thermal", "nuclear", "land", "water", "semiconductor", "chip", "networking",
                "optical", "fiber", "fab", "fabs", "battery", "batteries", "backup power",
                "interconnection", "permitting", "zoning", "transformer", "switchgear",
            ],
            "enterprise_and_labor": [
                "hiring", "layoff", "layoffs", "job", "jobs", "workforce", "productivity", "automation",
                "employee", "employees", "coding", "developer", "software development", "copilot",
                "agentic", "agent", "workflow", "governance", "compliance", "spend control",
            ],
            "capital_markets_and_investment": [
                "earnings", "revenue", "valuation", "funding", "raised", "investment", "investor",
                "capital", "stock", "shares", "private equity", "venture", "vc", "lease",
                "bond", "debt", "private credit", "project finance", "capex", "ipo",
            ],
            "regulation_and_policy": [
                "regulation", "regulatory", "policy", "lawmakers", "congress", "senate", "government",
                "public feedback", "moratorium", "antitrust", "export control", "compliance", "bill",
                "procurement", "model safety", "privacy", "ip", "hiring rule", "public-sector",
            ],
            "physical_ai_and_robotics": [
                "robot", "robotics", "autonomous", "autonomy", "warehouse automation", "drone", "aviation",
                "manufacturing", "factory", "humanoid", "inspection", "logistics", "evtol",
                "lab automation", "surgical automation", "embodied ai", "defense autonomy",
            ],
        }

        tags = []
        for theme_name, terms in theme_rules.items():
            if any(term in text for term in terms):
                tags.append(theme_name)
        return tags

    def event_anchor(article):
        companies = [company.lower() for company in parse_companies(article.get("companies"))]
        title = (article.get("title") or "").lower()
        normalized_title = re.sub(r"[^a-z0-9\s]", " ", title)
        stopwords = {
            "the", "and", "for", "with", "from", "into", "after", "amid", "over", "under", "that",
            "this", "will", "would", "could", "about", "their", "they", "says", "said", "report",
            "reported", "announced", "launches", "launch", "launching", "new", "its", "are", "now",
            "more", "than", "into", "using", "use", "shows",
        }
        title_tokens = [
            token for token in normalized_title.split()
            if len(token) > 2 and token not in stopwords and not token.isdigit()
        ]
        theme_tags = extract_theme_tags(article)

        if companies:
            return "company|" + "|".join(companies[:2] + theme_tags[:2])
        if title_tokens:
            return "title|" + "|".join(title_tokens[:6] + theme_tags[:2])
        return "fallback|" + (article.get("url") or article.get("published_at") or "")

    def deduplicate_articles_by_event(articles):
        grouped_articles = {}
        for article in articles:
            anchor = event_anchor(article)
            incumbent = grouped_articles.get(anchor)
            if incumbent is None or article_priority_score(article) > article_priority_score(incumbent):
                grouped_articles[anchor] = article

        deduped_articles = list(grouped_articles.values())
        deduped_articles.sort(
            key=lambda article: (
                has_policy_priority(article),
                is_big_story(article),
                has_named_event_anchor(article),
                article_priority_score(article),
                article.get("published_at") or "",
            ),
            reverse=True,
        )
        return deduped_articles

    def clip_prompt_text(value, limit):
        text_value = " ".join(str(value or "").split())
        if len(text_value) <= limit:
            return text_value
        return text_value[: limit - 3].rstrip() + "..."

    def primary_section_hint(article):
        preferred_order = [
            "regulation_and_policy",
            "capital_markets_and_investment",
            "infrastructure_and_power",
            "enterprise_and_labor",
            "physical_ai_and_robotics",
        ]
        label_map = {
            "regulation_and_policy": "REGULATION, GOVERNANCE AND POLICY",
            "capital_markets_and_investment": "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS",
            "infrastructure_and_power": "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS",
            "enterprise_and_labor": "ENTERPRISE ADOPTION AND LABOR",
            "physical_ai_and_robotics": "PHYSICAL AI AND ROBOTICS",
        }

        themes = extract_theme_tags(article)
        for theme_name in preferred_order:
            if theme_name in themes:
                return label_map[theme_name]
        return "TOP STORIES"

    def select_prompt_articles(deduped_articles, min_count=12, max_count=18):
        selected_articles = []
        seen_ids = set()
        required_themes = [
            "regulation_and_policy",
            "capital_markets_and_investment",
            "infrastructure_and_power",
            "physical_ai_and_robotics",
            "enterprise_and_labor",
        ]

        for theme_name in required_themes:
            for article in deduped_articles:
                article_id = id(article)
                if article_id in seen_ids:
                    continue
                if theme_name not in extract_theme_tags(article):
                    continue

                selected_articles.append(article)
                seen_ids.add(article_id)
                break

        for article in deduped_articles:
            if len(selected_articles) >= max_count:
                break

            article_id = id(article)
            if article_id in seen_ids:
                continue

            selected_articles.append(article)
            seen_ids.add(article_id)

        if len(selected_articles) < min_count:
            return deduped_articles[:max_count]

        return selected_articles

    def build_theme_signal_block(all_articles):
        theme_labels = {
            "infrastructure_and_power": "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS",
            "enterprise_and_labor": "ENTERPRISE ADOPTION AND LABOR",
            "capital_markets_and_investment": "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS",
            "regulation_and_policy": "REGULATION, GOVERNANCE AND POLICY",
            "physical_ai_and_robotics": "PHYSICAL AI AND ROBOTICS",
        }
        theme_examples = {theme_name: [] for theme_name in theme_labels}

        for article in all_articles:
            companies = parse_companies(article.get("companies"))
            example_label = companies[0] if companies else (article.get("title") or "").split(":")[0].strip()
            for theme_name in extract_theme_tags(article):
                if example_label and example_label not in theme_examples[theme_name]:
                    theme_examples[theme_name].append(example_label)

        theme_counts = Counter(
            theme_name
            for article in all_articles
            for theme_name in extract_theme_tags(article)
        )

        lines = []
        for theme_name, count in theme_counts.most_common():
            examples = ", ".join(theme_examples[theme_name][:4])
            lines.append(
                f"THEME_SIGNAL: {theme_labels[theme_name]} | corroborating_articles={count} | representative_examples={examples}"
            )

        if not lines:
            return ""
        return "\n".join(lines)

    def get_recent_articles():
        engine = get_engine()
        window_start, window_end = get_pipeline_window(hours=24)

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT title, source, COALESCE(original_publisher, source) AS original_publisher, summary, url, published_at, companies, advisor_relevance, ai_score
                FROM articles
                WHERE published_at >= :window_start
                  AND published_at <= :window_end
                ORDER BY published_at DESC
            """), {"window_start": window_start.isoformat(), "window_end": window_end.isoformat()})

            rows = result.fetchall()

        articles = []
        for row in rows:
            title = row[0] or ""
            source = row[1] or ""
            original_publisher = row[2] or source
            summary = row[3] or ""
            url = row[4] or ""
            published_at = row[5] or ""
            companies = row[6] or ""
            advisor_relevance = row[7] or ""
            ai_score = row[8]

            # Skip empty/incomplete content per your rule
            if not title or not summary:
                continue

            articles.append({
                "title": title,
                "source": source,
                "original_publisher": original_publisher,
                "summary": summary,
                "url": url,
                "published_at": published_at,
                "companies": companies,
                "advisor_relevance": advisor_relevance,
                "ai_score": ai_score,
            })

        articles.sort(
            key=lambda article: (
                has_policy_priority(article),
                is_big_story(article),
                has_named_event_anchor(article),
                article_priority_score(article),
                article.get("published_at") or "",
            ),
            reverse=True,
        )

        return articles

    def _normalize_text(value):
        text_value = unescape(re.sub(r"<[^>]+>", " ", value or ""))
        return " ".join(text_value.lower().split())

    def _extract_digest_bullets(content):
        sections = []
        for section_name, section_body in re.findall(r"<h3>(.*?)</h3>\s*<ul>(.*?)</ul>", content or "", flags=re.DOTALL | re.IGNORECASE):
            for item in re.findall(r"<li>(.*?)</li>", section_body, flags=re.DOTALL | re.IGNORECASE):
                lead_match = re.search(r"<strong>(.*?)</strong>", item, flags=re.DOTALL | re.IGNORECASE)
                source_match = re.search(r"\(Source:\s*([^\)]+)\)", item, flags=re.DOTALL | re.IGNORECASE)
                sections.append(
                    {
                        "section": unescape(section_name.strip()),
                        "lead": unescape((lead_match.group(1) if lead_match else item).strip()),
                        "source": unescape((source_match.group(1) if source_match else "").strip()),
                        "text": _normalize_text(item),
                    }
                )
        return sections

    def _find_diversity_issues(content, available_publishers):
        expected_sections = [
            "TOP THEME OF THE DAY",
            "TOP STORIES",
            "ENTERPRISE ADOPTION AND LABOR",
            "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS",
            "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS",
            "REGULATION, GOVERNANCE AND POLICY",
            "PHYSICAL AI AND ROBOTICS",
            "WHAT TO WATCH",
            "ADVISOR / WHOLESALER SOUNDBITES",
        ]
        issues = []
        found_sections = re.findall(r"<h3>(.*?)</h3>", content or "", flags=re.IGNORECASE)
        normalized_found_sections = [unescape(section).strip().upper() for section in found_sections]
        missing_sections = [section for section in expected_sections if section not in normalized_found_sections]
        if missing_sections:
            issues.append(f"Missing required sections: {', '.join(missing_sections)}")
        found_required_sections = [section for section in normalized_found_sections if section in expected_sections]
        if found_required_sections != expected_sections:
            issues.append("Required sections are not in the expected order or old section names were used")

        top_theme_match = re.search(
            r"<h3>\s*TOP THEME OF THE DAY\s*</h3>\s*<p>.*?</p>",
            content or "",
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not top_theme_match:
            issues.append("TOP THEME OF THE DAY must be a paragraph immediately after its h3 heading")

        disallowed_tags = [
            tag for tag in re.findall(r"</?\s*([a-zA-Z0-9]+)", content or "")
            if tag.lower() not in {"h2", "h3", "p", "ul", "li", "strong"}
        ]
        if disallowed_tags:
            issues.append("HTML includes disallowed tags: " + ", ".join(sorted(set(disallowed_tags))))

        if re.search(r"(^|\s)(buy|sell|hold|overweight|underweight|price target)(\s|[.,;:])", content or "", flags=re.IGNORECASE):
            issues.append("Output includes explicit recommendation language")
        if "->" in (content or "") or "→" in (content or ""):
            issues.append("Output includes arrows")

        bullets = _extract_digest_bullets(content)
        bullets_missing_sources = [
            bullet["lead"] for bullet in bullets
            if bullet["section"].upper() not in {"WHAT TO WATCH", "ADVISOR / WHOLESALER SOUNDBITES"} and not bullet["source"]
        ]
        if bullets_missing_sources:
            issues.append("Analytical section bullets must include Source attribution")

        lead_counts = Counter(_normalize_text(bullet["lead"]) for bullet in bullets if bullet["lead"])
        repeated_leads = [lead for lead, count in lead_counts.items() if lead and count > 1]
        if repeated_leads:
            issues.append("Repeated lead phrases suggest the same development is being reused across sections")

        publisher_counts = Counter(bullet["source"] for bullet in bullets if bullet["source"])
        unique_publishers = len({publisher for publisher in publisher_counts if publisher})
        dominant_publishers = [
            publisher for publisher, count in publisher_counts.items()
            if count >= 5 and unique_publishers >= 4 and len(available_publishers) >= 4
        ]
        if dominant_publishers:
            issues.append(
                "Publisher concentration is still too high: " + ", ".join(
                    f"{publisher} ({publisher_counts[publisher]})" for publisher in dominant_publishers
                )
            )

        section_story_map = {}
        for bullet in bullets:
            normalized_lead = _normalize_text(bullet["lead"])
            if not normalized_lead:
                continue
            section_story_map.setdefault(normalized_lead, set()).add(bullet["section"])
        cross_section_repeats = [lead for lead, sections in section_story_map.items() if len(sections) > 1]
        if cross_section_repeats:
            issues.append("The same underlying development appears in multiple sections")

        return issues

    all_articles = get_recent_articles()
    articles = deduplicate_articles_by_event(all_articles)
    if report_date is None:
        report_date = datetime.now(_CENTRAL_TZ).date()
    today = report_date.strftime("%B %d, %Y")
    available_publishers = {
        article.get("original_publisher") or article.get("source")
        for article in all_articles
        if article.get("original_publisher") or article.get("source")
    }
    theme_signal_block = build_theme_signal_block(all_articles)
    prompt_articles = select_prompt_articles(articles)

    if not all_articles:
        return f"""<h2>{DAILY_TITLE}</h2>
<p><strong>{today}</strong></p>
<h3>TOP THEME OF THE DAY</h3>
<p>No meaningful Gen AI developments surfaced in the daily source window, so there is no cross-story investment theme to elevate today.</p>
<h3>TOP STORIES</h3>
<ul><li><strong>No major Gen AI stories surfaced:</strong> Continue monitoring company actions, policy moves, infrastructure buildouts, financing events, and enterprise deployments for fresh signals. (Source: Full article set)</li></ul>
<h3>ENTERPRISE ADOPTION AND LABOR</h3>
<ul><li><strong>No major enterprise adoption or labor developments surfaced:</strong> Continue monitoring agentic AI, copilots, workflow redesign, professional services automation, and governance signals. (Source: Full article set)</li></ul>
<h3>INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS</h3>
<ul><li><strong>No major infrastructure or power bottleneck developments surfaced:</strong> Continue monitoring data centers, grid capacity, cooling, semiconductors, networking, and permitting constraints. (Source: Full article set)</li></ul>
<h3>CAPITAL MARKETS AND INVESTMENT IMPLICATIONS</h3>
<ul><li><strong>No major capital markets or investment-implication developments surfaced:</strong> Continue monitoring earnings, capex, financing, funding, valuation discipline, and second-derivative beneficiaries. (Source: Full article set)</li></ul>
<h3>REGULATION, GOVERNANCE AND POLICY</h3>
<ul><li><strong>No major regulation, governance, or policy developments surfaced:</strong> Continue monitoring procurement rules, model safety, privacy, export controls, antitrust, and AI hiring rules. (Source: Full article set)</li></ul>
<h3>PHYSICAL AI AND ROBOTICS</h3>
<ul><li><strong>No major commercial Physical AI or robotics developments surfaced:</strong> Continue monitoring robotics, autonomous systems, lab automation, industrial automation, and AI-enabled manufacturing for signs that pilots are moving into real deployment. (Source: Full article set)</li></ul>
<h3>WHAT TO WATCH</h3>
<ul><li><strong>Fresh source flow:</strong> Watch for new company announcements, policy actions, capex disclosures, infrastructure projects, and enterprise deployments in the next daily window. (Source: Full article set)</li></ul>
<h3>ADVISOR / WHOLESALER SOUNDBITES</h3>
<ul><li><strong>Quiet days still matter:</strong> When the source window is thin, the discipline is to wait for real events rather than force an AI narrative. (Source: Full article set)</li></ul>"""
    article_block = "\n\n---\n\n".join(
        "\n".join(
            [
                f"TITLE: {article['title']}",
                f"SOURCE: {article.get('original_publisher') or article['source']}",
                f"PRIMARY_SECTION_HINT: {primary_section_hint(article)}",
                f"SOURCE_QUALITY_HINT: {source_quality_hint(article)}",
                f"INVESTMENT_THEME_SCORE: {investment_theme_score(article)}",
                f"BIG_STORY_HINT: {'YES' if is_big_story(article) else 'NO'}",
                f"POLICY_PRIORITY_HINT: {'YES' if has_policy_priority(article) else 'NO'}",
                f"COMPANIES_MENTIONED: {', '.join(parse_companies(article.get('companies')))}",
                f"AI_SCORE: {article.get('ai_score') if article.get('ai_score') is not None else ''}",
                f"ADVISOR_RELEVANCE: {clip_prompt_text(article.get('advisor_relevance'), 220)}",
                f"SUMMARY: {clip_prompt_text(article['summary'], 420)}",
            ]
        )
        for article in prompt_articles
    )

    system_prompt = _load_daily_prompt("daily_digest_system")
    user_prompt = _load_daily_prompt(
        "daily_digest_user",
        daily_title=DAILY_TITLE,
        today=today,
        theme_signal_block=theme_signal_block,
        article_block=article_block,
    )

    content = ""
    issues = []
    extra_feedback = ""
    for attempt in range(3):
        print(
            f"Daily digest LLM attempt {attempt + 1}/3 "
            f"with max_completion_tokens={digest_token_budget}"
        )
        request_prompt = user_prompt.strip()
        if extra_feedback:
            request_prompt = f"{request_prompt}\n\nREVISION FEEDBACK:\n{extra_feedback}"

        try:
            response = client.chat.completions.create(
                model="gpt-5.5",
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": request_prompt}
                ],
                max_completion_tokens=digest_token_budget,
                timeout=digest_request_timeout,
            )
        except APITimeoutError:
            if attempt == 2:
                raise

            print(
                "Daily digest request timed out; retrying with the same prompt "
                f"and timeout={digest_request_timeout:.0f}s"
            )
            extra_feedback = (
                "The previous attempt timed out before returning the full HTML digest. "
                "Rewrite the full digest more compactly while preserving all required sections, "
                "source diversity, event specificity, and complete HTML structure. "
                "Return only the finished HTML."
            )
            digest_token_budget = min(digest_token_budget, 5000)
            continue

        choice = response.choices[0]
        content = (choice.message.content or "").strip()

        if not content:
            if choice.finish_reason == "length" and attempt < 2:
                print("Daily digest returned empty content due to length; retrying with a larger token budget")
                digest_token_budget = 7500
                extra_feedback = (
                    "The previous attempt ran out of output tokens before returning usable HTML. "
                    "Rewrite the full digest more compactly while preserving all required sections, "
                    "source diversity, event specificity, and complete HTML structure. "
                    "Return only the finished HTML."
                )
                continue
            raise ValueError(
                f"LLM returned empty digest content "
                f"(finish_reason={choice.finish_reason})"
            )

        issues = _find_diversity_issues(content, available_publishers)
        if not issues:
            break

        print("Daily digest diversity retry triggered: " + "; ".join(issues))
        extra_feedback = (
            "The previous draft did not satisfy diversity requirements. "
            "Rewrite from the same article set and fix these issues:\n- "
            + "\n- ".join(issues)
            + "\nDo not explain the fixes. Return only the corrected HTML."
        )

    # -----------------------------
    # FINAL OUTPUT
    # -----------------------------
    return content
