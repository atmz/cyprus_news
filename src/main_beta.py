"""Beta pipeline orchestrator — runs alongside main.py, never touches prod state.

Waits for prod's transcript, summarizes via claude -p (summarize_beta),
posts to the beta Substack. Idempotent via summary_beta.txt / flag_beta.txt.
See docs/superpowers/specs/2026-09-12-beta-pipeline-design.md.
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from beta_config import load_beta_config
from helpers import get_text_folder_for_day
from post_to_substack import post_to_substack
from summarize_beta import summarize_for_day_beta
from timing import timing_step

CY_TZ = ZoneInfo("Europe/Nicosia")
START_HOUR = 6  # match prod: don't process until 6am Cyprus time


def resolve_day(date_arg, now=None):
    if date_arg:
        return datetime.strptime(date_arg, "%Y-%m-%d").date()
    now_cy = now or datetime.now(CY_TZ)
    if now_cy.hour < START_HOUR:
        print(f"⏳ It's {now_cy.strftime('%H:%M')} in Cyprus — too early, waiting until {START_HOUR}:00.")
        return None
    return now_cy.date() - timedelta(days=1)


def run_beta(day, publish=True, no_post=False, cfg=None):
    cfg = cfg or load_beta_config()
    if not cfg.get("enabled", False):
        print("[beta] Disabled in config/beta.json — exiting.")
        return

    txt = get_text_folder_for_day(day)
    transcript = txt / "transcript_gr.txt"
    if not transcript.exists():
        print(f"⏳ [beta] {transcript} not found — waiting for prod transcript, exiting.")
        return

    summary_file = txt / cfg["summary_filename"]
    if not summary_file.exists():
        with timing_step("summarize_beta", date=day.isoformat()):
            summarize_for_day_beta(day, cfg=cfg)
    else:
        print(f"[beta] {summary_file} exists — skipping summarization.")

    if no_post:
        print("⏭️  [beta] --no-post specified, skipping Substack posting.")
        return

    flag_file = txt / cfg["flag_filename"]
    if summary_file.exists() and not flag_file.exists():
        cover_path = txt / "cover.png"
        if not cover_path.exists():
            print(f"⏳ [beta] {cover_path} not found — waiting for prod cover, skipping post this run.")
            return
        if not cfg["substack_url"].startswith("https://"):
            print("❌ [beta] substack_url is not configured (still the placeholder?) — skipping post.")
            return
        secrets_root = Path(os.getenv("SECRETS_ROOT", "./data"))
        session_path = secrets_root / cfg["substack_session_file"]
        with timing_step("post_to_substack_beta", date=day.isoformat()):
            if post_to_substack(summary_file, publish, cover_path=cover_path,
                                substack_url=cfg["substack_url"],
                                session_file=str(session_path), lang="en"):
                flag_file.touch()


def main():
    parser = argparse.ArgumentParser(description="Generate and post beta Cyprus news summary.")
    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (defaults to yesterday)")
    parser.add_argument("--draft", action="store_true", help="Save draft instead of publishing")
    parser.add_argument("--no-post", action="store_true", help="Skip Substack posting entirely")
    parser.add_argument("--config", type=str, help="Path to an alternate beta config JSON")
    args = parser.parse_args()

    try:
        day = resolve_day(args.date)
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD (e.g. 2026-09-01).")
        return
    if day is None:
        return

    cfg = load_beta_config(args.config) if args.config else None
    run_beta(day, publish=not args.draft, no_post=args.no_post, cfg=cfg)


if __name__ == "__main__":
    main()
