import argparse
import os
from pathlib import Path
import shutil
import subprocess
from datetime import date, datetime, timedelta
import requests

from article_loaders.cm_loader import refresh_cm
from helpers import get_media_folder_for_day, get_root_folder_for_day, get_text_folder_for_day, make_folders
from article_loaders.in_cyprus_loader import refresh_ic
from post_to_substack import post_to_substack
from summarize import load_articles, summarize_for_day
from transcribe import transcribe_for_day
def download_video(url, local_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        raise Exception(f"Failed to download video. Status code: {response.status_code}")

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
    refresh_cm()
    # refresh_ic()

def generate_for_date(day: date):
    make_folders(day)

    date_str = day.strftime('%d%m%y')  # e.g. 280625
    url_video = f"http://v6.cloudskep.com/rikvod/idisisstisokto/8news{date_str}.mp4?attachment=true"

    # Target paths
    media = get_media_folder_for_day(day)
    txt = get_text_folder_for_day(day)

    local_filename_video = os.path.join(media, f"video.mp4")
    local_filename_audio = os.path.join(media, f"audio.mp3")
    local_filename_audio_short_prefix = os.path.join(media, f"split_audio")
    text_gr = os.path.join(txt, f"transcript_gr.txt")
    summary_md = os.path.join(txt, f"summary.txt")

    # Skip if text already exists
    if os.path.exists(text_gr):
        print(f"{text_gr} exists — skipping video download, audio extraction, and transcription.")

    else:
        # Download video if needed
        if os.path.exists(local_filename_video):
            print(f"{local_filename_video} exists.")
        else:
            print(f"Downloading video to {local_filename_video}...")
            download_video(url_video, local_filename_video)

        # Extract audio if needed
        if os.path.exists(local_filename_audio):
            print(f"{local_filename_audio} exists.")
        else:
            print(f"Extracting audio to {local_filename_audio}...")
            extract_audio(local_filename_video, local_filename_audio, local_filename_audio_short_prefix)
        
        if os.path.exists(text_gr):
            print(f"{text_gr} exists.")
        else:
            print(f"Transcribing text to {text_gr}...")
            transcribe_for_day(day)
        if os.path.exists(text_gr):
            try:
                shutil.rmtree(media)
                print(f"🗑️ Deleted media folder: {media}")
            except Exception as e:
                print(f"⚠️ Failed to delete media folder {media}: {e}")
    if os.path.exists(summary_md):
        print(f"{summary_md} exists.")
    else:
        print(f"Summarizing text to {summary_md}...")
        refresh_saved_articles()
        summarize_for_day(day)
        
    

def main():
    parser = argparse.ArgumentParser(description="Generate and post Cyprus news summary.")
    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (defaults to yesterday)")
    args = parser.parse_args()

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD (e.g. 2025-06-01).")
            return
    else:
        day = (datetime.now() - timedelta(days=1)).date()

    generate_for_date(day)

    txt = get_text_folder_for_day(day)
    summary_md = os.path.join(txt, "summary.txt")
    post_to_substack(Path(summary_md), True)

if __name__ == "__main__":
    main()