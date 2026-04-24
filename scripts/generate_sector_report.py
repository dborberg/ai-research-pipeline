#!/usr/bin/env python3
"""Generate a sector report from an assembled prompt package."""

from __future__ import annotations

import argparse
import os
import re
import sys
from html import escape
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.4"
DEFAULT_MAX_OUTPUT_TOKENS = 2800
DEFAULT_OUTPUT_FORMAT = "markdown"


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
        "- Treat the 'User Prompt' section as the active task and run-specific input layer.\n"
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
                    "context, and the User Prompt as the active task. Return only the "
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
    content = response.choices[0].message.content
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise RuntimeError("The Chat Completions response did not contain any text output.")


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
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Maximum output tokens. Defaults to {DEFAULT_MAX_OUTPUT_TOKENS}.",
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

    client = OpenAI(api_key=api_key)
    generation_errors: list[str] = []

    try:
        report = generate_with_responses_api(
            client=client,
            prompt_package=prompt_package,
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            output_format=args.output_format,
        )
    except Exception as exc:
        generation_errors.append(f"Responses API failed: {exc}")
        try:
            report = generate_with_chat_completions(
                client=client,
                prompt_package=prompt_package,
                model=args.model,
                max_output_tokens=args.max_output_tokens,
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

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.rstrip() + "\n", encoding="utf-8")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
