import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from summarize_beta import apply_title_prefix, summarize_for_day_beta

FAKE_USAGE = {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001}

TEST_CFG = {
    "enabled": True,
    "model": "claude-sonnet-5",
    "prompts_dir": "src/prompts",
    "title_prefix": "🧪 ",
    "article_sources": [],
    "summary_filename": "summary_beta.txt",
    "summary_without_links_filename": "summary_without_links_beta.txt",
    "flag_filename": "flag_beta.txt",
    "substack_url": "unused",
    "substack_session_file": "unused",
}


def fake_complete(prompt, system_prompt=None, model=None, timeout=600, retries=1):
    # Headline call and chunk call both return valid sectioned markdown;
    # the cleanup call returns a recognizable cleaned body.
    if "SUMMARY:" in prompt:
        return "### Economy\n- cleaned bullet", FAKE_USAGE
    return "### Top stories\n- headline one\n\n### Economy\n- economy bullet", FAKE_USAGE


class ApplyTitlePrefixTestCase(unittest.TestCase):
    def test_prefix_inserted_after_h2_marker(self):
        heading = "## 📰 News Summary — Friday\n\nintro text"
        out = apply_title_prefix(heading, "🧪 ")
        self.assertTrue(out.startswith("## 🧪 📰 News Summary"))
        self.assertIn("intro text", out)

    def test_empty_prefix_is_noop(self):
        heading = "## 📰 News Summary"
        self.assertEqual(apply_title_prefix(heading, ""), heading)


class SummarizeForDayBetaTestCase(unittest.TestCase):
    def test_writes_beta_files_with_prefix_and_skips_linking_without_articles(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text(
                "Πρώτη παράγραφος.\n\nΔεύτερη παράγραφος.", encoding="utf-8"
            )
            with patch("summarize_beta.get_text_folder_for_day", return_value=txt), \
                 patch("summarize_beta.complete", side_effect=fake_complete), \
                 patch("summarize_beta.load_ongoing_topics",
                       return_value={"topics": [], "config": {}}):
                summarize_for_day_beta(day, cfg=TEST_CFG)

            without_links = (txt / "summary_without_links_beta.txt").read_text(encoding="utf-8")
            final = (txt / "summary_beta.txt").read_text(encoding="utf-8")
            self.assertIn("🧪", without_links.splitlines()[0])
            self.assertIn("🧪", final.splitlines()[0])
            self.assertIn("Top stories", final)
            self.assertIn("cleaned bullet", final)
            # beta must not touch prod filenames
            self.assertFalse((txt / "summary.txt").exists())
            self.assertFalse((txt / "summary_without_links.txt").exists())

    def test_existing_beta_summary_is_reused_not_regenerated(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_without_links_beta.txt").write_text(
                "## 🧪 heading\n\n### Top stories\n- old headline\n\n### Economy\n- old bullet",
                encoding="utf-8",
            )
            calls = []

            def counting_complete(prompt, **kwargs):
                calls.append(prompt)
                return "### Economy\n- cleaned bullet", FAKE_USAGE

            with patch("summarize_beta.get_text_folder_for_day", return_value=txt), \
                 patch("summarize_beta.complete", side_effect=counting_complete), \
                 patch("summarize_beta.load_ongoing_topics",
                       return_value={"topics": [], "config": {}}):
                summarize_for_day_beta(day, cfg=TEST_CFG)

            # Only the cleanup call should have hit the LLM (no chunk summarization)
            self.assertEqual(len(calls), 1)
            self.assertIn("SUMMARY:", calls[0])


if __name__ == "__main__":
    unittest.main()
