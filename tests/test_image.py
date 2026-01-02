import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

import image


class ImageTestCase(unittest.TestCase):
    def test_extract_top_stories_from_markdown_bullets(self):
        markdown = """# Daily Brief\n\n- Story one\n- Story two\n\nMore text here."""
        extracted = image.extract_top_stories_from_md(markdown)
        self.assertEqual(extracted, "- Story one\n- Story two")

    def test_extract_top_stories_from_markdown_fallback(self):
        markdown = """# Daily Brief\n\nTop stories paragraph.\n\nMore text."""
        extracted = image.extract_top_stories_from_md(markdown)
        self.assertEqual(extracted, "Top stories paragraph.")

    def test_build_image_prompt_includes_lead_subject_and_faces_clause(self):
        prompt = image.build_image_prompt(
            "Monday, 01 January 2024",
            "- Budget talks\n- Tourism updates",
            lead_subject="Budget talks",
            allow_faces=False,
        )
        self.assertIn("Lead subject: Budget talks.", prompt)
        self.assertIn("Avoid faces", prompt)


if __name__ == "__main__":
    unittest.main()
