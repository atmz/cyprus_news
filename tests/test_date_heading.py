# tests/test_date_heading.py
import sys
from pathlib import Path
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from date_heading import generate_date_heading

class DateHeadingTestCase(unittest.TestCase):
    def test_english_heading(self):
        heading = generate_date_heading(date(2026, 2, 17), "en")
        self.assertIn("News Summary", heading)
        self.assertIn("Tuesday", heading)
        self.assertIn("17 February 2026", heading)

    def test_greek_heading(self):
        heading = generate_date_heading(date(2026, 2, 17), "el")
        self.assertIn("Περίληψη Ειδήσεων", heading)
        self.assertIn("Τρίτη", heading)
        self.assertIn("Φεβρουαρίου", heading)

    def test_english_heading_contains_rik_link(self):
        heading = generate_date_heading(date(2026, 2, 17), "en")
        self.assertIn("tv.rik.cy", heading)

    def test_greek_heading_contains_rik_link(self):
        heading = generate_date_heading(date(2026, 2, 17), "el")
        self.assertIn("tv.rik.cy", heading)

if __name__ == "__main__":
    unittest.main()
