import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

try:
    from article_loaders.philenews_loader import parse_greek_datetime
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "bs4/playwright not installed")
class PhilenewsLoaderTestCase(unittest.TestCase):
    def test_parse_standard_date(self):
        result = parse_greek_datetime("17 Φεβρουαρίου 2026, 9:33")
        self.assertEqual(result, "2026-02-17T09:33:00")

    def test_parse_date_with_two_digit_hour(self):
        result = parse_greek_datetime("5 Μαρτίου 2026, 14:05")
        self.assertEqual(result, "2026-03-05T14:05:00")

    def test_parse_relative_time_returns_none(self):
        result = parse_greek_datetime("Πριν 48 λεπτά")
        self.assertIsNone(result)

    def test_parse_december(self):
        result = parse_greek_datetime("25 Δεκεμβρίου 2025, 20:00")
        self.assertEqual(result, "2025-12-25T20:00:00")


if __name__ == "__main__":
    unittest.main()
