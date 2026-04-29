#!/usr/bin/env python3
"""Repair malformed saved frontier HTML reports without making a model call."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from app.send_email import send_report
from scripts.generate_sector_report import has_malformed_html_artifacts, repair_common_html_artifacts
from scripts.send_sector_report import build_subject, html_to_plain_text


DEFAULT_REPORT_DIR = REPO_ROOT / "out" / "streamlit"
REPORT_NAME_RE = re.compile(r"^report_(?P<sector>.+?)_frontier_possibilities_(?P<stamp>\d{8}_\d{6})\.html$")
load_dotenv(REPO_ROOT / ".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair malformed saved frontier HTML reports and optionally email corrected copies."
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Directory containing saved Streamlit frontier reports. Defaults to {DEFAULT_REPORT_DIR}.",
    )
    parser.add_argument(
        "--report-path",
        action="append",
        type=Path,
        help="Optional specific report path to repair. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write corrected sibling files with a _repaired suffix.",
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Email corrected report copies using the shared Gmail delivery path.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Repair and resend selected reports even if they are not currently flagged as malformed.",
    )
    return parser.parse_args()


def iter_candidate_reports(report_dir: Path, explicit_paths: list[Path] | None) -> list[Path]:
    if explicit_paths:
        return explicit_paths
    return sorted(report_dir.glob("report_*_frontier_possibilities_*.html"))


def repaired_output_path(path: Path) -> Path:
    return path.with_name(path.stem + "_repaired.html")


def infer_sector_from_filename(path: Path) -> str:
    match = REPORT_NAME_RE.match(path.name)
    if not match:
        raise ValueError(f"Could not infer sector from report filename: {path.name}")
    return match.group("sector")


def repair_report(path: Path) -> tuple[bool, str]:
    original = path.read_text(encoding="utf-8", errors="ignore")
    repaired = repair_common_html_artifacts(original)
    changed = repaired != original
    return changed, repaired


def email_repaired_report(sector: str, html_report: str) -> None:
    send_report(
        subject=f"{build_subject(sector)} [Corrected HTML]",
        body_text=html_to_plain_text(html_report),
        body_html=html_report,
    )


def main() -> int:
    args = parse_args()
    candidates = iter_candidate_reports(args.report_dir, args.report_path)

    if not candidates:
        print("No candidate frontier HTML reports found.")
        return 0

    repaired_count = 0
    for path in candidates:
        if not path.exists():
            print(f"Skipping missing file: {path}", file=sys.stderr)
            continue

        original = path.read_text(encoding="utf-8", errors="ignore")
        malformed = has_malformed_html_artifacts(original)
        if not malformed and not args.force:
            continue

        changed, repaired = repair_report(path)
        if not changed and not args.force:
            continue

        repaired_count += 1
        print(f"Repaired: {path}")

        if args.write:
            output_path = repaired_output_path(path)
            output_path.write_text(repaired, encoding="utf-8")
            print(f"  wrote: {output_path}")

        if args.email:
            sector = infer_sector_from_filename(path)
            email_repaired_report(sector, repaired)
            print(f"  emailed corrected copy for sector: {sector}")

    if repaired_count == 0:
        print("No malformed frontier HTML reports needed repair.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
