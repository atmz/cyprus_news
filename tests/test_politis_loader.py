import unittest

try:
    from article_loaders.politis_loader import parse_politis_date
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "bs4/playwright not installed")
class TestPolitisDateParsing(unittest.TestCase):
    def test_full_datetime(self):
        self.assertEqual(
            parse_politis_date("17.02.2026 13:31"),
            "2026-02-17T13:31:00",
        )

    def test_single_digit_hour(self):
        self.assertEqual(
            parse_politis_date("05.01.2026 9:05"),
            "2026-01-05T09:05:00",
        )

    def test_no_match(self):
        self.assertIsNone(parse_politis_date("yesterday"))

    def test_whitespace(self):
        self.assertEqual(
            parse_politis_date("  17.02.2026 13:31  "),
            "2026-02-17T13:31:00",
        )


if __name__ == "__main__":
    unittest.main()
