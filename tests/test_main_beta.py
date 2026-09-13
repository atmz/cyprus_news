import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from main_beta import resolve_day, run_beta

CY_TZ = ZoneInfo("Europe/Nicosia")

BASE_CFG = {
    "enabled": True,
    "model": "claude-sonnet-5",
    "prompts_dir": "src/prompts",
    "title_prefix": "🧪 ",
    "article_sources": [],
    "summary_filename": "summary_beta.txt",
    "summary_without_links_filename": "summary_without_links_beta.txt",
    "flag_filename": "flag_beta.txt",
    "substack_url": "https://example.substack.com/publish/post",
    "substack_session_file": "substack_session.json",
}


class ResolveDayTestCase(unittest.TestCase):
    def test_explicit_date(self):
        self.assertEqual(resolve_day("2026-09-01"), date(2026, 9, 1))

    def test_before_start_hour_returns_none(self):
        now = datetime(2026, 9, 12, 5, 30, tzinfo=CY_TZ)
        self.assertIsNone(resolve_day(None, now=now))

    def test_after_start_hour_returns_yesterday(self):
        now = datetime(2026, 9, 12, 7, 0, tzinfo=CY_TZ)
        self.assertEqual(resolve_day(None, now=now), date(2026, 9, 11))


class RunBetaTestCase(unittest.TestCase):
    def test_disabled_config_does_nothing(self):
        with patch("main_beta.summarize_for_day_beta") as mock_summarize, \
             patch("main_beta.post_to_substack") as mock_post:
            run_beta(date(2026, 9, 1), cfg={**BASE_CFG, "enabled": False})
            mock_summarize.assert_not_called()
            mock_post.assert_not_called()

    def test_missing_transcript_exits_without_summarizing(self):
        with TemporaryDirectory() as tmp:
            with patch("main_beta.get_text_folder_for_day", return_value=Path(tmp)), \
                 patch("main_beta.summarize_for_day_beta") as mock_summarize, \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(date(2026, 9, 1), cfg=BASE_CFG)
                mock_summarize.assert_not_called()
                mock_post.assert_not_called()

    def test_summarizes_posts_and_touches_flag_on_success(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")

            def fake_summarize(d, cfg=None):
                (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
                (txt / "cover.png").touch()

            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.summarize_for_day_beta", side_effect=fake_summarize), \
                 patch("main_beta.post_to_substack", return_value=True) as mock_post:
                run_beta(day, cfg=BASE_CFG)
                mock_post.assert_called_once()
                kwargs = mock_post.call_args.kwargs
                self.assertEqual(kwargs["substack_url"], BASE_CFG["substack_url"])
                self.assertEqual(kwargs["lang"], "en")
                self.assertTrue((txt / "flag_beta.txt").exists())

    def test_failed_post_leaves_no_flag(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            (txt / "cover.png").touch()
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack", return_value=False):
                run_beta(day, cfg=BASE_CFG)
                self.assertFalse((txt / "flag_beta.txt").exists())

    def test_missing_cover_skips_posting_and_leaves_no_flag(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            # cover.png deliberately absent — prod hasn't generated it yet.
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, cfg=BASE_CFG)
                mock_post.assert_not_called()
                self.assertFalse((txt / "flag_beta.txt").exists())

    def test_placeholder_substack_url_skips_posting(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            (txt / "cover.png").touch()
            cfg = {**BASE_CFG, "substack_url": "REPLACE_WITH_BETA_PUBLISH_URL"}
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, cfg=cfg)
                mock_post.assert_not_called()

    def test_no_post_skips_posting(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, no_post=True, cfg=BASE_CFG)
                mock_post.assert_not_called()

    def test_existing_flag_skips_posting(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            (txt / "flag_beta.txt").touch()
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, cfg=BASE_CFG)
                mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
