import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from summarize_beta import (
    _restore_section_headers,
    _strip_llm_preamble,
    apply_title_prefix,
    generate_chunked_summary_beta,
    strip_hallucinated_links,
    summarize_for_day_beta,
)

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


class StripLlmPreambleTestCase(unittest.TestCase):
    def test_drops_leading_commentary_line(self):
        text = (
            "Looking at the articles provided, I found two clear matches.\n\n"
            "### Economy\n- cleaned bullet"
        )
        out = _strip_llm_preamble(text)
        self.assertEqual(out, "### Economy\n- cleaned bullet")

    def test_noop_when_already_starts_with_header(self):
        text = "### Economy\n- cleaned bullet"
        self.assertEqual(_strip_llm_preamble(text), text)

    def test_noop_when_no_headers_at_all(self):
        text = "Just some plain text with no section headers."
        self.assertEqual(_strip_llm_preamble(text), text)


class RestoreSectionHeadersTestCase(unittest.TestCase):
    def test_converts_downgraded_headers(self):
        text = "## Economy\n- bullet one\n\n## Society\n- bullet two"
        out = _restore_section_headers(text)
        self.assertEqual(out, "### Economy\n- bullet one\n\n### Society\n- bullet two")

    def test_leaves_correct_headers_untouched(self):
        text = "### Economy\n- bullet one"
        self.assertEqual(_restore_section_headers(text), text)


class GenerateChunkedSummaryBetaTestCase(unittest.TestCase):
    def test_headline_without_header_gets_top_stories_prefix(self):
        def headerless_complete(prompt, system_prompt=None, model=None, timeout=600, retries=1):
            if system_prompt and "headline" in (system_prompt or "").lower():
                return "- headline one\n- headline two", FAKE_USAGE
            return "### Economy\n- economy bullet", FAKE_USAGE

        with patch("summarize_beta.complete", side_effect=headerless_complete):
            combined, usage = generate_chunked_summary_beta(
                "Some short transcript text.",
                "user prompt",
                "first chunk system prompt",
                "followup chunk system prompt",
                "headline system prompt",
                model="claude-sonnet-5",
                sleep_time=0,
            )

        self.assertIn("### Top stories", combined)


class StripHallucinatedLinksTestCase(unittest.TestCase):
    def test_removes_unsupplied_url_keeps_supplied_one(self):
        articles = [{"t": "Real story", "a": "abstract", "u": "https://cyprus-mail.com/real", "tag": "CM"}]
        text = (
            "- Some story happened. [(CM)](https://cyprus-mail.com/real)\n"
            "- Another story. [(Φ)](https://philenews.com/hallucinated-greek-link)"
        )
        cleaned = strip_hallucinated_links(text, articles)
        self.assertIn("https://cyprus-mail.com/real", cleaned)
        self.assertNotIn("philenews.com/hallucinated-greek-link", cleaned)
        self.assertNotIn("[(Φ)]", cleaned)

    def test_noop_when_all_links_are_supplied(self):
        articles = [
            {"t": "A", "a": "a", "u": "https://cyprus-mail.com/a", "tag": "CM"},
            {"t": "B", "a": "b", "u": "https://en.philenews.com/b", "tag": "IC"},
        ]
        text = "- Story. [(CM)](https://cyprus-mail.com/a) [(IC)](https://en.philenews.com/b)"
        self.assertEqual(strip_hallucinated_links(text, articles), text)


if __name__ == "__main__":
    unittest.main()
