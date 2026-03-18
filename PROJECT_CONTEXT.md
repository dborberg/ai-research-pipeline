PROJECT: AI Research Pipeline for Financial Advisors

GOAL:
Build an end-to-end automated system that ingests AI news, enriches it with scoring and tagging, and produces:
- Daily digest (advisor-ready)
- Weekly investment digest
- Weekly thematic digest
- Monthly synthesis of underlying macro AI themes

CORE COMPONENTS:

1. INGESTION
- Source: Feedly API
- Pull daily AI-related articles

2. ENRICHMENT
- Model: GPT-5.3 or 5.4
- Output:
  - summary
  - relevance score
  - category tags
  - advisor relevance

3. DAILY DIGEST
- Structured into 8 fixed sections
- Bullet format
- Advisor-ready language
- Includes physical AI/robotics when relevant

4. WEEKLY DIGESTS
- Investment-focused version
- Thematic version
- Built from daily outputs

5. MONTHLY SYNTHESIS
- Identifies hidden macro AI themes
- Tracks shifts across weeks

6. DELIVERY
- Email (primary)
- Streamlit dashboard (secondary)

7. SCORING (CRITICAL)
- Must be preserved throughout pipeline
- Used to prioritize content in all outputs

RULES:
- No markdown in outputs
- Plain English, professional tone
- No hallucinated data
- Skip incomplete articles
- Maintain consistency across outputs

ENGINEERING PRINCIPLES:
- Keep system modular
- Avoid duplicating logic across files
- Centralize prompts where possible
- Use environment variables for keys (no .env in repo)