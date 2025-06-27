# summarize.py – Refactored with flexible sources and modular structure

import os
import sys
import argparse
import json
from datetime import datetime, timedelta
from openai import OpenAI
from dateutil.parser import parse as parse_datetime, ParserError

# --- Configuration ---
SUMMARY_DIR = "summaries"
ARTICLE_SOURCES = [
    {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_economy_articles.json"}
]
MODEL_NAME = "gpt-4o"
PROMPT_FILE = "prompt.txt"
SYSTEM_PROMPT_FILE = "system_prompt.txt"

# --- Parse arguments ---
parser = argparse.ArgumentParser(description="Summarize a transcript file using OpenAI.")
parser.add_argument("transcript_file", help="Path to the transcript file (e.g., news/8news250625_gr.txt)")
parser.add_argument("--date", help="Optional date in DDMMYY format (e.g., 250625)")
args = parser.parse_args()

# --- Derive summary date ---
if args.date:
    try:
        summary_date = datetime.strptime(args.date, "%d%m%y")
    except ValueError:
        sys.exit("Invalid date format. Use DDMMYY (e.g., 250625)")
else:
    try:
        filename_date = os.path.basename(args.transcript_file).split("_")[0].replace("8news", "")
        summary_date = datetime.strptime(filename_date, "%d%m%y")
    except Exception:
        sys.exit("Could not infer date from filename. Use --date to specify manually.")

date_heading = f"## 📰 News Summary for {summary_date.strftime('%A, %d %B %Y')}\n\n"
date_heading += "Here is a summary of the RIK 8pm news broadcast, with links to related newspaper articles from the Cyprus Mail and In-Cyprus. This is an AI-generated summary, so mistakes may occur."

summary_file = os.path.join(SUMMARY_DIR, f"8news{summary_date.strftime('%d%m%y')}_summary.md")
output_file = summary_file

# --- Load required files ---
for required_file in [args.transcript_file, PROMPT_FILE, SYSTEM_PROMPT_FILE]:
    if not os.path.exists(required_file):
        sys.exit(f"Required file not found: {required_file}")

with open(args.transcript_file, "r", encoding="utf-8") as f:
    transcript_text = f.read()
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    prompt_text = f.read().strip().replace("[DATE]", summary_date.strftime('%A, %d %B %Y'))
with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
    system_prompt = f.read().strip()

client = OpenAI()

# --- Summary Generation ---
def generate_summary():
    print("Sending to OpenAI for summarization...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
            {"role": "user", "content": transcript_text}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip(), response.usage

# --- Load and Filter Articles ---
def load_articles(start_date, end_date):
    results = []
    for source in ARTICLE_SOURCES:
        if not os.path.exists(source["file"]):
            continue
        with open(source["file"], "r", encoding="utf-8") as f:
            try:
                articles = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse {source['file']}")
                continue

        for a in articles:
            dt_raw = a.get("datetime")
            if not dt_raw:
                continue
            try:
                dt = parse_datetime(dt_raw).replace(tzinfo=None)
            except (ParserError, ValueError):
                continue
            if start_date <= dt <= end_date:
                results.append({
                    "t": a.get("title"),
                    "a": a.get("abstract"),
                    "u": a.get("url"),
                    "tag": source["tag"]
                })
    return results

# --- Linking Logic ---
def link_articles_to_summary(summary_text, filtered_articles):
    if not filtered_articles:
        print("No article metadata found, skipping link injection.")
        return summary_text, None

    linking_prompt = f"""
Match the following newspaper articles to the relevant story summaries. For each bullet point, if one of the articles clearly corresponds to the story, append a markdown link in this format:

- [(CM)](https://cyprus-mail.com/...) for Cyprus Mail
- [(IC)](https://in-cyprus.philenews.com/...) for In-Cyprus

Use the article's actual link. If no article fits, leave the line unchanged. Do not modify or rewrite the text otherwise.

SUMMARY:
{summary_text}

ARTICLES:
{json.dumps(filtered_articles, ensure_ascii=False)}
"""

    print("Sending to OpenAI for article-linking...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a careful editor helping link summaries to matching newspaper articles. Do not alter text except to add a (CM) or (IC) link."},
            {"role": "user", "content": linking_prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip(), response.usage

# --- Main Logic ---
summary_exists = os.path.exists(summary_file)
if summary_exists:
    print(f"📄 Found existing summary: {summary_file}, skipping summarization.")
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = f.read().replace(date_heading + "\n\n", "", 1)
    usage1 = None
else:
    summary, usage1 = generate_summary()
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(date_heading + "\n\n" + summary)
    print(f"✅ Summary saved to {summary_file}")

start_date = summary_date - timedelta(days=1)
end_date = summary_date + timedelta(days=1)
filtered_articles = load_articles(start_date, end_date)
linked_summary, usage2 = link_articles_to_summary(summary, filtered_articles)

final_output = date_heading + "\n\n" + linked_summary

with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_output)

# --- Token usage & cost ---
total_tokens = 0
if usage1:
    total_tokens += usage1.prompt_tokens + usage1.completion_tokens
if usage2:
    total_tokens += usage2.prompt_tokens + usage2.completion_tokens

COST_PER_1K_PROMPT = 0.005
COST_PER_1K_COMPLETION = 0.015
estimated_cost = (total_tokens / 1000) * ((COST_PER_1K_PROMPT + COST_PER_1K_COMPLETION) / 2)

print(f"\n✅ Final summary with links saved to {output_file}")
print(f"📊 Token usage: ~{total_tokens} total")
print(f"💰 Estimated cost: ${estimated_cost:.4f} USD")