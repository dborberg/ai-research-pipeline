#!/usr/bin/env python3
"""Assemble a sector-specific Generative AI investment report prompt package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .resolve_sector_focus import SECTOR_FOCUS_OPTIONS, normalize_token
except ImportError:  # pragma: no cover - script execution path
    from resolve_sector_focus import SECTOR_FOCUS_OPTIONS, normalize_token


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
SECTORS_DIR = PROMPTS_DIR / "sectors"
CORE_PROMPT_PATH = PROMPTS_DIR / "core_system_prompt.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_prompt_template.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "out"
DEFAULT_REPORT_MODE = "investment_implications"
BALANCED_FOCUS_LABEL = "a Balanced Sector View"
REPORT_MODE_CONFIG: dict[str, dict[str, Path | str]] = {
    "investment_implications": {
        "label": "Investment Implications",
        "template_path": USER_TEMPLATE_PATH,
    },
    "frontier_possibilities": {
        "label": "Frontier Possibilities",
        "template_path": PROMPTS_DIR / "user_prompt_frontier_possibilities.md",
    },
}


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


def default_output_path(sector: str, report_mode: str) -> Path:
    normalized_sector = normalize_sector_name(sector)
    if report_mode == DEFAULT_REPORT_MODE:
        return DEFAULT_OUTPUT_DIR / f"final_prompt_{normalized_sector}.md"
    return DEFAULT_OUTPUT_DIR / f"final_prompt_{normalized_sector}_{report_mode}.md"


def normalize_report_mode(value: str) -> str:
    normalized_value = normalize_token(value)
    if normalized_value not in REPORT_MODE_CONFIG:
        available_modes = ", ".join(sorted(REPORT_MODE_CONFIG))
        raise ValueError(f"Unsupported report mode '{value}'. Available modes: {available_modes}")
    return normalized_value


def get_report_mode_label(report_mode: str) -> str:
    return str(REPORT_MODE_CONFIG[report_mode]["label"])


def get_report_mode_options() -> dict[str, str]:
    return {
        report_mode: str(config["label"])
        for report_mode, config in REPORT_MODE_CONFIG.items()
    }


def prettify_token(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def get_sector_display_name(sector: str) -> str:
    sector_key = normalize_sector_name(sector)
    sector_config = SECTOR_FOCUS_OPTIONS.get(sector_key)
    if sector_config:
        return str(sector_config["label"])
    return prettify_token(sector)


def get_industry_display_name(sector: str, industry_focus: str) -> str:
    sector_key = normalize_sector_name(sector)
    normalized_focus = normalize_token(industry_focus)
    if normalized_focus == "balanced":
        return BALANCED_FOCUS_LABEL

    sector_config = SECTOR_FOCUS_OPTIONS.get(sector_key)
    if sector_config:
        industry_config = sector_config["industries"].get(normalized_focus)
        if industry_config:
            return str(industry_config["label"])

    return prettify_token(industry_focus)


def get_user_template_path(report_mode: str) -> Path:
    return Path(REPORT_MODE_CONFIG[report_mode]["template_path"])


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
    report_mode: str = DEFAULT_REPORT_MODE,
    industry_focus: str = "balanced",
) -> str:
    normalized_report_mode = normalize_report_mode(report_mode)
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

    sector_display_name = get_sector_display_name(sector)
    industry_display_name = get_industry_display_name(sector, industry_focus)

    replacements = {
        "sector_name": sector,
        "sector_display_name": sector_display_name,
        "industry_name": industry_display_name,
        "time_horizon": time_horizon,
        "audience": audience,
        "style_notes": style_notes or "None provided.",
        "special_instructions": special_instructions or "None provided.",
        "report_mode_label": get_report_mode_label(normalized_report_mode),
    }

    core_prompt = read_text(CORE_PROMPT_PATH)
    sector_prompt = read_text(sector_path)
    user_template = render_template(read_text(get_user_template_path(normalized_report_mode)), replacements)

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
        "--sector-name",
        dest="sector_name",
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
        "--industry-focus",
        default="balanced",
        help="Industry focus slug or balanced. Used for display framing while preserving the existing sector and industry context layering.",
    )
    parser.add_argument(
        "--report-mode",
        default=DEFAULT_REPORT_MODE,
        help="Report mode. Supported values: investment_implications or frontier_possibilities. UI labels such as 'Investment Implications' are also accepted.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path for the assembled prompt package. Defaults to out/final_prompt_<sector>.md for investment implications and a mode-specific filename otherwise.",
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

    sector_name = args.sector_name or args.sector

    if not sector_name:
        print(
            "A sector name is required unless --list-sectors is used. Use either the positional sector argument or --sector-name.",
            file=sys.stderr,
        )
        return 1

    try:
        normalized_report_mode = normalize_report_mode(args.report_mode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        prompt_package = build_prompt_package(
            sector=sector_name,
            audience=args.audience,
            time_horizon=args.time_horizon,
            style_notes=args.style_notes,
            special_instructions=args.special_instructions,
            report_mode=normalized_report_mode,
            industry_focus=args.industry_focus,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = args.output or default_output_path(sector_name, normalized_report_mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt_package, encoding="utf-8")
    print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
