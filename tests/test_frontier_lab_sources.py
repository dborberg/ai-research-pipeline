import unittest

from app.fetch_rss_articles import FEED_BUCKETS, _compute_priority_score


class FrontierLabSourceTests(unittest.TestCase):
    def test_frontier_lab_sources_cover_official_announcements(self):
        sources = "\n".join(FEED_BUCKETS["frontier_labs"])

        for domain in [
            "openai.com", "anthropic.com", "deepmind.google", "ai.meta.com", "x.ai", "mistral.ai",
        ]:
            self.assertIn(domain, sources)

    def test_named_frontier_model_launch_has_high_priority(self):
        launch_score = _compute_priority_score(
            "OpenAI launches ChatGPT Astral model",
            "The company announced a new frontier model release.",
        )
        ordinary_score = _compute_priority_score(
            "OpenAI executive discusses industry trends",
            "The company shared general AI commentary.",
        )

        self.assertGreaterEqual(launch_score, ordinary_score + 10)


if __name__ == "__main__":
    unittest.main()