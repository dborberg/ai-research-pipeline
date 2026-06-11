#!/usr/bin/env python3
"""Validate daily digest HTML against the daily output contract."""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


REQUIRED_HEADINGS = [
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
ALLOWED_TAGS = {"h2", "h3", "p", "ul", "li", "strong"}
READ_THROUGH_CATEGORIES = [
    "private credit",
    "construction",
    "construction services",
    "electrical equipment",
    "power equipment",
    "grid",
    "grid infrastructure",
    "cooling",
    "backup power",
    "fiber",
    "networking",
    "utilities",
    "gpus",
    "gpu",
    "ai pcs",
    "local inference",
    "enterprise workstations",
    "hybrid cloud",
    "semiconductors",
    "semicap",
    "memory",
    "advanced packaging",
    "optical networking",
    "data platforms",
    "governance software",
    "cybersecurity",
    "it services",
    "industrial automation",
]
RECOMMENDATION_RE = re.compile(
    r"(^|\s)(buy|sell|hold|overweight|underweight|price target|guaranteed winner|guaranteed loser)(\s|[.,;:])",
    flags=re.IGNORECASE,
)
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF]",
    flags=re.UNICODE,
)
PHYSICAL_AI_FALLBACK = (
    "<li><strong>No major commercial Physical AI or robotics developments surfaced:</strong> "
    "Continue monitoring robotics, autonomous systems, lab automation, industrial automation, "
    "and AI-enabled manufacturing for signs that pilots are moving into real deployment. "
    "(Source: Full article set)</li>"
)


def _normalize_text(value):
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").lower().split())


def _read_through_signature(text):
    normalized = _normalize_text(text)
    return tuple(category for category in READ_THROUGH_CATEGORIES if category in normalized)


def _is_local_data_center_permitting_bullet(text):
    normalized = _normalize_text(text)
    return (
        ("data center" in normalized or "datacenter" in normalized)
        and any(term in normalized for term in ["permit", "permitting", "zoning", "moratorium", "county", "city council", "local"])
    )


class DigestHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.h3_headings = []
        self.li_items = []
        self._current_tag = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag.lower())
        if tag.lower() in {"h3", "li"}:
            self._current_tag = tag.lower()
            self._current_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._current_tag == tag:
            text = " ".join("".join(self._current_text).split())
            if tag == "h3":
                self.h3_headings.append(text)
            elif tag == "li":
                self.li_items.append(text)
            self._current_tag = None
            self._current_text = []

    def handle_data(self, data):
        if self._current_tag:
            self._current_text.append(data)


def validate_daily_digest_html(html, require_physical_ai_fallback=False):
    issues = []
    parser = DigestHtmlParser()
    parser.feed(html)

    disallowed_tags = sorted({tag for tag in parser.tags if tag not in ALLOWED_TAGS})
    if disallowed_tags:
        issues.append("Disallowed HTML tags: " + ", ".join(disallowed_tags))
    for required_tag in ["h2", "h3", "p", "ul", "li", "strong"]:
        if required_tag not in parser.tags:
            issues.append(f"Required HTML tag not found: {required_tag}")

    if parser.h3_headings != REQUIRED_HEADINGS:
        issues.append(
            "Required h3 headings are missing, renamed, duplicated, or out of order. "
            f"Found: {parser.h3_headings}"
        )
    duplicate_headings = sorted(
        heading for heading in set(parser.h3_headings) if parser.h3_headings.count(heading) > 1
    )
    if duplicate_headings:
        issues.append("Duplicate section headings detected: " + ", ".join(duplicate_headings))

    top_theme_pattern = re.compile(
        r"<h3>\s*TOP THEME OF THE DAY\s*</h3>\s*<p>.+?</p>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not top_theme_pattern.search(html):
        issues.append("TOP THEME OF THE DAY must be present as a paragraph")

    if re.search(r"(^|\n)\s*[-*]\s+", html):
        issues.append("Markdown bullet formatting detected")
    if re.search(r"(\*\*|__|^#{1,6}\s+|`)", html, flags=re.MULTILINE):
        issues.append("Markdown formatting detected")
    if "->" in html or "→" in html:
        issues.append("Arrow formatting detected")
    if EMOJI_RE.search(html):
        issues.append("Emoji detected")
    if RECOMMENDATION_RE.search(html):
        issues.append("Explicit recommendation language detected")

    bullet_sections = {
        "TOP STORIES",
        "ENTERPRISE ADOPTION AND LABOR",
        "INFRASTRUCTURE, POWER AND PHYSICAL BOTTLENECKS",
        "CAPITAL MARKETS AND INVESTMENT IMPLICATIONS",
        "REGULATION, GOVERNANCE AND POLICY",
        "PHYSICAL AI AND ROBOTICS",
        "WHAT TO WATCH",
        "ADVISOR / WHOLESALER SOUNDBITES",
    }
    section_blocks = re.findall(
        r"<h3>(.*?)</h3>\s*(?:<p>.*?</p>\s*)?(?:<ul>(.*?)</ul>)?",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for heading, body in section_blocks:
        normalized_heading = " ".join(re.sub(r"<[^>]+>", "", heading).split()).upper()
        if normalized_heading not in bullet_sections:
            continue
        for item in re.findall(r"<li>.*?</li>", body or "", flags=re.DOTALL | re.IGNORECASE):
            if "(Source:" not in item:
                issues.append(f"Missing Source attribution in {normalized_heading}")
                break

    source_counts = {}
    for item in parser.li_items:
        source_match = re.search(r"\(Source:\s*([^\)]+)\)", item, flags=re.DOTALL | re.IGNORECASE)
        if not source_match:
            continue
        source = " ".join(source_match.group(1).split())
        if source.lower() == "full article set":
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
    sourced_bullet_count = sum(source_counts.values())
    if len(source_counts) >= 4 and sourced_bullet_count >= 10:
        source, count = max(source_counts.items(), key=lambda item: item[1])
        if count >= 6 and count / sourced_bullet_count > 0.4:
            issues.append(f"Repeated source concentration appears high: {source} appears {count} times")

    long_category_lists = []
    category_signatures = {}
    for item in parser.li_items:
        signature = _read_through_signature(item)
        if len(signature) >= 7:
            long_category_lists.append(item[:80])
        if len(signature) >= 5:
            category_signatures[signature] = category_signatures.get(signature, 0) + 1
    if long_category_lists:
        issues.append("Investment read-through list appears too long in one or more bullets")
    if any(count > 1 for count in category_signatures.values()):
        issues.append("Repeated long investment read-through category list detected")

    local_permitting_count = sum(1 for item in parser.li_items if _is_local_data_center_permitting_bullet(item))
    if local_permitting_count > 3:
        issues.append("Too many bullets repeat local data-center permitting language")

    bullet_lengths = [len(_normalize_text(item).split()) for item in parser.li_items]
    if sum(1 for length in bullet_lengths if length > 90) > 3 or any(length > 130 for length in bullet_lengths):
        issues.append("Excessive bullet length detected")

    if len(html) < 1200:
        issues.append("Output appears unusually short")
    if len(html) > 40000:
        issues.append("Output appears unusually long")

    if require_physical_ai_fallback and PHYSICAL_AI_FALLBACK not in html:
        issues.append("Physical AI fallback language is not available in the output")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate a saved daily digest HTML file.")
    parser.add_argument("path", help="Path to the daily digest HTML/text output")
    parser.add_argument(
        "--require-physical-ai-fallback",
        action="store_true",
        help="Require the exact Physical AI fallback bullet for a no-robotics source set.",
    )
    args = parser.parse_args()

    html = Path(args.path).read_text(encoding="utf-8")
    issues = validate_daily_digest_html(
        html,
        require_physical_ai_fallback=args.require_physical_ai_fallback,
    )
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1

    print("Daily digest validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
