#!/usr/bin/env python3
"""Validate assembled prompt packages before publication."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL_MARKERS = [
    "# Prompt Package",
    "## Selected Sector",
    "## Core System Prompt",
    "## Sector Adapter",
    "## User Prompt",
]

HEALTHCARE_REQUIRED_MARKERS = [
    "### A. Clinical and Administrative Workflow",
    "### B. Biotechnology and Therapeutic Development",
    "### C. Diagnostic Intelligence at Scale",
    "### D. In-Home Healthcare and Physical AI",
    "Do not let the report become mostly about documentation and administrative automation.",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt package not found: {path}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an assembled prompt package before uploading or model invocation."
    )
    parser.add_argument(
        "--prompt-package",
        required=True,
        type=Path,
        help="Path to the assembled prompt package markdown file.",
    )
    parser.add_argument(
        "--sector-name",
        required=True,
        help="Sector name associated with the prompt package.",
    )
    return parser.parse_args()


def validate_markers(text: str, markers: list[str]) -> list[str]:
    missing = []
    for marker in markers:
        if marker not in text:
            missing.append(marker)
    return missing


def main() -> int:
    args = parse_args()

    try:
        prompt_text = read_text(args.prompt_package)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    missing = validate_markers(prompt_text, REQUIRED_TOP_LEVEL_MARKERS)
    if missing:
        print("Prompt package is missing required top-level sections:", file=sys.stderr)
        for marker in missing:
            print(f"- {marker}", file=sys.stderr)
        return 1

    normalized_sector = args.sector_name.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized_sector == "healthcare":
        missing = validate_markers(prompt_text, HEALTHCARE_REQUIRED_MARKERS)
        if missing:
            print(
                "Healthcare prompt package failed validation. Missing required analytical pillars or guardrails:",
                file=sys.stderr,
            )
            for marker in missing:
                print(f"- {marker}", file=sys.stderr)
            return 1

    print(f"Prompt package validation passed for sector '{args.sector_name}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
