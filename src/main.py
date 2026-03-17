import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
from datetime import date, datetime, timedelta
import requests
from zoneinfo import ZoneInfo

from openai import OpenAI

from article_loaders.cm_loader import refresh_cm
from helpers import get_media_folder_for_day, get_root_folder_for_day, get_text_folder_for_day, make_folders
from article_loaders.in_cyprus_loader import refresh_ic
from article_loaders.philenews_loader import refresh_philenews
from article_loaders.sigmalive_loader import refresh_sigmalive
from article_loaders.politis_loader import refresh_politis, refresh_en_politis
from article_loaders.evropakipr_loader import refresh_evropakipr
from article_loaders.cyprusbutterfly_loader import refresh_cyprusbutterfly
from article_loaders.kibrispostasi_loader import refresh_kibrispostasi

# Map language codes to their article refresh functions
LANG_REFRESHERS = {
    "el": [
        ("Philenews", refresh_philenews),
        ("Sigmalive", refresh_sigmalive),
        ("Politis", refresh_politis),
    ],
    "ru": [
        ("EvropaKipr", refresh_evropakipr),
        ("Cyprus Butterfly", refresh_cyprusbutterfly),
    ],
    "tr": [
        ("Kıbrıs Postası", refresh_kibrispostasi),
    ],
}
from post_to_substack import post_to_substack
from summarize import load_articles, summarize_for_day, link_articles_to_summary, strip_summary_marker, split_summary, get_article_sources, reorder_sections
from ongoing_topics import (
    load_ongoing_topics, save_ongoing_topics, expire_topics,
    detect_ongoing_topics, update_topics, restructure_summary_with_topics,
)
from image import generate_cover_from_md
from transcribe import transcribe_for_day
from timing import timing_step
from lang_config import load_language_config, get_translation_languages, get_native_summary_languages, get_source_language
from translate import translate_summary
from date_heading import generate_date_heading


CY_TZ = ZoneInfo("Europe/Nicosia")
START_HOUR = 6  # Don't process until 6am — more articles available by then


MIN_VIDEO_SIZE_MB = 100

def download_video(url, local_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        if size_mb < MIN_VIDEO_SIZE_MB:
            os.remove(local_path)
            raise Exception(f"Downloaded file from {url} too small ({size_mb:.1f} MB < {MIN_VIDEO_SIZE_MB} MB)")
    else:
        raise Exception(f"Failed to download video from {url}. Status code: {response.status_code}")

def extract_audio(local_filename_video, local_filename_audio, local_filename_audio_short_prefix):
    subprocess.run([
                "ffmpeg", "-i", local_filename_video, "-vn",
                "-codec:a", "libmp3lame", "-qscale:a", "4",
                local_filename_audio
            ], check=True)

    print("Splitting audio into 3-minute segments...")
    subprocess.run([
        "ffmpeg", "-i", local_filename_video, "-vn",
        "-segment_time", "00:03:00", "-f", "segment",
        "-reset_timestamps", "1", "-codec:a", "libmp3lame", "-qscale:a", "4",
        f"{local_filename_audio_short_prefix}%03d.mp3"
    ], check=True)

# def refresh_saved_articles_if_needed(day:date):
#     articles =  load_articles(day, day)
#     if len(articles) == 0:
#         refresh_cm()
#         refresh_ic()

def refresh_saved_articles():
    try:
        refresh_cm()
    except Exception as e:
        print(f"⚠️ Failed to refresh cyprus mail: {e}")
    try:
        refresh_ic()
    except Exception as e:
        print(f"⚠️ Failed to refresh in cyprus: {e}")
    try:
        refresh_en_politis()
    except Exception as e:
        print(f"⚠️ Failed to refresh English Politis: {e}")

def generate_for_date(day: date):
    make_folders(day)

    date_str = day.strftime('%d%m%y')  # e.g. 280625
    base = "http://v6.cloudskep.com/rikvod/idisisstisokto"
    video_urls = [
        f"{base}/8news{date_str}.mp4?attachment=true",
        f"{base}/8news{date_str}02.mp4?attachment=true",
        f"{base}/8news_{date_str}.mp4?attachment=true",
        f"{base}/d8news{date_str}.mp4?attachment=true",
    ]

    # Target paths
    media = get_media_folder_for_day(day)
    txt = get_text_folder_for_day(day)

    local_filename_video = media /  f"video.mp4"
    local_filename_audio = media /  f"audio.mp3"
    local_filename_audio_short_prefix = media /  f"split_audio"
    text_gr = txt / f"transcript_gr.txt"
    summary_md = txt /  f"summary.txt"
    cover_file = txt /  f"cover.png"
    log_context = {
        "date": day.isoformat(),
        "video_path": local_filename_video,
        "audio_path": local_filename_audio,
        "transcript_path": text_gr,
        "summary_path": summary_md,
        "cover_path": cover_file,
    }

    # Skip if text already exists
    if os.path.exists(text_gr):
        print(f"{text_gr} exists — skipping video download, audio extraction, and transcription.")

    else:
        # Download video if needed
        if os.path.exists(local_filename_video):
            print(f"{local_filename_video} exists.")
        else:
            print(f"Downloading video to {local_filename_video}...")
            with timing_step(
                "video_download",
                **log_context,
                urls=video_urls,
            ):
                for i, url in enumerate(video_urls):
                    try:
                        download_video(url, local_filename_video)
                        break
                    except Exception:
                        if i == len(video_urls) - 1:
                            raise
                        continue
                
                

        # Extract audio if needed
        if os.path.exists(local_filename_audio):
            print(f"{local_filename_audio} exists.")
        else:
            print(f"Extracting audio to {local_filename_audio}...")
            with timing_step("audio_extract_segment", **log_context):
                extract_audio(local_filename_video, local_filename_audio, local_filename_audio_short_prefix)
        
        if os.path.exists(text_gr):
            print(f"{text_gr} exists.")
        else:
            print(f"Transcribing text to {text_gr}...")
            with timing_step("transcription", **log_context):
                transcribe_for_day(day)
        # if os.path.exists(text_gr):
        #     try:
        #         shutil.rmtree(media)
        #         print(f"🗑️ Deleted media folder: {media}")
        #     except Exception as e:
        #         print(f"⚠️ Failed to delete media folder {media}: {e}")
    if os.path.exists(summary_md):
        print(f"{summary_md} exists.")
    else:
        print(f"Summarizing text to {summary_md}...")
        with timing_step("summarization", **log_context):
            refresh_saved_articles()
            summarize_for_day(day)
        
    # NEW: load from file and generate cover.png in same folder
    if os.path.exists(cover_file):
        print(f"{cover_file} exists.")
        return False
    else:
        try:
            with timing_step("cover_generation", **log_context):
                md_text = Path(summary_md).read_text(encoding="utf-8")
                from openai import OpenAI
                # Reuse your OpenAI client
                client = OpenAI()
                out_dir = Path(summary_md).parent
                generate_cover_from_md(
                    client=client,
                    day=day,
                    markdown=md_text,
                    out_dir=str(out_dir),
                    allow_faces=True,     # flip to False if needed on sensitive days
                    lead_subject=None,    # or pass an explicit subject
                    model="gpt-image-1"
                )
        except Exception as e:
            print(f"⚠️ Failed to read {summary_md} for cover generation: {e}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate and post Cyprus news summary.")
    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (defaults to yesterday)")
    parser.add_argument("--draft", action="store_true", help="Save draft instead of publishing")
    parser.add_argument("--no-post", action="store_true", help="Skip Substack posting entirely (generate summaries only)")
    parser.add_argument("--lang", type=str, help="Run only a specific language pipeline (e.g. 'el'). English files must already exist for translation languages.")

    args = parser.parse_args()

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD (e.g. 2025-06-01).")
            return
    else:
        now_cy = datetime.now(CY_TZ)
        if now_cy.hour < START_HOUR:
            print(f"⏳ It's {now_cy.strftime('%H:%M')} in Cyprus — too early, waiting until {START_HOUR}:00.")
            return
        day = now_cy.date() - timedelta(days=1)

    txt = get_text_folder_for_day(day)
    cover_path = txt / "cover.png"
    post = False if args.draft else True
    no_post = args.no_post
    run_lang = args.lang  # None means run all

    config = load_language_config()
    native_langs = get_native_summary_languages(config)
    translation_langs = get_translation_languages(config)

    # Apply --lang filter
    if run_lang and run_lang != "en":
        if run_lang in native_langs:
            native_langs = {run_lang: native_langs[run_lang]}
        else:
            native_langs = {}
        if run_lang in translation_langs:
            translation_langs = {run_lang: translation_langs[run_lang]}
        else:
            translation_langs = {}

    # =========================================================
    # PHASE 1: Generate all summaries
    # =========================================================

    # --- English ---
    if run_lang is None or run_lang == "en":
        generate_for_date(day)

        # --- Ongoing topic detection (runs on English summary) ---
        en_summary_without_links = txt / config["en"]["summary_without_links_filename"]
        if en_summary_without_links.exists():
            try:
                with timing_step("detect_ongoing_topics", date=day.isoformat()):
                    topics_data = load_ongoing_topics()
                    topics_data = expire_topics(topics_data, day)

                    summary_text = en_summary_without_links.read_text(encoding="utf-8")
                    client = OpenAI()
                    detected = detect_ongoing_topics(
                        client, summary_text, topics_data["topics"], day
                    )

                    topics_data, topics_changed = update_topics(topics_data, detected, day)
                    save_ongoing_topics(topics_data)

                    if topics_changed:
                        print("🔄 New ongoing topics detected, restructuring English summary...")
                        restructured = restructure_summary_with_topics(
                            client, summary_text, topics_data["topics"], lang="en"
                        )
                        en_summary_without_links.write_text(restructured, encoding="utf-8")
                        print(f"✅ Restructured summary saved to {en_summary_without_links}")

                        # Also restructure the final linked summary if it exists
                        en_summary_final = txt / config["en"]["summary_filename"]
                        if en_summary_final.exists():
                            final_text = en_summary_final.read_text(encoding="utf-8")
                            restructured_final = restructure_summary_with_topics(
                                client, final_text, topics_data["topics"], lang="en"
                            )
                            en_summary_final.write_text(restructured_final, encoding="utf-8")
                            print(f"✅ Restructured final summary saved to {en_summary_final}")
            except Exception as e:
                print(f"⚠️ Ongoing topic detection failed (non-fatal): {e}")
                import traceback
                traceback.print_exc()

    # --- Native summary languages (e.g. Greek) ---
    for lang, lang_cfg in native_langs.items():
        try:
            target_output_file = txt / lang_cfg["summary_filename"]

            if not target_output_file.exists():
                for name, refresher in LANG_REFRESHERS.get(lang, []):
                    try:
                        refresher()
                    except Exception as e:
                        print(f"⚠️ Failed to refresh {name}: {e}")

                print(f"Summarizing natively in {lang}...")
                with timing_step("summarize_native", date=day.isoformat(), lang=lang):
                    summarize_for_day(day, lang=lang)
            else:
                print(f"{target_output_file} exists — skipping {lang} native summarization.")
        except Exception as e:
            print(f"❌ Error generating native summary for '{lang}': {e}")
            import traceback
            traceback.print_exc()

    # --- Translation languages ---
    for lang, lang_config in translation_langs.items():
        try:
            source_lang = get_source_language(lang_config)
            source_summary_file = txt / config[source_lang]["summary_without_links_filename"]

            if not source_summary_file.exists():
                print(f"⚠️ Source summary for {source_lang} not found, skipping {lang}")
                continue

            target_summary_file = txt / lang_config["summary_without_links_filename"]
            target_output_file = txt / lang_config["summary_filename"]

            if not target_output_file.exists():
                source_text = source_summary_file.read_text(encoding="utf-8")
                body_match = re.search(r'(### .+)', source_text, re.DOTALL)
                source_body = body_match.group(1) if body_match else source_text

                print(f"Translating summary to {lang}...")
                client = OpenAI()
                with timing_step("translate_summary", date=day.isoformat(), lang=lang):
                    translated, usage = translate_summary(client, source_body, target_lang=lang)

                first_sections = lang_config.get("first_sections")
                if first_sections:
                    translated = reorder_sections(translated, first_sections)

                date_heading = generate_date_heading(day, lang)
                target_summary_file.write_text(
                    date_heading + "\n\n" + translated, encoding="utf-8"
                )
                print(f"✅ Translated summary saved to {target_summary_file}")

                article_sources = lang_config.get("article_sources", [])
                for name, refresher in LANG_REFRESHERS.get(lang, []):
                    try:
                        refresher()
                    except Exception as e:
                        print(f"⚠️ Failed to refresh {name}: {e}")

                if article_sources:
                    start_date = day - timedelta(days=1)
                    end_date = day + timedelta(days=1)
                    filtered_articles = load_articles(start_date, end_date, article_sources)
                    top_stories, main_summary = split_summary(translated)
                    with open("src/prompts/link_prompt.txt", "r", encoding="utf-8") as f:
                        link_prompt = f.read().strip()
                    linked, _ = link_articles_to_summary(client, main_summary, filtered_articles, link_prompt, article_sources)
                    final = date_heading + "\n\n" + top_stories + "\n\n" + linked
                else:
                    final = date_heading + "\n\n" + translated

                final = strip_summary_marker(final)
                target_output_file.write_text(final, encoding="utf-8")
                print(f"✅ Final {lang} summary saved to {target_output_file}")
            else:
                print(f"{target_output_file} exists — skipping {lang} translation.")
        except Exception as e:
            print(f"❌ Error generating translation for '{lang}': {e}")
            import traceback
            traceback.print_exc()

    # =========================================================
    # PHASE 2: Post all summaries to Substack
    # =========================================================

    if no_post:
        print("⏭️  --no-post specified, skipping all Substack posting.")
        return

    secrets_root = Path(os.getenv("SECRETS_ROOT", "./data"))

    # --- English ---
    if run_lang is None or run_lang == "en":
        summary_md = txt / "summary.txt"
        flag_file = txt / "flag.txt"
        if summary_md.exists() and not flag_file.exists():
            try:
                log_context = {"date": day.isoformat(), "summary_path": summary_md, "cover_path": cover_path, "publish": post}
                with timing_step("post_to_substack", **log_context):
                    if post_to_substack(summary_md, post, cover_path=cover_path, lang="en"):
                        flag_file.touch()
            except Exception as e:
                print(f"❌ Error posting English summary: {e}")
                import traceback
                traceback.print_exc()

    # --- Native summary languages ---
    for lang, lang_cfg in native_langs.items():
        try:
            target_output_file = txt / lang_cfg["summary_filename"]
            target_flag_file = txt / lang_cfg["flag_filename"]
            if target_output_file.exists() and not target_flag_file.exists():
                session_path = secrets_root / lang_cfg["substack_session_file"]
                substack_url = lang_cfg["substack_url"]
                with timing_step("post_to_substack", date=day.isoformat(), lang=lang):
                    if post_to_substack(target_output_file, post, cover_path=cover_path, substack_url=substack_url, session_file=str(session_path), lang=lang):
                        target_flag_file.touch()
        except Exception as e:
            print(f"❌ Error posting native summary for '{lang}': {e}")
            import traceback
            traceback.print_exc()

    # --- Translation languages ---
    for lang, lang_config in translation_langs.items():
        try:
            target_output_file = txt / lang_config["summary_filename"]
            target_flag_file = txt / lang_config["flag_filename"]
            if target_output_file.exists() and not target_flag_file.exists():
                session_path = secrets_root / lang_config["substack_session_file"]
                substack_url = lang_config["substack_url"]
                with timing_step("post_to_substack", date=day.isoformat(), lang=lang):
                    if post_to_substack(target_output_file, post, cover_path=cover_path, substack_url=substack_url, session_file=str(session_path), lang=lang):
                        target_flag_file.touch()
        except Exception as e:
            print(f"❌ Error posting translation for '{lang}': {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
