import unittest

from scripts.generate_sector_report import build_cross_sector_generation_user_prompt, build_generation_user_prompt
from scripts.render_prompt import (
    CROSS_SECTOR_SYSTEM_PROMPT_PATH,
    FRONTIER_SYSTEM_PROMPT_PATH,
    CORE_PROMPT_PATH,
    build_cross_sector_prompt_components,
    build_prompt_components,
)


class CrossSectorThematicPromptTests(unittest.TestCase):
    def test_sector_investable_path_still_uses_existing_core_prompt(self):
        components = build_prompt_components(
            sector="healthcare",
            audience="financial advisors and investment professionals",
            time_horizon="1-3 years and 3-7 years",
            style_notes="",
            special_instructions="",
            report_mode="investment_implications",
            industry_focus="balanced",
        )

        self.assertEqual(components["system_prompt"], CORE_PROMPT_PATH.read_text(encoding="utf-8").strip())
        self.assertIn("## Sector Adapter", components["prompt_package"])
        self.assertIn("Realistic Investable Impact", components["prompt_package"])
        self.assertNotIn("All Sectors / Cross-Sector Theme", components["prompt_package"])

    def test_sector_frontier_path_still_uses_existing_frontier_prompt(self):
        components = build_prompt_components(
            sector="healthcare",
            audience="financial advisors and investment professionals",
            time_horizon="1-3 years and 3-7 years",
            style_notes="",
            special_instructions="",
            report_mode="frontier_possibilities",
            industry_focus="balanced",
        )

        self.assertEqual(components["system_prompt"], FRONTIER_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip())
        self.assertIn("This is the Frontier Possibilities version", components["user_prompt"])
        self.assertIn("## Sector Adapter", components["prompt_package"])

    def test_cross_sector_path_does_not_require_gics_values(self):
        components = build_cross_sector_prompt_components(
            broad_theme="Space Economy",
            optional_subtheme="Low-earth-orbit satellite networks",
            ai_lens="Gen AI as Important Accelerator",
            report_mode="Combined",
            time_horizon="Full stack",
            audience="Financial advisors",
            small_cap_lens="Include small-cap relevance where appropriate.",
        )

        self.assertEqual(components["system_prompt"], CROSS_SECTOR_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip())
        self.assertIn("## Report Scope\n\nAll Sectors / Cross-Sector Theme", components["prompt_package"])
        self.assertNotIn("## Selected Sector", components["prompt_package"])
        self.assertNotIn("## Sector Adapter", components["prompt_package"])
        self.assertIn("Do not force the theme into a single GICS sector", components["user_prompt"])

    def test_broad_theme_is_required_for_cross_sector_path(self):
        with self.assertRaisesRegex(ValueError, "Broad Theme is required"):
            build_cross_sector_prompt_components(
                broad_theme=" ",
                optional_subtheme="",
                ai_lens="Do Not Force Gen AI",
                report_mode="Realistic Investable Impact",
                time_horizon="1-3 years",
                audience="Clients",
                small_cap_lens="Not requested.",
            )

    def test_cross_sector_variables_are_passed_into_prompt(self):
        components = build_cross_sector_prompt_components(
            broad_theme="Water Infrastructure",
            optional_subtheme="Municipal leakage detection",
            ai_lens="Do Not Force Gen AI",
            report_mode="Realistic Investable Impact",
            time_horizon="3-7 years",
            audience="Clients",
            small_cap_lens="Include small-cap relevance where appropriate.",
            source_material="Theme adapter notes",
        )

        user_prompt = components["user_prompt"]
        for expected in [
            "Broad Theme: Water Infrastructure",
            "Optional Subtheme: Municipal leakage detection",
            "AI Lens: Do Not Force Gen AI",
            "Report Mode: Realistic Investable Impact",
            "Time Horizon: 3-7 years",
            "Audience: Clients",
            "Small-Cap Lens: Include small-cap relevance where appropriate.",
            "Theme adapter notes",
        ]:
            self.assertIn(expected, user_prompt)

    def test_ai_lens_instructions_are_available_for_each_cross_sector_mode(self):
        system_prompt = CROSS_SECTOR_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn('If the AI lens is “Gen AI as Primary Driver,” make Generative AI the central force', system_prompt)
        self.assertIn('If the AI lens is “Gen AI as Important Accelerator,” explain how Generative AI', system_prompt)
        self.assertIn('If the AI lens is “Gen AI as Supporting Factor,” mention AI only where it naturally improves', system_prompt)
        self.assertIn('If the AI lens is “Do Not Force Gen AI,” do not insert AI unless it is clearly relevant', system_prompt)

    def test_cross_sector_execution_prompt_is_not_sector_specific(self):
        components = build_cross_sector_prompt_components(
            broad_theme="Robotics and Autonomy",
            optional_subtheme="Industrial software and physical infrastructure",
            ai_lens="Gen AI as Important Accelerator",
            report_mode="Frontier Possibilities",
            time_horizon="Full stack",
            audience="Internal CPM",
            small_cap_lens="Not requested.",
        )
        execution_prompt = build_cross_sector_generation_user_prompt(
            theme_context=components["theme_context"],
            user_prompt=components["user_prompt"],
            output_format="markdown",
        )

        self.assertIn("cross-sector thematic report request", execution_prompt)
        self.assertIn("Do not require or infer a GICS sector", execution_prompt)
        self.assertIn("Robotics and Autonomy", execution_prompt)
        self.assertIn("AI Lens: Gen AI as Important Accelerator", execution_prompt)

    def test_existing_sector_execution_prompt_remains_sector_specific(self):
        execution_prompt = build_generation_user_prompt(
            sector_adapter="Healthcare adapter",
            user_prompt="Healthcare user prompt",
            output_format="markdown",
        )

        self.assertIn("sector-specific Generative AI report request", execution_prompt)
        self.assertIn("Sector Adapter follows", execution_prompt)

    def test_cross_sector_prompt_file_is_separate_from_frontier_prompt(self):
        cross_prompt = CROSS_SECTOR_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        frontier_prompt = FRONTIER_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

        self.assertNotEqual(CROSS_SECTOR_SYSTEM_PROMPT_PATH, FRONTIER_SYSTEM_PROMPT_PATH)
        self.assertIn("Cross-Sector Thematic Report", cross_prompt)
        self.assertIn("GICS sector", frontier_prompt)
        self.assertNotEqual(cross_prompt, frontier_prompt)


if __name__ == "__main__":
    unittest.main()
