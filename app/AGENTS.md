Project goal:
Build an automated AI research ingestion and analysis pipeline.

Architecture:
- ingestion layer (RSS, APIs)
- storage (SQLite)
- processing (LLM enrichment)
- output (email digests)

Rules:
- Do not rely on a single data provider
- Prefer modular functions over monolithic scripts
- Always return structured data
- Handle errors gracefully per source

Dev commands:
- Run pipeline: python run_pipeline.py
- Test ingestion: python app/test_feedly_auth.py

Current priority:
Replace Feedly ingestion with RSS-based ingestion.