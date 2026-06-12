#!/usr/bin/env python3
"""Lightweight validation for weekly synthesis outputs."""

import argparse
import re
import sys
from pathlib import Path


RECOMMENDATION_RE = re.compile(
    r"(^|\s)(buy|sell|hold|overweight|underweight|price target|guaranteed winner|guaranteed loser)(\s|[.,;:])",
    flags=re.IGNORECASE,
)
PERFORMANCE_PROMISE_RE = re.compile(
    r"\b(will outperform|guaranteed|can't miss|cannot miss|sure winner|certain winner)\b",
    flags=re.IGNORECASE,
)
SYNTHESIS_TERMS = [
    "pattern",
    "theme",
    "suggests",
    "collectively",
    "across the week",
    "repeated",
    "signals",
    "shift",
    "cycle",
]
FORWARD_ADOPTION_TERMS = [
    "production",
    "readiness",
    "workflow",
    "orchestration",
    "platform",
    "convergence",
    "agent",
    "governance",
    "embedded",
    "productivity",
    "automation",
    "discovery",
]
ADVISOR_TERMS = [
    "advisor",
    "wholesaler",
    "client conversation",
    "conversation",
    "talking point",
    "soundbite",
    "portfolio",
    "monitor",
]
SINGLE_STOCK_RE = re.compile(r"\b[A-Z]{1,5}\b")
THEME_TERMS = [
    "supply chain",
    "business model",
    "infrastructure",
    "adoption",
    "productivity",
    "governance",
    "capex",
    "portfolio",
    "sector",
    "theme",
]
REQUIRED_WHOLESALER_HEADINGS = [
    "TOP 5 STORIES THIS WEEK",
    "BEYOND THE MAG 7",
    "WHAT IS BEING DISRUPTED",
    "REGULATORY RADAR",
    "WHAT TO WATCH NEXT",
    "READY TO USE SOUNDBITES",
    "QUESTIONS TO BRING TO YOUR CLIENTS",
]
MONITORABLE_TERMS = [
    "track",
    "watch",
    "monitor",
    "follow",
    "filings",
    "aftermarket",
    "issuance",
    "loan spreads",
    "debt",
    "permits",
    "permitting",
    "interconnection",
    "deployment",
    "uptime",
    "unit economics",
    "approval",
]


def _count_terms(text, terms):
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _find_heading_positions(text, headings):
    positions = {}
    for heading in headings:
        match = re.search(rf"(?im)^\s*{re.escape(heading)}\s*$", text)
        if match:
            positions[heading] = match.start()
    return positions


def _section_text(text, heading, following_headings):
    heading_match = re.search(rf"(?im)^\s*{re.escape(heading)}\s*$", text)
    if not heading_match:
        return ""
    start = heading_match.end()
    end = len(text)
    for next_heading in following_headings:
        next_match = re.search(rf"(?im)^\s*{re.escape(next_heading)}\s*$", text[start:])
        if next_match:
            end = start + next_match.start()
            break
    return text[start:end].strip()


def _numbered_items(section):
    return [
        match.group(0).strip()
        for match in re.finditer(r"(?ms)^\s*\d+\.\s+.*?(?=^\s*\d+\.\s+|\Z)", section)
    ]


def _all_numbered_items(text):
    return [
        match.group(0).strip()
        for match in re.finditer(r"(?ms)^\s*\d+\.\s+.*?(?=^\s*\d+\.\s+|^[A-Z][A-Z0-9 /]+$|\Z)", text)
    ]


def _is_frontier_capital_markets_text(text):
    lowered = text.lower()
    capital_terms = [
        "ipo",
        "initial public offering",
        "direct listing",
        "secondary offering",
        "tender offer",
        "private-market liquidity",
        "private market liquidity",
        "liquidity event",
        "funding round",
        "growth equity",
        "private credit",
        "debt facility",
        "valuation reset",
        "acquisition",
        "merger",
    ]
    frontier_terms = [
        "spacex",
        "starlink",
        "space technology",
        "satellite communications",
        "satellite",
        "defense",
        "autonomy",
        "edge connectivity",
    ]
    return any(term in lowered for term in capital_terms) and any(term in lowered for term in frontier_terms)


def _has_honest_frontier_framing(text):
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "not a pure gen ai story",
            "ai-adjacent",
            "ai adjacent",
            "broader innovation cycle",
            "frontier technology",
        ]
    )


def validate_weekly_digest_text(text):
    issues = []
    stripped = text.strip()

    if len(stripped) < 1200:
        issues.append("Weekly output appears unusually short")
    if len(stripped) > 50000:
        issues.append("Weekly output appears unusually long")

    if RECOMMENDATION_RE.search(stripped):
        issues.append("Explicit recommendation language detected")
    if PERFORMANCE_PROMISE_RE.search(stripped):
        issues.append("Performance promise language detected")

    heading_positions = _find_heading_positions(stripped, REQUIRED_WHOLESALER_HEADINGS)
    if heading_positions:
        missing_headings = [
            heading for heading in REQUIRED_WHOLESALER_HEADINGS if heading not in heading_positions
        ]
        if missing_headings:
            issues.append("Missing weekly section headings: " + ", ".join(missing_headings))
        found_in_order = [
            heading for heading in REQUIRED_WHOLESALER_HEADINGS if heading in heading_positions
        ]
        if found_in_order != sorted(found_in_order, key=lambda heading: heading_positions[heading]):
            issues.append("Weekly section headings are out of expected order")

    watch_section = _section_text(
        stripped,
        "WHAT TO WATCH NEXT",
        ["READY TO USE SOUNDBITES", "QUESTIONS TO BRING TO YOUR CLIENTS", "AI PRACTICE TIP OF THE WEEK"],
    )
    if not watch_section:
        issues.append("WHAT TO WATCH NEXT section missing")
    else:
        watch_items = _numbered_items(watch_section)
        if not 4 <= len(watch_items) <= 6:
            issues.append("WHAT TO WATCH NEXT should include 4 to 6 monitorable indicators")
        if watch_items and _count_terms(watch_section, MONITORABLE_TERMS) < 2:
            issues.append("WHAT TO WATCH NEXT lacks monitorable indicator language")

    frontier_items = [item for item in _all_numbered_items(stripped) if _is_frontier_capital_markets_text(item)]
    if any(not _has_honest_frontier_framing(item) for item in frontier_items):
        issues.append("Frontier technology capital markets discussion needs honest AI-adjacent framing")

    local_data_center_mentions = len(
        re.findall(r"\b(local|county|city council|zoning|permitting)\b.{0,80}\bdata centers?\b|\bdata centers?\b.{0,80}\b(local|county|city council|zoning|permitting)\b", stripped, flags=re.IGNORECASE)
    )
    if local_data_center_mentions > 3 and "broader" not in stripped.lower() and "pattern" not in stripped.lower():
        issues.append("Weekly output may overuse local data-center examples without broader synthesis")

    synthesis_score = _count_terms(stripped, SYNTHESIS_TERMS)
    if synthesis_score < 3:
        issues.append("Weekly output may be aggregating headlines rather than synthesizing patterns")

    adoption_score = _count_terms(stripped, FORWARD_ADOPTION_TERMS)
    if adoption_score < 2:
        issues.append("Weekly output does not clearly consider forward-looking AI adoption signals")

    advisor_score = _count_terms(stripped, ADVISOR_TERMS)
    if advisor_score < 2:
        issues.append("Weekly output lacks advisor/wholesaler-usable language")

    ticker_count = len(SINGLE_STOCK_RE.findall(stripped))
    theme_score = _count_terms(stripped, THEME_TERMS)
    if ticker_count >= 12 and theme_score < 4:
        issues.append("Weekly output may overuse single-stock commentary without enough broader theme language")

    headline_like_lines = [
        line for line in stripped.splitlines()
        if len(line.strip()) > 25 and line.strip().isupper()
    ]
    numbered_lines = [
        line for line in stripped.splitlines()
        if re.match(r"^\s*\d+\.\s+", line)
    ]
    if len(headline_like_lines) > 0 and len(numbered_lines) >= 5:
        avg_words = sum(len(line.split()) for line in numbered_lines) / len(numbered_lines)
        if avg_words < 12:
            issues.append("Weekly numbered items look too headline-like for synthesis")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate a saved weekly digest text file.")
    parser.add_argument("path", help="Path to the weekly digest text output")
    args = parser.parse_args()

    text = Path(args.path).read_text(encoding="utf-8")
    issues = validate_weekly_digest_text(text)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1

    print("Weekly digest validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
