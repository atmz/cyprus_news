# summarize.py – Refactored with flexible sources and modular structure

from collections import defaultdict
import os
import re
import sys
import argparse
import json
from datetime import datetime, timedelta
from openai import OpenAI
from dateutil.parser import parse as parse_datetime, ParserError
from textwrap import dedent
import time
import tiktoken


# --- Configuration ---
SUMMARY_DIR = "summaries"
ARTICLE_SOURCES = [
    {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
    {"name": "Cyprus Mail", "tag": "CM", "file": "data/cm_crime_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_economy_articles.json"}
]
MODEL_NAME = "gpt-4o"
PROMPT_FILE = "prompt.txt"
LINK_PROMPT_FILE = "link_prompt.txt"
SYSTEM_PROMPT_FILE = "system_prompt.txt"
FIRST_CHUNK_SYSTEM_PROMPT_FILE = "first_chunk_system_prompt.txt"
FOLLOWUP_CHUNK_SYSTEM_PROMPT_FILE = "followup_chunk_system_prompt.txt"

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
date_heading += "This is a summary of yesterday's 8pm RIK news broadcast. Where available, links to related English-language articles from the Cyprus Mail and In-Cyprus are provided for further reading. Please note that this summary was generated with the assistance of AI and may contain inaccuracies."

summary_file = os.path.join(SUMMARY_DIR, f"8news{summary_date.strftime('%d%m%y')}_summary_without_links.md")
output_file = os.path.join(SUMMARY_DIR, f"8news{summary_date.strftime('%d%m%y')}_summary.md")

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
with open(LINK_PROMPT_FILE, "r", encoding="utf-8") as f:
    link_prompt = f.read().strip()

with open(FIRST_CHUNK_SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
    first_chunk_system_prompt = f.read().strip()
with open(FOLLOWUP_CHUNK_SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
    followup_chunk_system_prompt = f.read().strip()

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
        temperature=0.0
    )
    return response.choices[0].message.content.strip(), response.usage

from textwrap import dedent

def combine_summaries(chunks):
    # Function to parse a summary into a dictionary of sections
    def parse_summary_sections(summary_text):
        sections = defaultdict(list)
        current_section = None
        for line in summary_text.strip().splitlines():
            if line.startswith("### "):
                current_section = line.replace("### ", "").strip()
            elif line.startswith("- ") or line.startswith("• "):
                if current_section:
                    sections[current_section].append(line.strip())
        return sections

    # Merge all chunk dictionaries
    combined = defaultdict(list)
    for chunk in chunks:
        parsed = parse_summary_sections(chunk)
        for section, bullets in parsed.items():
            combined[section].extend(bullets)

    # Optional: Deduplicate within sections
    for section in combined:
        combined[section] = list(dict.fromkeys(combined[section]))

    # Define canonical section order
    section_order = [
        "Top stories",
        "Government & Politics",
        "Cyprus Problem",
        "Justice",
        "Foreign Affairs",
        "Public Health & Safety",
        "Energy & Infrastructure",
        "Education",
        "Culture",
        "Society",
        "Sports"
    ]

    # Generate final markdown
    final_md = ""
    for section in section_order:
        if combined[section]:
            final_md += f"### {section}\n"
            final_md += "\n".join(combined[section]) + "\n\n"
    return final_md


# New chunk-aware generate_summary function with different prompts for the first and remaining chunks
def generate_chunked_summary(
    transcript_text,
    client,
    prompt_template,
    first_chunk_system_prompt,
    followup_chunk_system_prompt,
    model="gpt-4o",
    chunk_separator="\n\n",
    max_chunk_size=3000,
    sleep_time=60
):

    def count_tokens(text):
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))

    # Split into paragraphs and then chunk based on token count
    paragraphs = transcript_text.split(chunk_separator)
    chunks = []
    current_chunk = []

    for para in paragraphs:
        current_chunk.append(para)
        if count_tokens(chunk_separator.join(current_chunk)) > max_chunk_size:
            chunks.append(chunk_separator.join(current_chunk[:-1]))
            current_chunk = [para]
    if current_chunk:
        chunks.append(chunk_separator.join(current_chunk))

    all_summaries = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for i, chunk in enumerate(chunks):
        is_first = (i == 0)
        system_prompt = first_chunk_system_prompt if is_first else followup_chunk_system_prompt

        previous_summary = "".join(all_summaries)
        user_prompt = prompt_template.replace("[PREVIOUS_SUMMARY]", previous_summary if not is_first else "")

        print(f"\n⏳ Summarizing chunk {i + 1}/{len(chunks)}... ({count_tokens(chunk)} tokens)")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "user", "content": chunk}
            ],
            temperature=0.0
        )

        summary = response.choices[0].message.content.strip()
        all_summaries.append(summary)

        if hasattr(response, "usage"):
            total_usage["prompt_tokens"] += response.usage.prompt_tokens
            total_usage["completion_tokens"] += response.usage.completion_tokens

        if i < len(chunks) - 1:
            print(f"🕒 Sleeping {sleep_time}s before next chunk...")
            time.sleep(sleep_time)

    combined_summary = combine_summaries(all_summaries)
    return combined_summary, total_usage


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


def split_summary(summary):
    split_match = re.split(r'(?m)^### [^\n]+', summary)
    headers = re.findall(r'(?m)^### [^\n]+', summary)
    sections = [h.strip() + "\n" + b.strip() for h, b in zip(headers, split_match[1:])]
    top_stories_text = ""
    main_summary_text = ""

    if sections and sections[0].strip().startswith("### Top stories"):
        top_stories_text = sections[0].strip()
        main_summary_text = "\n".join(sections[1:]).strip()
    else:
        print("⚠️ No Top stories section found, sending entire summary.")
        main_summary_text = summary

    return top_stories_text, main_summary_text

# --- Linking Logic ---
def link_articles_to_summary(summary_text, filtered_articles):
    
    if not filtered_articles:
        print("No article metadata found, skipping link injection.")
        return summary_text, None

    linking_prompt = f"""{link_prompt}

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
    summary, usage1 =  generate_chunked_summary(transcript_text, client, prompt_text, first_chunk_system_prompt, followup_chunk_system_prompt)

    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(date_heading + "\n\n" + summary)
    print(f"✅ Summary saved to {summary_file}")

start_date = summary_date - timedelta(days=1)
end_date = summary_date + timedelta(days=1)
filtered_articles = load_articles(start_date, end_date)

top_stories, main_summary = split_summary(summary)

linked_main_summary, usage2 = link_articles_to_summary(main_summary, filtered_articles)

final_output = date_heading + "\n\n" + top_stories + "\n\n" + linked_main_summary

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