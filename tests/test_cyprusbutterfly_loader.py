import unittest
from unittest.mock import patch
from datetime import datetime

try:
    from article_loaders.cyprusbutterfly_loader import parse_butterfly_date
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "playwright not installed")
class TestButterflyDateParsing(unittest.TestCase):
    def test_date_month(self):
        self.assertEqual(
            parse_butterfly_date("16 февраля"),
            f"{datetime.now().year}-02-16T00:00:00",
        )

    @patch("article_loaders.cyprusbutterfly_loader.datetime")
    def test_yesterday(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 2, 18, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        self.assertEqual(
            parse_butterfly_date("Вчера в 15:47"),
            "2026-02-17T15:47:00",
        )

    @patch("article_loaders.cyprusbutterfly_loader.datetime")
    def test_today(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 2, 18, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        self.assertEqual(
            parse_butterfly_date("Сегодня в 10:00"),
            "2026-02-18T10:00:00",
        )

    def test_no_match(self):
        self.assertIsNone(parse_butterfly_date("some random text"))


if __name__ == "__main__":
    unittest.main()
