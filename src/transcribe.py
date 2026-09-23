import os
import argparse
import json
from datetime import datetime
from datetime import date
from helpers import get_media_folder_for_day, get_text_folder_for_day
from openai import OpenAI
from timing import timing_step

MAX_RETRIES = 3
MIN_EXPECTED_CHARS = 1000  # Adjust depending on your clip length/content

def print_helper(str : str):
    print("TRANSCRIBE: " + str)

def transcribe_with_retry(client, audio_file, retries=3, min_chars=200):
    best_result = None
    best_length = -1  # keep even an empty result — never return None

    for attempt in range(retries):
        # Rewind before every attempt: the first call consumes the file
        # handle, and a retry would otherwise upload an empty (EOF) file.
        audio_file.seek(0)
        result = client.audio.transcriptions.create(
            model="gpt-transcribe",
            file=audio_file
        )
        text = result.text.strip()
        length = len(text)

        if length > best_length:
            best_result = result
            best_length = length

        if length >= min_chars:
            return result  # Good enough, return immediately

        print_helper(f"⚠️ Attempt {attempt+1}: possibly truncated (len={length}) — retrying...")

    print_helper(f"❌ All retries failed to reach threshold ({min_chars} chars). Returning longest result (len={best_length}).")
    return best_result

def transcribe_for_day(day : date):
    client = OpenAI()
    combined_text = []
    combined_json = []

    mp3_folder = get_media_folder_for_day(day)
    output_folder = get_text_folder_for_day(day)
    txt_output = output_folder / "transcript_gr.txt"
    json_output = output_folder / "transcript_gr.json"
    log_context = {
        "date": day.isoformat(),
        "media_folder": mp3_folder,
        "transcript_path": txt_output,
        "transcript_json_path": json_output,
    }
    i = 0
    with timing_step("transcription_loop", **log_context):
        while True:
            filename = mp3_folder / f"split_audio{i:03d}.mp3"
            if not os.path.exists(filename):
                break
            print_helper(f"Transcribing {filename}...")
            with timing_step("transcription_chunk", **log_context, chunk_index=i, chunk_path=filename):
                # A short trailing segment (credits music after the 3-minute
                # splits) legitimately transcribes to nothing — don't burn
                # retries demanding 200 chars from a few seconds of audio,
                # and never let an empty segment sink the whole transcript
                # (this lost the 2026-09-22 bulletin for a full day).
                small_file = os.path.getsize(filename) < 500_000  # ~<30s of mp3
                with open(filename, "rb") as audio_file:
                    result = transcribe_with_retry(
                        client,
                        audio_file,
                        min_chars=0 if small_file else 200,
                    )
                if result is None or not result.text.strip():
                    print_helper(f"⚠️ Empty transcription for {filename} — skipping segment.")
                else:
                    combined_text.append(result.text)
                    combined_json.append(result.model_dump())  # Convert to dict for JSON
            i += 1

    if i == 0:
        raise SystemExit(f"No input files found in directory: {mp3_folder}")

    # --- Save plain text ---
    with timing_step("transcription_write_text", **log_context):
        with open(txt_output, "w", encoding="utf-8") as f:
            f.write("\n\n".join(combined_text))

    # --- Save full JSON ---
    with timing_step("transcription_write_json", **log_context):
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(combined_json, f, ensure_ascii=False, indent=2)

    print_helper(f"✅ Saved transcript to {txt_output}")
    print_helper(f"📦 Saved full JSON to {json_output}")
