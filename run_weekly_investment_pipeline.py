import os
from pathlib import Path
from openai import OpenAI
import smtplib

OUTPUT_DIR = Path("outputs/daily")


def get_last_n_files(n=7):
    files = sorted(OUTPUT_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:n]


def load_content(files):
    return "\n\n".join([f.read_text(encoding="utf-8") for f in files])


def generate_weekly_digest(content):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
You are a senior AI research analyst.

Create a weekly investment digest using the structure below.

TOP 5 STORIES THIS WEEK
BEYOND THE MAG 7
WHAT IS BEING DISRUPTED
REGULATORY RADAR
READY TO USE SOUNDBITES
QUESTIONS TO BRING TO YOUR CLIENTS
AI PRACTICE TIP OF THE WEEK

Content:
{content}
"""

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content


def send_email(body):
    sender = os.getenv("EMAIL_USER")
    to = os.getenv("EMAIL_TO")
    password = os.getenv("EMAIL_PASSWORD")

    subject = "Weekly Investment AI Digest"

    message = f"Subject: {subject}\nFrom: {sender}\nTo: {to}\n\n{body}"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, to, message.encode("utf-8"))


def main():
    files = get_last_n_files(7)
    content = load_content(files)
    digest = generate_weekly_digest(content)
    send_email(digest)


if __name__ == "__main__":
    main()
