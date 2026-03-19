import time
import os
import requests
import sqlite3
from dotenv import load_dotenv

load_dotenv()

FEEDLY_TOKEN = os.getenv("FEEDLY_TOKEN")

# Replace this with your stream id
STREAM_ID = "user/6e33c753-43bd-4085-bbc6-96fde9d420e6/category/27493d69-ee3e-4c45-8668-463d4be7b8b6"

DB_PATH = "data/articles.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedly_id TEXT UNIQUE,
    title TEXT,
    url TEXT,
    source TEXT,
    published INTEGER
)
""")

headers = {
    "Authorization": f"Bearer {FEEDLY_TOKEN}"
}

now = int(time.time() * 1000)
one_day_ago = now - (24 * 60 * 60 * 1000)

url = "https://cloud.feedly.com/v3/streams/contents"

params = {
    "streamId": STREAM_ID,
    "count": 50,
    "newerThan": one_day_ago
}

print("Fetching articles from Feedly...")

response = requests.get(url, headers=headers, params=params)

print("Status code:", response.status_code)

data = response.json()

items = data.get("items", [])

print("Articles returned:", len(items))

for a in items[:5]:
    print(a.get("title"), a.get("published"))

inserted = 0

for entry in items:

    feedly_id = entry.get("id")
    title = entry.get("title")

    article_url = None
    if entry.get("alternate"):
        article_url = entry["alternate"][0].get("href")

    published = entry.get("published")

    source = None
    if entry.get("origin"):
        source = entry["origin"].get("title")

    cursor.execute("""
    IINSERT OR IGNORE INTO articles
    (feedly_id, title, url, source, published)
    VALUES (?, ?, ?, ?, ?)
    """, (feedly_id, title, article_url, source, published))

    if cursor.rowcount > 0:
        inserted += 1

conn.commit()
conn.close()

print("Articles inserted:", inserted)
