import importlib
import os
from datetime import date
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from helpers import build_summary_with_note

SAMPLE_SUMMARY = """## 📰 News Summary for Saturday, 29 August 2026

This is a summary of yesterday's broadcast.

### Top stories
- First headline
"""


class BuildSummaryWithNoteTestCase(unittest.TestCase):
    def test_note_inserted_after_title_line(self):
        result = build_summary_with_note(SAMPLE_SUMMARY, "We're back after an outage.")
        lines = result.splitlines()
        self.assertTrue(lines[0].startswith("## 📰"))
        self.assertEqual(lines[2], "*Editors note: We're back after an outage.*")
        self.assertIn("### Top stories", result)

    def test_empty_note_returns_summary_unchanged(self):
        self.assertEqual(build_summary_with_note(SAMPLE_SUMMARY, ""), SAMPLE_SUMMARY)
        self.assertEqual(build_summary_with_note(SAMPLE_SUMMARY, "   \n "), SAMPLE_SUMMARY)
        self.assertEqual(build_summary_with_note(SAMPLE_SUMMARY, None), SAMPLE_SUMMARY)

    def test_multiline_note_collapsed_to_one_paragraph(self):
        result = build_summary_with_note(SAMPLE_SUMMARY, "Line one.\nLine two.")
        self.assertIn("*Editors note: Line one. Line two.*", result)

    def test_summary_without_heading_gets_note_prepended(self):
        result = build_summary_with_note("Just text.", "Hello.")
        self.assertTrue(result.startswith("*Editors note: Hello.*\n\n"))
        self.assertIn("Just text.", result)


class HelpersTestCase(unittest.TestCase):
    def test_make_folders_creates_expected_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["SUMMARIES_ROOT"] = tmpdir
            helpers = importlib.import_module("helpers")
            helpers = importlib.reload(helpers)

            target_day = date(2024, 1, 15)
            helpers.make_folders(target_day)

            root = Path(tmpdir) / "2024-01-15"
            self.assertTrue(root.exists())
            self.assertTrue((root / "media").exists())
            self.assertTrue((root / "txt").exists())

    def test_get_root_folder_for_day_uses_env_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["SUMMARIES_ROOT"] = tmpdir
            helpers = importlib.import_module("helpers")
            helpers = importlib.reload(helpers)

            target_day = date(2024, 5, 20)
            expected = Path(tmpdir) / "2024-05-20"
            self.assertEqual(helpers.get_root_folder_for_day(target_day), expected)


if __name__ == "__main__":
    unittest.main()
