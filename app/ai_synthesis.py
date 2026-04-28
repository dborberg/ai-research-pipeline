import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Debug output path (used by dashboard to show last synthesis)
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
LOG_FILE = os.path.join(LOG_DIR, "ai_synthesis_response.txt")

os.makedirs(LOG_DIR, exist_ok=True)


def generate_ai_insights(articles):
    """
    Generate high-level AI insights from high-scoring articles.
    
    Args:
        articles: Pandas DataFrame with columns: title, summary, themes, companies, 
                  advisor_relevance, ai_score
    
    Returns:
        dict with keys: themes, top_stories, soundbites, client_questions
        or empty dict if synthesis fails
    """
    
    # Filter articles with ai_score >= 7
    high_score_articles = articles[
        (articles["ai_score"].notna()) & (articles["ai_score"] >= 7)
    ].copy()
    
    if len(high_score_articles) == 0:
        return {
            "themes": [],
            "top_stories": [],
            "soundbites": [],
            "client_questions": []
        }
    
    # Sort by ai_score descending to prioritize higher scores
    high_score_articles = high_score_articles.sort_values("ai_score", ascending=False)
    
    # Build dataset string
    dataset_lines = []
    for _, row in high_score_articles.iterrows():
        title = row.get("title", "")
        summary = row.get("summary", "")
        themes = row.get("themes", "")
        companies = row.get("companies", "")
        advisor_relevance = row.get("advisor_relevance", "")
        score = row.get("ai_score", "")
        
        dataset_lines.append(
            f"ARTICLE: {title}\n"
            f"SCORE: {score}\n"
            f"SUMMARY: {summary}\n"
            f"THEMES: {themes}\n"
            f"COMPANIES: {companies}\n"
            f"ADVISOR_RELEVANCE: {advisor_relevance}\n"
        )
    
    dataset_str = "\n---\n".join(dataset_lines)
    
    system_message = "You are a senior AI research analyst writing for mutual fund wholesalers. Be concise, practical, and advisor-relevant."
    
    user_message = f"""Analyze these high-impact AI articles and produce structured insights.

{dataset_str}

Return ONLY valid JSON:

{{
  "themes": ["...", "...", "..."],
  "top_stories": [
    {{"title": "...", "summary": "..."}},
    {{"title": "...", "summary": "..."}}
  ],
  "soundbites": ["...", "..."],
  "client_questions": ["...", "..."]
}}

Prioritize higher AI Score articles. Avoid repeating headers. Keep tone consistent. Focus on advisor relevance."""

    try:
        response = client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
        )
        
        response_text = response.choices[0].message.content.strip()

        # Save raw response for debugging
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(response_text)

        # Try to parse JSON
        try:
            result = json.loads(response_text)
        except Exception:
            # Try extracting JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    result = json.loads(response_text[start : end + 1])
                except Exception:
                    print("❌ Failed to parse AI synthesis response")
                    return {
                        "themes": [],
                        "top_stories": [],
                        "soundbites": [],
                        "client_questions": []
                    }
            else:
                print("❌ No JSON found in AI synthesis response")
                return {
                    "themes": [],
                    "top_stories": [],
                    "soundbites": [],
                    "client_questions": []
                }
        
        # Validate structure
        for key in ["themes", "top_stories", "soundbites", "client_questions"]:
            if key not in result or not isinstance(result.get(key), list):
                result[key] = []
        
        # If the AI returned empty results, fall back to a simple heuristic
        if not any(result.values()):
            return fallback_insights(high_score_articles)

        return result
    
    except Exception as e:
        # Save error for debugging
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"ERROR: {e}\n")
        print(f"❌ AI synthesis error: {e}")
        return fallback_insights(high_score_articles)


def fallback_insights(high_score_articles):
    """Fallback insight generation when AI synthesis fails or returns empty."""
    # Top stories: top 3 by score
    top_stories = []
    for _, row in high_score_articles.head(3).iterrows():
        top_stories.append({
            "title": row.get("title", ""),
            "summary": row.get("summary", ""),
        })

    # Themes: most common themes from top rows
    all_themes = []
    for t in high_score_articles["themes"].dropna():
        try:
            parsed = json.loads(t) if isinstance(t, str) else t
            if isinstance(parsed, list):
                all_themes.extend(parsed)
        except Exception:
            pass

    themes = []
    if all_themes:
        from collections import Counter
        themes = [t for t, _ in Counter(all_themes).most_common(5)]

    soundbites = [s for s in high_score_articles["summary"].dropna().head(3).tolist()]
    client_questions = [
        "What are the key risks and opportunities for our portfolios from these AI trends?",
        "Which sectors and companies are best positioned to benefit from this wave of AI infrastructure spending?",
    ]

    return {
        "themes": themes,
        "top_stories": top_stories,
        "soundbites": soundbites,
        "client_questions": client_questions,
    }
