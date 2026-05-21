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


def _count_terms(text, terms):
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


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
