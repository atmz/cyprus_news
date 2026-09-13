import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

import summarize


class SummarizeTestCase(unittest.TestCase):
    def test_combine_summaries_merges_and_orders_sections(self):
        chunk_one = """### Top stories\n- Item A\n\n### Culture\n- Item C"""
        chunk_two = """### Top stories\n- Item B\n\n### Education\n- Item D"""

        combined = summarize.combine_summaries([chunk_one, chunk_two])

        top_index = combined.find("### Top stories")
        edu_index = combined.find("### Education")
        culture_index = combined.find("### Culture")

        self.assertNotEqual(top_index, -1)
        self.assertNotEqual(edu_index, -1)
        self.assertNotEqual(culture_index, -1)
        self.assertTrue(top_index < edu_index < culture_index)
        self.assertIn("- Item A", combined)
        self.assertIn("- Item B", combined)

    def test_limit_headlines_caps_bullet_count(self):
        text = """Header\n- One\n- Two\n- Three"""
        limited = summarize.limit_headlines(text, max_count=2)
        self.assertIn("- One", limited)
        self.assertIn("- Two", limited)
        self.assertNotIn("- Three", limited)

    def test_build_tag_examples(self):
        sources = [
            {"name": "Philenews", "tag": "ΦΝ", "file": "data/philenews_kipros_articles.json"},
            {"name": "Philenews", "tag": "ΦΝ", "file": "data/philenews_oikonomia_articles.json"},
        ]
        examples = summarize.build_tag_examples(sources)
        self.assertIn("(ΦΝ)", examples)
        self.assertIn("Philenews", examples)
        # Duplicate tag should only appear once
        self.assertEqual(examples.count("(ΦΝ)"), 1)

    def test_build_tag_examples_english(self):
        sources = [
            {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
            {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
        ]
        examples = summarize.build_tag_examples(sources)
        self.assertIn("(CM)", examples)
        self.assertIn("(IC)", examples)

    def test_strip_hallucinated_links_removes_unsupplied_url(self):
        articles = [{"t": "Real story", "a": "abstract", "u": "https://cyprus-mail.com/real", "tag": "CM"}]
        text = (
            "- Some story happened. [(CM)](https://cyprus-mail.com/real)\n"
            "- Another story. [(Φ)](https://philenews.com/hallucinated-greek-link)"
        )
        cleaned = summarize.strip_hallucinated_links(text, articles)
        self.assertIn("https://cyprus-mail.com/real", cleaned)
        self.assertNotIn("philenews.com/hallucinated-greek-link", cleaned)
        self.assertNotIn("[(Φ)]", cleaned)

    def test_strip_hallucinated_links_keeps_all_supplied_urls(self):
        articles = [
            {"t": "A", "a": "a", "u": "https://cyprus-mail.com/a", "tag": "CM"},
            {"t": "B", "a": "b", "u": "https://en.philenews.com/b", "tag": "IC"},
        ]
        text = "- Story. [(CM)](https://cyprus-mail.com/a) [(IC)](https://en.philenews.com/b)"
        cleaned = summarize.strip_hallucinated_links(text, articles)
        self.assertEqual(text, cleaned)

    def test_strip_hallucinated_links_no_articles_strips_all_links(self):
        text = "- Story. [(CM)](https://cyprus-mail.com/a)"
        cleaned = summarize.strip_hallucinated_links(text, [])
        self.assertNotIn("cyprus-mail.com", cleaned)


if __name__ == "__main__":
    unittest.main()
