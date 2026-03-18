import json
import sqlite3
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = "data/articles.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
SELECT rowid, title
FROM articles
WHERE themes IS NULL OR companies IS NULL OR advisor_relevance IS NULL OR ai_score IS NULL
LIMIT 10
""")

articles = cursor.fetchall()

print(f"Articles to enrich: {len(articles)}")

for rowid, title in articles:

    system_message = """You are a senior AI research analyst writing for mutual fund wholesalers. Your job is to analyze AI-related news and produce structured insights that are directly usable in advisor conversations. Keep language clear, factual, and practical. Be consistent across articles in structure and level of detail. Do not repeat section headers inside the content fields."""

    user_message = f"""Article title: {title}

Produce structured output with exactly these sections:

SUMMARY
2–3 sentences, clear and factual

THEMES
3–5 bullet points capturing the most important underlying trends

COMPANIES
List specific companies mentioned or clearly implied

ADVISOR RELEVANCE
2–3 sentences explaining why this matters for financial advisors and their clients

AI IMPORTANCE SCORE
Score from 1–10 based on:
- Market impact
- Relevance to portfolios
- Strategic importance

Return ONLY valid JSON in this format:

{{
  "summary": "string",
  "themes": ["string"],
  "companies": ["string"],
  "advisor_relevance": "string",
  "ai_score": number
}}

Do not include any additional text. Do not include section labels like 'Summary:' or 'Themes:' inside the field values."""

    response_text = None
    parsed = None

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
            )

            response_text = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(response_text)
            except Exception as e:
                print(f"Attempt {attempt + 1} parse failed: {e}")
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        parsed = json.loads(response_text[start : end + 1])
                    except Exception:
                        pass

            if parsed:
                break

            if attempt == 0:
                time.sleep(1)

        except Exception as e:
            print(f"API call failed on attempt {attempt + 1}: {e}")
            if attempt == 0:
                time.sleep(1)

    if not parsed:
        print(f"❌ Failed to parse JSON for: {title}")
        print(f"   Response: {response_text[:200] if response_text else 'No response'}")
        continue

    # Validate and extract fields
    try:
        summary = (parsed.get("summary") or "").strip()
        themes = parsed.get("themes") or []
        companies = parsed.get("companies") or []
        advisor_relevance = (parsed.get("advisor_relevance") or "").strip()
        ai_score = parsed.get("ai_score")

        # Ensure lists
        if isinstance(themes, str):
            themes = [t.strip() for t in themes.split("\n") if t.strip()]
        if isinstance(companies, str):
            companies = [c.strip() for c in companies.split("\n") if c.strip()]

        themes = [t for t in themes if t]  # Filter empty strings
        companies = [c for c in companies if c]  # Filter empty strings

        # Convert score to int
        try:
            ai_score = int(ai_score)
            if not (1 <= ai_score <= 10):
                print(f"⚠️  AI score out of range for {title}: {ai_score}")
                ai_score = None
        except Exception:
            print(f"⚠️  Could not convert ai_score to int for {title}: {ai_score}")
            ai_score = None

        # Write to database
        cursor.execute("""
        UPDATE articles
        SET summary = ?, themes = ?, companies = ?, advisor_relevance = ?, ai_score = ?
        WHERE rowid = ?
        """,
        (
            summary if summary else None,
            json.dumps(themes) if themes else None,
            json.dumps(companies) if companies else None,
            advisor_relevance if advisor_relevance else None,
            ai_score,
            rowid,
        ),
        )

        print(f"✓ Enriched: {title[:70]}")

    except Exception as e:
        print(f"❌ Error processing {title}: {e}")
        continue

conn.commit()
conn.close()

print("Enrichment complete")

# Write timestamp of last enrichment
import datetime
timestamp = datetime.datetime.now().isoformat()
with open("data/.last_refresh", "w") as f:
    f.write(timestamp)
print(f"Timestamp saved: {timestamp}")