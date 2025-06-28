import os
import argparse
import json
from datetime import datetime
from openai import OpenAI

# --- Parse CLI arguments ---
parser = argparse.ArgumentParser(description="Transcribe segmented audio files and combine output.")
parser.add_argument("date", help="Date in DDMMYY format (e.g., 250625)")
args = parser.parse_args()

# --- Validate date format ---
try:
    date_obj = datetime.strptime(args.date, "%d%m%y")
except ValueError:
    raise SystemExit("Invalid date format. Please use DDMMYY (e.g., 250625).")

# --- Set up paths ---
prefix = f"news/8news{args.date}_"
txt_output = f"news/8news{args.date}_gr.txt"
json_output = f"news/8news{args.date}_gr.json"

MAX_RETRIES = 3
MIN_EXPECTED_CHARS = 1000  # Adjust depending on your clip length/content

def transcribe_with_retry(audio_file, retries=3, min_chars=200):
    best_result = None
    best_length = 0

    for attempt in range(retries):
        result = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )
        text = result.text.strip()
        length = len(text)

        if length > best_length:
            best_result = result
            best_length = length

        if length >= min_chars:
            return result  # Good enough, return immediately

        print(f"⚠️ Attempt {attempt+1}: possibly truncated (len={length}) — retrying...")

    print(f"❌ All retries failed to reach threshold ({min_chars} chars). Returning longest result (len={best_length}).")
    return best_result

client = OpenAI()
combined_text = []
combined_json = []

i = 0
while True:
    filename = f"{prefix}{i:03d}.mp3"
    if not os.path.exists(filename):
        break
    print(f"Transcribing {filename}...")
    with open(filename, "rb") as audio_file:
        result = transcribe_with_retry(
            audio_file
        )
        combined_text.append(result.text)
        combined_json.append(result.model_dump())  # Convert to dict for JSON
    i += 1

if i == 0:
    raise SystemExit(f"No input files found with prefix: {prefix}")

# --- Save plain text ---
with open(txt_output, "w", encoding="utf-8") as f:
    f.write("\n\n".join(combined_text))

# --- Save full JSON ---
with open(json_output, "w", encoding="utf-8") as f:
    json.dump(combined_json, f, ensure_ascii=False, indent=2)

print(f"✅ Saved transcript to {txt_output}")
print(f"📦 Saved full JSON to {json_output}")
