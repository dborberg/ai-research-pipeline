#!/usr/bin/env python3
"""Assemble a sector-specific Generative AI investment report prompt package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
SECTORS_DIR = PROMPTS_DIR / "sectors"
CORE_PROMPT_PATH = PROMPTS_DIR / "core_system_prompt.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_prompt_template.md"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required prompt file not found: {path}") from exc


def list_available_sectors() -> list[str]:
    if not SECTORS_DIR.exists():
        return []
    return sorted(path.stem for path in SECTORS_DIR.glob("*.md"))


def normalize_sector_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def build_prompt_package(
    sector: str,
    audience: str,
    time_horizon: str,
    style_notes: str,
    special_instructions: str,
) -> str:
    normalized_sector = normalize_sector_name(sector)
    sector_path = SECTORS_DIR / f"{normalized_sector}.md"
    available_sectors = list_available_sectors()

    if not sector_path.exists():
        available = ", ".join(available_sectors) if available_sectors else "none found"
        raise FileNotFoundError(
            f"Sector adapter not found for '{sector}'. "
            f"Expected file: {sector_path}. "
            f"Available sectors: {available}"
        )

    replacements = {
        "sector_name": sector,
        "time_horizon": time_horizon,
        "audience": audience,
        "style_notes": style_notes or "None provided.",
        "special_instructions": special_instructions or "None provided.",
    }

    core_prompt = read_text(CORE_PROMPT_PATH)
    sector_prompt = read_text(sector_path)
    user_template = render_template(read_text(USER_TEMPLATE_PATH), replacements)

    return "\n\n".join(
        [
            "# Prompt Package",
            f"## Selected Sector\n\n{sector}",
            "## Core System Prompt\n\n" + core_prompt,
            "## Sector Adapter\n\n" + sector_prompt,
            "## User Prompt\n\n" + user_template,
        ]
    ).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a sector-specific prompt package for Generative AI investment impact reports."
    )
    parser.add_argument(
        "sector",
        nargs="?",
        help="Sector name or sector adapter filename stem.",
    )
    parser.add_argument(
        "--audience",
        default="financial advisors and investment professionals",
        help="Audience description for the report.",
    )
    parser.add_argument(
        "--time-horizon",
        dest="time_horizon",
        default="1-3 years and 3-7 years",
        help="Time horizon to emphasize in the report.",
    )
    parser.add_argument(
        "--style-notes",
        default="",
        help="Optional style notes passed into the user prompt.",
    )
    parser.add_argument(
        "--special-instructions",
        default="",
        help="Optional run-specific instructions passed into the user prompt.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path for the assembled prompt package. Prints to stdout if omitted.",
    )
    parser.add_argument(
        "--list-sectors",
        action="store_true",
        help="List available sector adapter names and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_sectors:
        sectors = list_available_sectors()
        if not sectors:
            print("No sector adapters found.", file=sys.stderr)
            return 1
        print("\n".join(sectors))
        return 0

    if not args.sector:
        print(
            "A sector name is required unless --list-sectors is used.",
            file=sys.stderr,
        )
        return 1

    try:
        prompt_package = build_prompt_package(
            sector=args.sector,
            audience=args.audience,
            time_horizon=args.time_horizon,
            style_notes=args.style_notes,
            special_instructions=args.special_instructions,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt_package, encoding="utf-8")
    else:
        print(prompt_package)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
