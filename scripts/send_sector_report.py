#!/usr/bin/env python3
"""Email a generated sector report using the shared Gmail delivery path."""

from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.send_email import send_report


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Generated report not found: {path}") from exc


def html_to_plain_text(text: str) -> str:
    plain = re.sub(r"(?i)<br\s*/?>", "\n", text)
    plain = re.sub(r"(?i)</p>|</div>|</h[1-6]>", "\n\n", plain)
    plain = re.sub(r"(?i)</li>", "\n", plain)
    plain = re.sub(r"(?i)<li[^>]*>", "- ", plain)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = unescape(plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def build_subject(sector: str) -> str:
    sector_label = sector.replace("_", " ").title()
    return f"[SECTOR REPORT] Generative AI Impact Report - {sector_label}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a generated HTML sector report via the shared email path."
    )
    parser.add_argument(
        "--sector",
        required=True,
        help="Sector name used to label the subject line.",
    )
    parser.add_argument(
        "--report-path",
        required=True,
        type=Path,
        help="Path to the generated HTML report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        html_report = read_text(args.report_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    plain_report = html_to_plain_text(html_report)
    send_report(
        subject=build_subject(args.sector),
        body_text=plain_report,
        body_html=html_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
