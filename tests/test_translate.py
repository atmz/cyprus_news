# tests/test_translate.py
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from translate import load_translate_prompt

class TranslateTestCase(unittest.TestCase):
    def test_translate_prompt_loads(self):
        prompt = load_translate_prompt()
        self.assertIn("Greek", prompt)
        self.assertIn("Markdown", prompt)

    def test_translate_prompt_contains_section_mappings(self):
        prompt = load_translate_prompt()
        self.assertIn("Κύριες Ειδήσεις", prompt)
        self.assertIn("Κυπριακό", prompt)

if __name__ == "__main__":
    unittest.main()
