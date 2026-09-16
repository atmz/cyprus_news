import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from ongoing_topics import drop_empty_sections


class DropEmptySectionsTestCase(unittest.TestCase):
    def test_removes_headers_with_no_bullets(self):
        text = (
            "### Pension Reform\n"
            "- A real bullet.\n"
            "\n"
            "### West Nile Virus Outbreak\n"
            "\n"
            "### Russia–Ukraine War\n"
            "\n"
            "### Economy\n"
            "- Another real bullet.\n"
        )
        cleaned = drop_empty_sections(text)
        self.assertIn("### Pension Reform", cleaned)
        self.assertIn("### Economy", cleaned)
        self.assertNotIn("West Nile", cleaned)
        self.assertNotIn("Russia–Ukraine", cleaned)

    def test_removes_trailing_empty_section(self):
        text = "### Economy\n- Bullet.\n\n### Foot-and-Mouth Disease Outbreak\n"
        cleaned = drop_empty_sections(text)
        self.assertNotIn("Foot-and-Mouth", cleaned)
        self.assertIn("- Bullet.", cleaned)

    def test_noop_when_all_sections_have_bullets(self):
        text = "### A\n- one\n- two\n\n### B\n- three\n"
        self.assertEqual(drop_empty_sections(text).strip(), text.strip())

    def test_preserves_heading_and_intro_before_first_section(self):
        text = "## 📰 Title\n\nIntro paragraph.\n\n### A\n- one\n\n### Empty\n"
        cleaned = drop_empty_sections(text)
        self.assertIn("## 📰 Title", cleaned)
        self.assertIn("Intro paragraph.", cleaned)
        self.assertIn("### A", cleaned)
        self.assertNotIn("### Empty", cleaned)


if __name__ == "__main__":
    unittest.main()
