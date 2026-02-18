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


    def test_load_articles_applies_base_url_to_relative_links(self):
        from tempfile import TemporaryDirectory
        import json
        from datetime import date

        with TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "articles.json"
            data_file.write_text(json.dumps([
                {
                    "title": "Sample",
                    "abstract": "Desc",
                    "datetime": "2026-02-17T00:00:00",
                    "url": "/novosti/example"
                }
            ]), encoding="utf-8")

            sources = [{
                "name": "EvropaKipr",
                "tag": "ЕК",
                "file": str(data_file),
                "base_url": "https://evropakipr.com"
            }]
            articles = summarize.load_articles(date(2026, 2, 17), date(2026, 2, 17), sources)

            self.assertEqual(len(articles), 1)
            self.assertEqual(articles[0]["u"], "https://evropakipr.com/novosti/example")

    def test_build_tag_examples_english(self):
        sources = [
            {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
            {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
        ]
        examples = summarize.build_tag_examples(sources)
        self.assertIn("(CM)", examples)
        self.assertIn("(IC)", examples)


if __name__ == "__main__":
    unittest.main()
