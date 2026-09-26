import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

import main
from beta_config import load_beta_config


class ProdEnglishConfigTestCase(unittest.TestCase):
    def test_promoted_config_loads_with_required_keys(self):
        cfg = load_beta_config(ROOT / "config" / "prod_english.json")
        for key in ("model", "prompts_dir", "title_prefix", "article_sources",
                    "summary_filename", "summary_without_links_filename"):
            self.assertIn(key, cfg)

    def test_promoted_config_writes_prod_filenames_with_no_prefix(self):
        cfg = load_beta_config(ROOT / "config" / "prod_english.json")
        self.assertEqual(cfg["summary_filename"], "summary.txt")
        self.assertEqual(cfg["summary_without_links_filename"], "summary_without_links.txt")
        self.assertEqual(cfg["title_prefix"], "")


class SummarizeEnglishForDayTestCase(unittest.TestCase):
    def test_claude_pipeline_used_when_it_succeeds(self):
        with patch("main.summarize_for_day_beta") as mock_claude, \
             patch("main.summarize_for_day") as mock_openai:
            main.summarize_english_for_day(date(2026, 9, 26))
            mock_claude.assert_called_once()
            self.assertEqual(mock_claude.call_args.kwargs["cfg"]["summary_filename"], "summary.txt")
            mock_openai.assert_not_called()

    def test_falls_back_to_openai_when_claude_fails(self):
        with patch("main.summarize_for_day_beta", side_effect=RuntimeError("claude exited 1")), \
             patch("main.summarize_for_day") as mock_openai:
            main.summarize_english_for_day(date(2026, 9, 26))
            mock_openai.assert_called_once_with(date(2026, 9, 26))

    def test_fallback_failure_propagates(self):
        # If both engines fail, the error must reach main.py's normal error
        # handling — a silent double-failure would look like success.
        with patch("main.summarize_for_day_beta", side_effect=RuntimeError("claude down")), \
             patch("main.summarize_for_day", side_effect=RuntimeError("openai down")):
            with self.assertRaises(RuntimeError):
                main.summarize_english_for_day(date(2026, 9, 26))


if __name__ == "__main__":
    unittest.main()
