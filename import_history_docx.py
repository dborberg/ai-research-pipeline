import argparse
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from app.db import init_db, upsert_daily_digest, upsert_weekly_digest


DOCX_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DATE_HEADER_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$"
)
WEEKLY_FILENAME_RE = re.compile(r"weekly_riffs_(\d{4}-\d{2}-\d{2})\.docx$")


def _read_docx_paragraphs(path):
    with ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//w:p", DOCX_NAMESPACE):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", DOCX_NAMESPACE)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _split_daily_entries(paragraphs):
    entries = []
    current_date = None
    current_lines = []

    for paragraph in paragraphs:
        if DATE_HEADER_RE.match(paragraph):
            if current_date and current_lines:
                entries.append((current_date, "\n".join(current_lines).strip()))
            current_date = datetime.strptime(paragraph, "%B %d, %Y").date()
            current_lines = [paragraph]
            continue

        if current_date is None:
            continue

        current_lines.append(paragraph)

    if current_date and current_lines:
        entries.append((current_date, "\n".join(current_lines).strip()))

    return entries


def import_daily_history(path):
    paragraphs = _read_docx_paragraphs(path)
    entries = _split_daily_entries(paragraphs)
    for digest_date, content in entries:
        upsert_daily_digest(digest_date, content)
    return len(entries)


def import_weekly_history(path):
    match = WEEKLY_FILENAME_RE.search(path.name)
    if not match:
        raise RuntimeError(f"Weekly filename must match weekly_riffs_YYYY-MM-DD.docx: {path.name}")

    week_start = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    content = "\n".join(_read_docx_paragraphs(path)).strip()
    upsert_weekly_digest(week_start, "wholesaler", content)
    return week_start.isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--imports-dir", required=True, help="Directory containing historical DOCX files")
    args = parser.parse_args()

    init_db()

    imports_dir = Path(args.imports_dir).expanduser().resolve()
    daily_path = imports_dir / "daily_riffs_history.docx"
    weekly_paths = sorted(imports_dir.glob("weekly_riffs_*.docx"))

    if not daily_path.exists():
        raise RuntimeError(f"Missing daily history file: {daily_path}")
    if not weekly_paths:
        raise RuntimeError(f"No weekly history files found in {imports_dir}")

    daily_count = import_daily_history(daily_path)
    imported_weeks = [import_weekly_history(path) for path in weekly_paths]

    print(f"Imported {daily_count} daily digests from {daily_path.name}")
    print(f"Imported {len(imported_weeks)} weekly digests: {', '.join(imported_weeks)}")


if __name__ == "__main__":
    main()