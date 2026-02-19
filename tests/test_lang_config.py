import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lang_config import load_language_config

class LangConfigTestCase(unittest.TestCase):
    def test_load_returns_all_languages(self):
        config = load_language_config()
        self.assertIn("en", config)
        self.assertIn("el", config)

    def test_english_is_transcript_source(self):
        config = load_language_config()
        self.assertEqual(config["en"]["summary_source"], "transcript")

    def test_greek_uses_native_summarization(self):
        config = load_language_config()
        self.assertEqual(config["el"]["summary_source"], "summarize_native")

    def test_each_language_has_required_keys(self):
        config = load_language_config()
        required = ["enabled", "summary_source", "summary_filename",
                     "summary_without_links_filename", "substack_url",
                     "substack_session_file", "flag_filename"]
        for lang, lc in config.items():
            for key in required:
                self.assertIn(key, lc, f"{lang} missing key {key}")

if __name__ == "__main__":
    unittest.main()
