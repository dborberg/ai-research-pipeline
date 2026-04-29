#!/usr/bin/env python3
"""Generate a sector report from an assembled prompt package."""

from __future__ import annotations

import argparse
import os
import re
import sys
from html import escape, unescape
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.reporting import get_openai_client


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_MAX_OUTPUT_TOKENS = 2800
FRONTIER_MAX_OUTPUT_TOKENS = 3600
DEFAULT_OUTPUT_FORMAT = "markdown"
FRONTIER_REQUIRED_HEADINGS = [
    "Executive Summary",
    "The Big Shift",
    "Near-Term Possibilities: 1-3 Years",
    "Medium-Term Possibilities: 3-7 Years",
    "Frontier Scenario: A Day in the Life",
    "Reality Check",
    "Most Important Boundaries",
    "Bottom Line",
]
FRONTIER_SECTION_BUDGET_GUIDANCE = (
    "Keep the overall report concise enough to finish cleanly. "
    "Use 2-3 short paragraphs for Executive Summary, 1-2 compact paragraphs for The Big Shift, "
    "3-4 concise use cases in Near-Term Possibilities, 3-4 concise use cases in Medium-Term Possibilities, "
    "2-3 short paragraphs for Frontier Scenario: A Day in the Life, 1 concise paragraph or tight bullets for Reality Check, "
    "4-5 brief bullets for Most Important Boundaries, and 2 short paragraphs for Bottom Line."
)


def get_max_output_tokens_for_mode(report_mode: str) -> int:
    if report_mode == "frontier_possibilities":
        return FRONTIER_MAX_OUTPUT_TOKENS
    return DEFAULT_MAX_OUTPUT_TOKENS


def get_max_output_tokens_for_prompt(prompt_package: str) -> int:
    if is_frontier_prompt_package(prompt_package):
        return FRONTIER_MAX_OUTPUT_TOKENS
    return DEFAULT_MAX_OUTPUT_TOKENS


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt package not found: {path}") from exc


def build_execution_prompt(prompt_package: str, output_format: str) -> str:
    output_instructions = (
        "Return only the finished report in markdown.\n"
        "- Aim for the lower half of the allowed report length unless the prompt explicitly requires more detail.\n"
        "- Prioritize a complete report over extra detail if there is any risk of truncation.\n"
        "- Do not end with unfinished bullets, unfinished sentences, or incomplete sections.\n"
        "- Ensure the Bottom Line section is fully completed.\n"
        "- Do not add meta commentary about the prompt package.\n"
    )

    if output_format == "html":
        output_instructions = (
            "Return only the finished report as complete HTML.\n"
            "- Use semantic tags such as <html>, <body>, <h1>, <h2>, <p>, <ul>, and <li>.\n"
            "- Make the HTML email-friendly with simple inline styling only.\n"
            "- Aim for the lower half of the allowed report length unless the prompt explicitly requires more detail.\n"
            "- Prioritize a complete report over extra detail if there is any risk of truncation.\n"
            "- Do not end with unfinished bullets, unfinished sentences, incomplete sections, or incomplete HTML.\n"
            "- Ensure the Bottom Line section is fully completed.\n"
            "- Do not wrap the HTML in markdown fences.\n"
            "- Do not add meta commentary about the prompt package.\n"
        )

    return (
        "You are executing an assembled prompt package for a sector-specific "
        "Generative AI report.\n\n"
        "Execution rules:\n"
        "- Treat the 'Core System Prompt' section as the governing instruction layer.\n"
        "- Treat the 'Sector Adapter' section as the sector-specific context layer.\n"
        "- Treat the 'User Prompt' section as the active task, run-specific input layer, and mode-specific override layer when it narrows or redirects the objective.\n"
        f"{output_instructions}\n"
        "Prompt package follows:\n\n"
        f"{prompt_package}"
    )


def extract_text_from_response(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    outputs = getattr(response, "output", None) or []
    collected: list[str] = []

    for item in outputs:
        content_items = getattr(item, "content", None) or []
        for content_item in content_items:
            text_value = getattr(content_item, "text", None)
            if isinstance(text_value, str) and text_value.strip():
                collected.append(text_value.strip())

    if collected:
        return "\n\n".join(collected).strip()

    raise RuntimeError("The model response did not contain any text output.")


def extract_text_from_chat_completion(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("The chat completion response did not contain any choices.")

    message = getattr(choices[0], "message", None)
    if message is None:
        raise RuntimeError("The chat completion response did not contain a message.")

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    collected: list[str] = []
    if isinstance(content, (list, tuple)):
        for part in content:
            if isinstance(part, str) and part.strip():
                collected.append(part.strip())
                continue

            text_value = getattr(part, "text", None)
            if isinstance(text_value, str) and text_value.strip():
                collected.append(text_value.strip())
                continue

            if isinstance(part, dict):
                direct_text = part.get("text")
                if isinstance(direct_text, str) and direct_text.strip():
                    collected.append(direct_text.strip())
                    continue

                nested_text = part.get("text", {})
                if isinstance(nested_text, dict):
                    value = nested_text.get("value")
                    if isinstance(value, str) and value.strip():
                        collected.append(value.strip())

    if collected:
        return "\n\n".join(collected).strip()

    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        raise RuntimeError(f"The model refused to provide text output: {refusal.strip()}")

    raise RuntimeError("The chat completion response did not contain any text output.")


def normalize_html_output(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^```html\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^```\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)

    if "<html" in stripped.lower():
        return stripped

    if "<body" in stripped.lower():
        return f"<html>{stripped}</html>"

    if re.search(r"(?i)<(h1|h2|h3|p|ul|ol|li|div|section|article)\b", stripped):
        return (
            "<html><body style=\"font-family: Arial, sans-serif; font-size: 14px; "
            "line-height: 1.6; color: #111827;\">"
            f"{stripped}"
            "</body></html>"
        )

    escaped = escape(stripped)
    escaped = escaped.replace("\n\n", "</p><p>").replace("\n", "<br />")
    body = (
        "<html><body style=\"font-family: Arial, sans-serif; font-size: 14px; "
        "line-height: 1.6; color: #111827;\">"
        f"<p>{escaped}</p>"
        "</body></html>"
    )
    return body


def normalize_markdown_output(text: str) -> str:
    return text.strip()


def is_frontier_prompt_package(prompt_package: str) -> bool:
    return "This is the Frontier Possibilities version" in prompt_package


def strip_html_for_validation(text: str) -> str:
    stripped = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    stripped = re.sub(r"(?is)<style.*?>.*?</style>", " ", stripped)
    stripped = re.sub(r"(?i)<br\\s*/?>", "\n", stripped)
    stripped = re.sub(r"</(p|div|h1|h2|h3|h4|h5|h6|li|section|article)>", "\n", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = unescape(stripped)
    stripped = re.sub(r"[ \t]+", " ", stripped)
    stripped = re.sub(r"\n+", "\n", stripped)
    return stripped


def get_missing_frontier_headings(report_text: str) -> list[str]:
    normalized = strip_html_for_validation(report_text)
    return [heading for heading in FRONTIER_REQUIRED_HEADINGS if heading not in normalized]


def repair_frontier_report(
    client: OpenAI,
    prompt_package: str,
    current_report: str,
    model: str,
    output_format: str,
    max_output_tokens: int,
) -> str:
    format_instruction = "markdown"
    if output_format == "html":
        format_instruction = "HTML suitable for email delivery"

    required_headings = "\n".join(f"- {heading}" for heading in FRONTIER_REQUIRED_HEADINGS)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "developer",
                "content": (
                    "You are repairing a frontier possibilities report so it matches the required structure exactly. "
                    "Preserve grounded content, keep the tone imaginative but credible, avoid fabricated facts, "
                    "and return only the revised report."
                ),
            },
            {
                "role": "user",
                "content": (
                    "The following frontier report draft is missing required headings or used substitute headings. "
                    f"Rewrite it in {format_instruction} using exactly these headings:\n"
                    f"{required_headings}\n\n"
                    "Keep the report grounded, sector-specific, and complete. "
                    f"{FRONTIER_SECTION_BUDGET_GUIDANCE} "
                    "Do not leave any section unfinished. "
                    "Do not add fabricated products, partnerships, financial figures, adoption statistics, or regulatory claims.\n\n"
                    "Prompt package:\n"
                    f"{prompt_package}\n\n"
                    "Current draft:\n"
                    f"{current_report}"
                ),
            },
        ],
        max_completion_tokens=max_output_tokens,
    )
    return extract_text_from_chat_completion(response)


def generate_missing_frontier_sections(
    client: OpenAI,
    prompt_package: str,
    current_report: str,
    missing_headings: list[str],
    model: str,
    output_format: str,
    max_output_tokens: int,
) -> str:
    format_instruction = "markdown"
    if output_format == "html":
        format_instruction = "HTML suitable for email delivery"

    missing_heading_list = "\n".join(f"- {heading}" for heading in missing_headings)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "developer",
                "content": (
                    "You are completing a frontier possibilities report that was truncated before its final required sections. "
                    "Return only the missing sections, using exactly the required headings and no extra preamble."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write only these missing sections in {format_instruction}:\n"
                    f"{missing_heading_list}\n\n"
                    f"{FRONTIER_SECTION_BUDGET_GUIDANCE} "
                    "Keep the output concise, grounded, and internally consistent with the existing report. "
                    "Do not restate earlier sections. Do not fabricate products, partnerships, financial figures, adoption statistics, or regulatory claims.\n\n"
                    "Prompt package:\n"
                    f"{prompt_package}\n\n"
                    "Existing report:\n"
                    f"{current_report}"
                ),
            },
        ],
        max_completion_tokens=max_output_tokens,
    )
    return extract_text_from_chat_completion(response)


def append_missing_frontier_sections(
    current_report: str,
    missing_sections: str,
    output_format: str,
) -> str:
    if output_format != "html":
        return current_report.rstrip() + "\n\n" + missing_sections.strip()

    report = current_report.rstrip()
    additions = missing_sections.strip()

    if not additions:
        return report

    if "<html" not in additions.lower():
        additions = normalize_html_output(additions)

    body_match = re.search(r"(?is)<body[^>]*>(.*)</body>", additions)
    body_content = body_match.group(1).strip() if body_match else additions

    closing_body = re.search(r"(?is)</body>\s*</html>\s*$", report)
    if closing_body:
        insertion_point = closing_body.start()
        return report[:insertion_point] + body_content + "\n</body></html>"

    closing_html = re.search(r"(?is)</html>\s*$", report)
    if closing_html:
        insertion_point = closing_html.start()
        return report[:insertion_point] + body_content + "\n</html>"

    return report + body_content


def generate_with_responses_api(
    client: OpenAI,
    prompt_package: str,
    model: str,
    max_output_tokens: int,
    output_format: str,
) -> str:
    response = client.responses.create(
        model=model,
        input=build_execution_prompt(prompt_package, output_format),
        max_output_tokens=max_output_tokens,
    )
    return extract_text_from_response(response)


def generate_with_chat_completions(
    client: OpenAI,
    prompt_package: str,
    model: str,
    max_output_tokens: int,
    output_format: str,
) -> str:
    format_instruction = "finished markdown report"
    if output_format == "html":
        format_instruction = (
            "complete HTML report suitable for email delivery, using semantic HTML "
            "tags and simple inline styling, with no markdown fences"
        )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "developer",
                "content": (
                    "Execute the supplied prompt package. Treat the Core System Prompt "
                    "as the governing instructions, the Sector Adapter as the sector "
                    "context, and the User Prompt as the active task and mode-specific "
                    "override layer when it narrows or redirects the objective. Return only the "
                    f"{format_instruction}. Aim for the lower half of the allowed "
                    "length range, prioritize completion over extra detail, do not end "
                    "with unfinished bullets or sentences, and ensure the Bottom Line "
                    "section is fully completed."
                ),
            },
            {"role": "user", "content": prompt_package},
        ],
        max_completion_tokens=max_output_tokens,
    )
    return extract_text_from_chat_completion(response)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a sector report from an assembled prompt package."
    )
    parser.add_argument(
        "--prompt-package",
        required=True,
        type=Path,
        help="Path to the assembled prompt package markdown file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file for the generated report. Prints to stdout if omitted.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use for generation. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "html"],
        default=DEFAULT_OUTPUT_FORMAT,
        help=f"Output format for the generated report. Defaults to {DEFAULT_OUTPUT_FORMAT}.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        help=(
            "Optional maximum output tokens override. "
            f"Defaults to {DEFAULT_MAX_OUTPUT_TOKENS} for investable prompts and "
            f"{FRONTIER_MAX_OUTPUT_TOKENS} for frontier prompts."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            "OPENAI_API_KEY must be set to generate a sector report.",
            file=sys.stderr,
        )
        return 1

    try:
        prompt_package = read_text(args.prompt_package)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    client = get_openai_client(api_key)
    generation_errors: list[str] = []
    max_output_tokens = args.max_output_tokens or get_max_output_tokens_for_prompt(prompt_package)

    try:
        report = generate_with_responses_api(
            client=client,
            prompt_package=prompt_package,
            model=args.model,
            max_output_tokens=max_output_tokens,
            output_format=args.output_format,
        )
    except Exception as exc:
        generation_errors.append(f"Responses API failed: {exc}")
        try:
            client = get_openai_client(api_key)
            report = generate_with_chat_completions(
                client=client,
                prompt_package=prompt_package,
                model=args.model,
                max_output_tokens=max_output_tokens,
                output_format=args.output_format,
            )
        except Exception as fallback_exc:
            generation_errors.append(f"Chat Completions fallback failed: {fallback_exc}")
            print("\n".join(generation_errors), file=sys.stderr)
            return 1

    if args.output_format == "html":
        report = normalize_html_output(report)
    else:
        report = normalize_markdown_output(report)

    if is_frontier_prompt_package(prompt_package):
        missing_headings = get_missing_frontier_headings(report)
        if missing_headings:
            try:
                repaired = repair_frontier_report(
                    client=client,
                    prompt_package=prompt_package,
                    current_report=report,
                    model=args.model,
                    output_format=args.output_format,
                    max_output_tokens=max_output_tokens,
                )
            except Exception:
                repaired = ""
            if repaired:
                if args.output_format == "html":
                    report = normalize_html_output(repaired)
                else:
                    report = normalize_markdown_output(repaired)
                missing_headings = get_missing_frontier_headings(report)
        if missing_headings:
            additions = generate_missing_frontier_sections(
                client=client,
                prompt_package=prompt_package,
                current_report=report,
                missing_headings=missing_headings,
                model=args.model,
                output_format=args.output_format,
                max_output_tokens=max_output_tokens,
            )
            report = append_missing_frontier_sections(
                current_report=report,
                missing_sections=additions,
                output_format=args.output_format,
            )
            if args.output_format == "html":
                report = normalize_html_output(report)
            else:
                report = normalize_markdown_output(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.rstrip() + "\n", encoding="utf-8")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
