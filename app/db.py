from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///data/ai_research.db")

def init_db():

    with engine.connect() as conn:

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            feedly_id TEXT,
            title TEXT,
            source TEXT,
            url TEXT,
            published_at TEXT,
            raw_text TEXT,
            cleaned_text TEXT,
            created_at TEXT
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS article_summaries (
            id INTEGER PRIMARY KEY,
            article_id INTEGER,
            summary_text TEXT,
            created_at TEXT
        )
        """))

        conn.commit()