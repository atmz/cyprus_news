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
        result = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
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
