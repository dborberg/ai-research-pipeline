Cluster the following weekly AI research articles into 5 to 10 distinct themes.

Return JSON with this exact structure:
{
  "clusters": [
    {
      "theme_name": "short theme name",
      "article_ids": [1, 2, 3],
      "representative_summary": "2-3 sentence synthesis of the cluster",
      "key_companies": ["Company A", "Company B"],
      "investment_relevance": "1-2 sentence explanation of why this matters for markets, sectors, or advisors"
    }
  ]
}

Rules:
- Each article may appear in at most one cluster.
- Favor high-signal articles when assigning the core of a cluster.
- Use medium-signal articles only if they materially strengthen the same theme.
- Do not create vague umbrella themes.
- Do not create clusters with fewer than 2 articles unless the signal is extremely strong.
- At least 60% of the articles used to define each cluster must be HIGH SIGNAL when available.
- Theme names should be concise, specific, and useful for business readers.

ARTICLES:
{{article_lines}}