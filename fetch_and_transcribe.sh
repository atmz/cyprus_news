#!/bin/bash

# Set full path for cron/launchd
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Activate the virtualenv
source /Users/alext/news2025/venv/bin/activate

# Change to working directory (just in case)
cd /Users/alext/news2025/
# Usage: ./fetch_and_transcribe.sh [optional DDMMYY]
# Example: ./fetch_and_transcribe.sh 250625

set -e

# --- 1. Get date ---
if [ -n "$1" ]; then
    today="$1"
else
    today=$(date -v -1d +%d%m%y)
fi

# --- 2. Define paths ---
url_video="http://v6.cloudskep.com/rikvod/idisisstisokto/8news${today}.mp4?attachment=true"
downloaded_filename="./news/8news${today}a.mp4?attachment=true"
local_filename_video="./news/8news${today}.mp4"
local_filename_audio="./news/8news${today}.mp3"
local_filename_audio_short_prefix="./news/8news${today}_"
text_gr="./news/8news${today}_gr.txt"
summary="./news/8news${today}_summary.md"

# --- 3. Download video if needed ---
echo "$local_filename_video."
if [ -f "$local_filename_video" ]; then 
    echo "$local_filename_video exists."
else
    wget "$url_video" -O "$local_filename_video"
fi

# --- 4. Extract audio if needed ---
if [ -f "$local_filename_audio" ]; then
    echo "$local_filename_audio exists."
else
    ffmpeg -i "$local_filename_video" -vn -codec:a libmp3lame -qscale:a 4 "$local_filename_audio"
    ffmpeg -i "$local_filename_video" -vn -segment_time 00:03:00 -f segment -reset_timestamps 1 -codec:a libmp3lame -qscale:a 4 "${local_filename_audio_short_prefix}%03d.mp3"
fi

# --- 5. Run transcription if needed ---
if [ -f "$text_gr" ]; then
    echo "$text_gr exists."
else
    python3 transcribe.py "$today"
fi
# --- 6. Gen summary if needed ---
if [ -f "$summary" ]; then
    echo "$summary exists."
else
    python3 summarize.py "$text_gr" --date "$today"
    python3 post_to_substack "$summary" --publish
fi
