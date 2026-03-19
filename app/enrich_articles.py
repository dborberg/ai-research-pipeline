import json
import sqlite3
import os
import time
import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = "data/ai_research.db"

# Ensure DB exists
if not os.path.exists("data"):
    os.makedirs("data")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Ensure table + columns exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedly_id TEXT UNIQUE,
    title TEXT,
    source TEXT,
    url TEXT,
    published_at TEXT,
    created_at TEXT,
    summary TEXT,
    themes TEXT,
    companies TEXT,
    advisor_relevance TEXT,
    ai_score INTEGER
)
""")

# Add missing columns safely (for existing DBs)
def add_column_if_missing(column_name, column_type):
    cursor.execute("PRAGMA table_info(articles)")
    columns = [col[1] for col in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}")

add_column_if_missing("summary", "TEXT")
add_column_if_missing("themes", "TEXT")
add_column_if_missing("companies", "TEXT")
add_column_if_missing("advisor_relevance", "TEXT")
add_column_if_missing("ai_score", "INTEGER")

conn.commit()

# Fetch articles needing enrichment
cursor.execute("""
SELECT rowid, title
FROM articles
WHERE summary IS NULL
   OR themes IS NULL
   OR companies IS NULL
   OR advisor_relevance IS NULL
   OR ai_score IS NULL
LIMIT 10
""")

articles = cursor.fetchall()

print(f"Articles to enrich: {len(articles)}")

for rowid, title in articles:

    system_message = """You are a senior AI research analyst writing for mutual fund wholesalers. 
Your job is to analyze AI-related news and produce structured insights usable in advisor conversations. 
Keep language clear, factual, and consistent."""

    user_message = f"""Article title: {title}

Produce structured output with exactly these fields:

{{
  "summary": "2-3 sentence summary",
  "themes": ["3-5 key themes"],
  "companies": ["companies mentioned"],
  "advisor_relevance": "why this matters",
  "ai_score": number between 1 and 10
}}

Return ONLY valid JSON. No extra text.
"""

    parsed = None
    response_text = None

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
            )

            response_text = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(response_text)
            except:
                # try to extract JSON block
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(response_text[start:end+1])
                    except:
                        pass

            if parsed:
                break

            time.sleep(1)

        except Exception as e:
            print(f"API error: {e}")
            time.sleep(1)

    if not parsed:
        print(f"❌ Failed: {title}")
        continue

    try:
        summary = parsed.get("summary")
        themes = parsed.get("themes") or []
        companies = parsed.get("companies") or []
        advisor_relevance = parsed.get("advisor_relevance")
        ai_score = parsed.get("ai_score")

        # Normalize lists
        if isinstance(themes, str):
            themes = [themes]
        if isinstance(companies, str):
            companies = [companies]

        # Validate score
        try:
            ai_score = int(ai_score)
            if ai_score < 1 or ai_score > 10:
                ai_score = None
        except:
            ai_score = None

        cursor.execute("""
        UPDATE articles
        SET summary = ?, themes = ?, companies = ?, advisor_relevance = ?, ai_score = ?
        WHERE rowid = ?
        """,
        (
            summary,
            json.dumps(themes),
            json.dumps(companies),
            advisor_relevance,
            ai_score,
            rowid,
        ))

        print(f"✓ Enriched: {title[:60]}")

    except Exception as e:
        print(f"❌ Error processing {title}: {e}")

conn.commit()
conn.close()

# Save timestamp
timestamp = datetime.datetime.now().isoformat()
with open("data/.last_refresh", "w") as f:
    f.write(timestamp)

print("Enrichment complete")
print(f"Timestamp saved: {timestamp}")