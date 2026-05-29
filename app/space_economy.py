"""Optional Space Economy theme tagging for the AI research pipeline."""

import re

SPACE_ECONOMY_FILTER_PROMPT = """SPACE ECONOMY OPTIONAL THEME FILTER

Space-related developments may be considered only when the connection to Gen AI, physical AI, autonomy, AI infrastructure, defense AI, satellite data, geospatial intelligence, robotics, cybersecurity, cloud analytics, or AI-enabled communications is direct and investment-relevant.

Do not include general space-economy stories solely because they are technologically interesting. A rocket launch, satellite deployment, NASA contract, broadband constellation update, or space funding story should appear in the Daily briefing only if it has a meaningful read-through to AI-enabled data intelligence, autonomous systems, defense decision loops, cloud/AI infrastructure, communications resilience, robotics, cybersecurity, or public-market AI beneficiaries.

When a space-related story qualifies, frame it through the AI, data, defense, communications, cybersecurity, or infrastructure read-through first, then explain the broader investment implication.
"""

SPACE_METADATA_FIELDS = (
    "is_space_economy_related",
    "space_relevance",
    "space_ai_connection",
    "space_time_horizon",
    "space_investment_layer",
)

_SPACE_TERMS = [
    "space", "rocket", "launch", "reusable rocket", "satellite", "satellites",
    "satcom", "direct-to-device", "direct to device", "low-earth orbit",
    "low earth orbit", "leo constellation", "earth observation", "geospatial",
    "space-domain awareness", "space domain awareness", "missile warning",
    "orbital", "in-orbit", "in orbit", "space debris", "cislunar", "lunar",
    "ground system", "ground systems", "antenna", "antennas",
]

_GENERIC_SPACE_TERMS = [
    "rocket launch", "launch vehicle", "satellite deployment", "deployed satellite",
    "nasa contract", "broadband constellation", "space tourism", "space funding",
]

_AI_CONNECTION_RULES = [
    ("Gen AI", ["gen ai", "generative ai", "large language model", "llm"]),
    ("AI infrastructure", ["ai infrastructure", "accelerated computing", "gpu", "gpus", "data center", "datacenter", "semiconductor", "chip", "chips"]),
    ("autonomy", ["autonomous", "autonomy", "autonomous satellite", "autonomous satellites"]),
    ("robotics", ["robot", "robotics", "robotic", "in-orbit servicing", "orbital servicing"]),
    ("geospatial intelligence", ["geospatial intelligence", "geoai", "earth observation analytics", "ai-enabled geospatial", "ai enabled geospatial"]),
    ("defense AI", ["defense ai", "defence ai", "defense autonomy", "space-domain awareness", "space domain awareness", "missile warning"]),
    ("communications resilience", ["communications resilience", "resilient communications", "secure communications", "resilient connectivity"]),
    ("cybersecurity", ["cybersecurity", "cyber security", "cyber threat", "satellite security", "space cyber"]),
    ("cloud analytics", ["cloud analytics", "cloud-based analytics", "cloud based analytics", "satellite data analytics", "geospatial analytics"]),
]

_INVESTMENT_LAYER_RULES = [
    ("launch", ["rocket", "launch", "reusable rocket"]),
    ("satellites", ["satellite", "satellites", "constellation", "low-earth orbit", "low earth orbit"]),
    ("ground systems", ["ground system", "ground systems", "ground station"]),
    ("communications", ["communications", "connectivity", "direct-to-device", "direct to device", "satcom"]),
    ("Earth observation", ["earth observation", "geospatial", "remote sensing"]),
    ("defense", ["defense", "defence", "space-domain awareness", "space domain awareness", "missile warning"]),
    ("in-orbit servicing", ["in-orbit servicing", "in orbit servicing", "orbital servicing", "space debris"]),
    ("lunar-cislunar", ["lunar", "cislunar", "moon"]),
    ("software-data-analytics", ["software", "analytics", "data platform", "cloud", "ai analytics"]),
    ("components-picks-and-shovels", ["semiconductor", "chip", "sensor", "sensors", "antenna", "antennas", "power system"]),
]


def _article_text(article):
    return " ".join(
        str(article.get(field) or "")
        for field in (
            "title",
            "summary",
            "advisor_relevance",
            "themes",
            "companies",
            "raw_text",
            "cleaned_text",
        )
    ).lower()


def _contains_any(text, terms):
    return any(term in text for term in terms)


def _strip_negated_context(text):
    return re.sub(r"\b(?:without|no)\b[^.?!;]*(?:read-through|connection|link|tie|angle|implication|use case|application|analytics|autonomy|infrastructure)", " ", text)


def _infer_connection(text):
    for label, terms in _AI_CONNECTION_RULES:
        if _contains_any(text, terms):
            if label == "AI infrastructure" and "ai" not in text and "artificial intelligence" not in text:
                continue
            if label == "communications resilience" and not _contains_any(
                text,
                ["ai", "artificial intelligence", "defense", "defence", "cloud", "analytics", "cyber"],
            ):
                continue
            return label
    if "satellite data" in text and _contains_any(text, ["ai", "analytics", "cloud", "machine learning"]):
        return "cloud analytics"
    if "earth observation" in text and _contains_any(text, ["ai", "analytics", "cloud", "machine learning"]):
        return "geospatial intelligence"
    if "defense" in text and "space" in text and _contains_any(text, ["ai", "autonomous", "analytics", "decision"]):
        return "defense AI"
    return "none"


def _infer_layer(text):
    for label, terms in _INVESTMENT_LAYER_RULES:
        if _contains_any(text, terms):
            return label
    if "space" in text:
        return "other"
    return "none"


def _infer_time_horizon(text, connection):
    if connection == "none":
        return "none"
    if _contains_any(text, ["deployed", "deployment", "launched", "contract", "customer", "commercial", "operational", "production"]):
        return "near-term"
    if _contains_any(text, ["funding", "partnership", "pilot", "prototype", "planned", "building"]):
        return "medium-term"
    return "long-term"


def classify_space_economy_article(article):
    """Return optional Space Economy metadata for an article-like dict."""
    text = _article_text(article)
    signal_text = _strip_negated_context(text)
    is_related = _contains_any(text, _SPACE_TERMS)
    connection = _infer_connection(signal_text) if is_related else "none"
    layer = _infer_layer(text) if is_related else "none"

    if not is_related:
        relevance = "none"
    elif connection != "none":
        relevance = "high"
    elif _contains_any(text, _GENERIC_SPACE_TERMS):
        relevance = "low"
    else:
        relevance = "medium"

    return {
        "is_space_economy_related": bool(is_related),
        "space_relevance": relevance,
        "space_ai_connection": connection,
        "space_time_horizon": _infer_time_horizon(text, connection),
        "space_investment_layer": layer,
    }


def ensure_space_metadata(article):
    """Return a copy of article with optional Space Economy metadata filled if absent."""
    enriched = dict(article)
    if all(enriched.get(field) not in (None, "") for field in SPACE_METADATA_FIELDS):
        return enriched
    enriched.update(classify_space_economy_article(enriched))
    return enriched


def is_qualified_space_economy_article(article, quality_filter=None):
    enriched = ensure_space_metadata(article)
    if not enriched.get("is_space_economy_related"):
        return False
    if enriched.get("space_ai_connection") in (None, "", "none"):
        return False
    if quality_filter is not None and not quality_filter(enriched):
        return False
    return True


def calculate_space_economy_theme_active(articles, quality_filter=None):
    return any(is_qualified_space_economy_article(article, quality_filter) for article in articles)


def format_space_metadata_lines(article):
    enriched = ensure_space_metadata(article)
    if not is_qualified_space_economy_article(enriched):
        return []
    return [
        f"IS_SPACE_ECONOMY_RELATED: {str(enriched.get('is_space_economy_related')).upper()}",
        f"SPACE_RELEVANCE: {enriched.get('space_relevance') or 'none'}",
        f"SPACE_AI_CONNECTION: {enriched.get('space_ai_connection') or 'none'}",
        f"SPACE_TIME_HORIZON: {enriched.get('space_time_horizon') or 'none'}",
        f"SPACE_INVESTMENT_LAYER: {enriched.get('space_investment_layer') or 'none'}",
    ]
