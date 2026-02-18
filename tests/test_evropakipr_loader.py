import unittest

try:
    from article_loaders.evropakipr_loader import parse_evropakipr_date
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "bs4/playwright not installed")
class TestEvropakiprDateParsing(unittest.TestCase):
    def test_full_date(self):
        self.assertEqual(
            parse_evropakipr_date("18 February 2026"),
            "2026-02-18T00:00:00",
        )

    def test_single_digit_day(self):
        self.assertEqual(
            parse_evropakipr_date("5 January 2026"),
            "2026-01-05T00:00:00",
        )

    def test_no_match(self):
        self.assertIsNone(parse_evropakipr_date("yesterday"))


if __name__ == "__main__":
    unittest.main()
