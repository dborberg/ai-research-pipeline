import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = "data/articles.db"


def generate_daily_digest():
    """Generate the daily digest text using OpenAI.

    This function reads the top 40 articles by ai_score and builds a prompt
    that matches the strict formatting rules defined in the project documentation.
    """

    # Read top 40 articles sorted by ai_score desc
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT title, source, ai_score, coalesce(summary, ''),
               coalesce(themes, ''), coalesce(companies, ''),
               coalesce(advisor_relevance, '')
        FROM articles
        ORDER BY (ai_score IS NULL), ai_score DESC, id DESC
        LIMIT 40
        """
    )
    rows = cursor.fetchall()
    conn.close()

    # Build DATA block
    data_lines = ["DATA:"]
    for row in rows:
        title, source, score, summary, themes, companies, advisor_relevance = row
        data_lines.append("\nArticle:")
        data_lines.append(f"Title: {title}")
        data_lines.append(f"Source: {source}")
        data_lines.append(f"Score: {score}")
        data_lines.append(f"Summary: {summary}")
        data_lines.append(f"Themes: {themes}")
        data_lines.append(f"Companies: {companies}")
        data_lines.append(f"Advisor Relevance: {advisor_relevance}")

    data_block = "\n".join(data_lines)

    system_message = (
        "You are an AI research analyst producing a daily briefing for financial advisors "
        "and mutual fund wholesalers. Distill generative AI news into clear, concise, "
        "professionally written summaries that a non-technical financial professional "
        "can understand and act on. Present both opportunities and risks where "
        "appropriate. Ensure emerging physical AI and robotics developments are included "
        "when strategically meaningful to industrial automation, logistics, defense, or "
        "public market exposure. If article content appears incomplete or missing, skip "
        "that article silently and summarize only what was provided. Do not use markdown "
        "formatting in your response. Use plain text only.\n\n"
        "Responses must be in bullet point format only. Write concise sound bites suitable "
        "for sharing directly with sales teams and advisors. Avoid long paragraphs. "
        "Maintain a professional, forward-looking tone. Cite the source publication for "
        "each bullet point using parentheses."
    )

    user_message = (
        "CRITICAL INSTRUCTION: Your response must contain EXACTLY these 8 section headers in "
        "EXACTLY this order. Each header must appear on its own line in ALL CAPS. You are "
        "forbidden from combining sections, renaming sections, or omitting sections.\n\n"
        "For each section: write 2–5 bullets when relevant material exists. If and only if there "
        "are zero relevant items, write exactly: \"Nothing to report today.\" Do not write that "
        "line if you included any bullets.\n\n"
        "If the input contains any material related to robotics, physical AI, humanoid systems, "
        "warehouse automation, autonomous systems, or industrial AI, you MUST include at least "
        "one substantive bullet under PHYSICAL AI AND ROBOTICS summarizing the most strategically "
        "meaningful development for investors.\n\n"
        "TOP STORIES\n"
        "ENTERPRISE AND LABOR\n"
        "INFRASTRUCTURE AND POWER\n"
        "CAPITAL MARKETS AND INVESTMENT\n"
        "REGULATION AND POLICY\n"
        "PHYSICAL AI AND ROBOTICS\n"
        "WHAT TO WATCH\n"
        "ADVISOR SOUNDBITES\n\n"
        "Append DATA in this format:\n\n"
        "DATA:\n\n"
        f"{data_block}\n"
        "\nEnsure:\n"
        "- Output is plain text (no JSON)\n"
        "- Do not modify formatting\n"
        "- Return response directly\n"
    )

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    # Return raw text response
    digest_text = response.choices[0].message.content.strip()

    # Persist digest to a file for dashboard access
    save_daily_digest(digest_text)

    return digest_text


def save_daily_digest(digest_text, output_dir="outputs/daily"):
    """Save the digest text to a dated file."""
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.utcnow().date().isoformat()
    file_path = os.path.join(output_dir, f"{today}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(digest_text)

    return file_path
