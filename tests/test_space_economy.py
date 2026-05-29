import unittest

from app.space_economy import (
    calculate_space_economy_theme_active,
    classify_space_economy_article,
    format_space_metadata_lines,
)


def _quality(article):
    return int(article.get("ai_score") or 0) >= 6


class SpaceEconomyThemeTests(unittest.TestCase):
    def test_no_space_stories_inactive(self):
        articles = [
            {
                "title": "Microsoft expands enterprise AI agents",
                "summary": "The deployment focuses on governed workflows and cloud AI adoption.",
                "ai_score": 8,
            }
        ]
        self.assertFalse(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_generic_rocket_launch_inactive(self):
        articles = [
            {
                "title": "Rocket launch sends new payload to orbit",
                "summary": "The mission successfully deployed a commercial payload with no AI read-through.",
                "ai_score": 8,
            }
        ]
        self.assertFalse(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_generic_satellite_deployment_inactive(self):
        articles = [
            {
                "title": "Satellite deployment expands orbital constellation",
                "summary": "The update describes additional satellites and generic broadband coverage.",
                "ai_score": 8,
            }
        ]
        self.assertFalse(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_generic_nasa_broadband_or_funding_inactive(self):
        articles = [
            {
                "title": "NASA contract and space funding support a broadband constellation update",
                "summary": "The story describes program funding without AI, data analytics, defense, autonomy, cybersecurity, communications resilience, or infrastructure read-through.",
                "ai_score": 8,
            }
        ]
        self.assertFalse(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_satellite_geospatial_ai_active(self):
        articles = [
            {
                "title": "Satellite geospatial intelligence platform adds AI analytics for insurers",
                "summary": "The earth observation company uses AI-enabled geospatial intelligence to process satellite data for commercial risk analytics.",
                "ai_score": 8,
            }
        ]
        self.assertTrue(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_defense_autonomy_cyber_cloud_or_resilience_active(self):
        examples = [
            "AI-enabled space-domain awareness improves defense decision loops.",
            "Autonomous satellite software adds onboard AI for orbital operations.",
            "Satellite cybersecurity platform protects space infrastructure.",
            "Cloud-based geospatial analytics processes satellite data for emergency response.",
            "AI-enabled communications resilience hardens satellite links for defense users.",
        ]
        for example in examples:
            with self.subTest(example=example):
                articles = [{"title": example, "summary": example, "ai_score": 8}]
                self.assertTrue(calculate_space_economy_theme_active(articles, quality_filter=_quality))

    def test_active_does_not_force_metadata_for_unqualified_story(self):
        generic = {
            "title": "Rocket launch sends tourism vehicle to orbit",
            "summary": "The article is a generic space tourism story.",
            "ai_score": 8,
        }
        qualified = {
            "title": "Satellite data analytics company deploys AI geospatial platform",
            "summary": "The platform uses cloud analytics and AI on earth observation data.",
            "ai_score": 8,
        }
        self.assertTrue(calculate_space_economy_theme_active([generic, qualified], quality_filter=_quality))
        self.assertEqual(format_space_metadata_lines(generic), [])
        self.assertNotEqual(format_space_metadata_lines(qualified), [])

    def test_optional_metadata_fields_are_backward_compatible(self):
        metadata = classify_space_economy_article({"title": "AI geospatial intelligence from satellites", "summary": ""})
        self.assertEqual(
            set(metadata),
            {
                "is_space_economy_related",
                "space_relevance",
                "space_ai_connection",
                "space_time_horizon",
                "space_investment_layer",
            },
        )


if __name__ == "__main__":
    unittest.main()
