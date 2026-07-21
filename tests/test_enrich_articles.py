import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import enrich_articles


class EnrichArticlesRetryTests(unittest.TestCase):
    def test_create_enrichment_response_retries_rate_limits_until_success(self):
        attempts = {"count": 0}

        class FakeRateLimitError(Exception):
            status_code = 429

        class FakeClient:
            def __init__(self):
                self.chat = SimpleNamespace(completions=self)

            def create(self, **kwargs):
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise FakeRateLimitError("429 Too Many Requests")
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"summary":"ok","themes":["infra"],"companies":["Example"],"advisor_relevance":"matters","ai_score":8}'
                            )
                        )
                    ]
                )

        with patch.object(enrich_articles, "MAX_API_ATTEMPTS", 5), patch.object(
            enrich_articles,
            "time",
        ) as mock_time:
            parsed = enrich_articles._create_enrichment_response(
                FakeClient(),
                "system",
                "user",
            )

        self.assertEqual(attempts["count"], 3)
        self.assertEqual(parsed["summary"], "ok")
        self.assertEqual(mock_time.sleep.call_args_list[0].args[0], 2.0)
        self.assertEqual(mock_time.sleep.call_args_list[1].args[0], 4.0)


if __name__ == "__main__":
    unittest.main()