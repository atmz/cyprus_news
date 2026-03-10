# summarize.py – Refactored with flexible sources and modular structure

from collections import defaultdict
import os
import re
import sys
import argparse
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from helpers import get_text_folder_for_day
from openai import OpenAI
from dateutil.parser import parse as parse_datetime, ParserError
from textwrap import dedent
import time
import tiktoken
from timing import timing_step
from date_heading import generate_date_heading
from lang_config import load_language_config
from ongoing_topics import load_ongoing_topics, build_ongoing_topics_section_entries


# --- Configuration ---
SUMMARY_DIR = "summaries"


def get_article_sources(lang="en"):
    config = load_language_config()
    if lang in config:
        return config[lang].get("article_sources", [])
    return []
MODEL_NAME = "gpt-4.1"
PROMPTS_DIR = "src/prompts"
LINK_PROMPT_FILE = "src/prompts/link_prompt.txt"
SYSTEM_PROMPT_FILE = "src/prompts/system_prompt.txt"
DEDUPLICATION_PROMPT_FILE = "src/prompts/deduplication_prompt.txt"


def _resolve_prompt_file(base_name, lang):
    """Try prompt_{lang}.txt first, fall back to prompt.txt."""
    if lang and lang != "en":
        lang_path = os.path.join(PROMPTS_DIR, f"{base_name}_{lang}.txt")
        if os.path.exists(lang_path):
            return lang_path
    return os.path.join(PROMPTS_DIR, f"{base_name}.txt")



from textwrap import dedent

def combine_summaries(chunks, ongoing_topic_names=None):
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

    # Deduplicate within sections — exact matches first, then fuzzy
    from difflib import SequenceMatcher

    def is_near_duplicate(a, b, full_threshold=0.7, prefix_threshold=0.75, prefix_len=80):
        if SequenceMatcher(None, a, b).ratio() > full_threshold:
            return True
        if SequenceMatcher(None, a[:prefix_len], b[:prefix_len]).ratio() > prefix_threshold:
            return True
        return False

    for section in combined:
        combined[section] = list(dict.fromkeys(combined[section]))  # exact
        deduped = []
        for bullet in combined[section]:
            if not any(is_near_duplicate(bullet, kept) for kept in deduped):
                deduped.append(bullet)
            else:
                print(f"🗑️  Deduped [{section}]: {bullet[:100]}...")
        combined[section] = deduped

    # Remove bullets from ongoing topic sections that duplicate Top Stories
    top_stories_keys = ["Top stories", "Κύριες Ειδήσεις"]
    top_bullets = []
    for k in top_stories_keys:
        top_bullets.extend(combined.get(k, []))
    if top_bullets and ongoing_topic_names:
        for topic_name in (ongoing_topic_names or []):
            if topic_name not in combined:
                continue
            deduped = []
            for bullet in combined[topic_name]:
                if any(is_near_duplicate(bullet, tb) for tb in top_bullets):
                    print(f"🗑️  Cross-deduped [{topic_name}] vs Top stories: {bullet[:80]}...")
                else:
                    deduped.append(bullet)
            combined[topic_name] = deduped

    # Build section order: Top stories, then ongoing topics, then canonical sections
    ongoing_topic_names = ongoing_topic_names or []

    # Define canonical section order (English and Greek)
    canonical_sections = [
        "Top stories",          "Κύριες Ειδήσεις",
        "Public Safety",          "Δημόσια Ασφάλεια",
        "Health",                 "Υγεία",
        "Energy & Infrastructure", "Ενέργεια & Υποδομές",
        "Crime & Justice",      "Έγκλημα & Δικαιοσύνη",
        "Government & Politics", "Κυβέρνηση & Πολιτική",
        "Cyprus Problem",       "Κυπριακό",
        "Economy",              "Οικονομία",
        "Foreign Affairs",      "Εξωτερικές Υποθέσεις",
        "Education",            "Εκπαίδευση",
        "Culture",              "Πολιτισμός",
        "Weather",              "Καιρός",
    ]

    # Insert ongoing topic names after both Top stories variants
    # (they come as a pair: "Top stories", "Κύριες Ειδήσεις")
    # We insert after the second one so topics don't jump ahead of
    # the Greek Top stories header.
    top_stories_names = {"Top stories", "Κύριες Ειδήσεις"}
    section_order = []
    top_stories_seen = 0
    top_stories_total = sum(1 for s in canonical_sections if s in top_stories_names)
    for s in canonical_sections:
        section_order.append(s)
        if s in top_stories_names:
            top_stories_seen += 1
            if top_stories_seen == top_stories_total:
                for topic_name in ongoing_topic_names:
                    if topic_name not in section_order:
                        section_order.append(topic_name)

    # Generate final markdown
    final_md = ""
    for section in section_order:
        if combined[section]:
            final_md += f"### {section}\n"
            final_md += "\n".join(combined[section]) + "\n\n"
    for section in combined.keys():
        if section not in section_order:
            print(f"Unexpected section: {section}")
            final_md += f"### {section}\n"
            final_md += "\n".join(combined[section]) + "\n\n"
    return final_md

def reorder_sections(markdown: str, first_sections: list[str]) -> str:
    """Reorder markdown sections so that first_sections appear at the top."""
    parts = re.split(r'(?=^### )', markdown.strip(), flags=re.MULTILINE)
    prioritized = []
    rest = []
    for part in parts:
        if not part.strip():
            continue
        header_match = re.match(r'^### (.+)', part)
        if header_match and header_match.group(1).strip() in first_sections:
            prioritized.append(part)
        else:
            rest.append(part)
    return "\n".join(prioritized + rest).strip() + "\n"


def limit_headlines(text: str, max_count: int = 10) -> str:
    lines = text.strip().splitlines()
    header_lines = []
    bullet_lines = []

    for line in lines:
        if line.strip().startswith("- "):
            bullet_lines.append(line)
        else:
            header_lines.append(line)

    # Keep only the first max_count bullet points
    bullet_lines = bullet_lines[:max_count]

    return "\n".join(header_lines + bullet_lines)

# New chunk-aware generate_summary function with different prompts for the first and remaining chunks
def generate_chunked_summary(
    transcript_text,
    client,
    user_prompt,
    first_chunk_system_prompt,
    followup_chunk_system_prompt,
    headline_system_prompt,
    model="gpt-4.1",
    chunk_separator="\n\n",
    max_chunk_size=3000,
    sleep_time=20,
    ongoing_topics_section="",
    ongoing_topic_names=None,
):

    def count_tokens(text):
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
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

    # Inject ongoing topics into prompt section lists (replace placeholder)
    first_chunk_system_prompt = first_chunk_system_prompt.replace("[ONGOING_TOPIC_SECTIONS]\n", ongoing_topics_section)
    followup_chunk_system_prompt = followup_chunk_system_prompt.replace("[ONGOING_TOPIC_SECTIONS]\n", ongoing_topics_section)

    all_summaries = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for i, chunk in enumerate(chunks):
        is_first = (i == 0)
        if is_first:
            print(f"\n⏳ Summarizing headlines... ({count_tokens(chunk)} tokens)")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": headline_system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.0
            )
            headlines = limit_headlines(response.choices[0].message.content.strip())
            print(f"Summarized chunk{str(i)}\n system_prompt:{headline_system_prompt}\nuser_prompt:{user_prompt}\n chunk:{chunk}\n summary{headlines}\n")
       

        previous_summary = "".join(all_summaries)
        system_prompt = followup_chunk_system_prompt.replace("[PREVIOUS_SUMMARY]", previous_summary) if not is_first else first_chunk_system_prompt

        def get_last_n_words(text, n=100):
            words = text.strip().split()
            return " ".join(words[-n:])

        if not is_first:
            overlap = get_last_n_words(chunks[i - 1], 100)
            chunk_with_overlap = overlap + " " + chunk
        else:
            chunk_with_overlap = chunk

        print(f"\n⏳ Summarizing chunk {i + 1}/{len(chunks)}... ({count_tokens(chunk_with_overlap)} tokens)")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "user", "content": chunk_with_overlap}
            ],
            temperature=0.0
        )

        summary = response.choices[0].message.content.strip()
        print(f"Summarized chunk{str(i)}\n system_prompt:{system_prompt}\nuser_prompt:{user_prompt}\n chunk:{chunk_with_overlap}\n summary{summary}\n")
        all_summaries.append(summary)

        if hasattr(response, "usage"):
            total_usage["prompt_tokens"] += response.usage.prompt_tokens
            total_usage["completion_tokens"] += response.usage.completion_tokens

        if i < len(chunks) - 1:
            print(f"🕒 Sleeping {sleep_time}s before next chunk...")
            time.sleep(sleep_time)
    all_summaries.insert(0,headlines)
    combined_summary = combine_summaries(all_summaries, ongoing_topic_names=ongoing_topic_names or [])
    return combined_summary, total_usage


# --- Load and Filter Articles ---
def load_articles(start_date, end_date, article_sources=None):
    if article_sources is None:
        article_sources = get_article_sources("en")
    results = []
    for source in article_sources:
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
            if start_date <= dt.date() <= end_date:
                results.append({
                    "t": a.get("title"),
                    "a": a.get("abstract"),
                    "u": a.get("url"),
                    "tag": source["tag"]
                })
    return results

def cleanup_merged_summary(client, summary_text, deduplication_prompt):
    final_prompt = f"""{deduplication_prompt}

    SUMMARY:
    {summary_text}

    """
    print("Sending to OpenAI for cleanup...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.2
    )
    print(f"prompt:{final_prompt}\noutput{response.choices[0].message.content.strip()}")
    return response.choices[0].message.content.strip(), response.usage


def strip_summary_marker(text):
    if not text:
        return text
    cleaned = re.sub(r'(?m)^\s*SUMMARY:\s*$', '', text)
    cleaned = re.sub(r'\bSUMMARY:\s*', '', cleaned)
    return cleaned.strip()


def split_summary(summary):
    split_match = re.split(r'(?m)^### [^\n]+', summary)
    headers = re.findall(r'(?m)^### [^\n]+', summary)
    sections = [h.strip() + "\n" + b.strip() for h, b in zip(headers, split_match[1:])]
    top_stories_text = ""
    main_summary_text = ""

    TOP_STORIES_MARKERS = ["### Top stories", "### Κύριες Ειδήσεις", "### Главные новости", "### Головні новини", "### כותרות ראשיות", "### Manşetler"]
    if sections and any(sections[0].strip().startswith(m) for m in TOP_STORIES_MARKERS):
        top_stories_text = sections[0].strip()
        main_summary_text = "\n".join(sections[1:]).strip()
    else:
        print("⚠️ No Top stories section found, sending entire summary.")
        main_summary_text = summary

    return top_stories_text, main_summary_text

# --- Linking Logic ---
def build_tag_examples(article_sources):
    """Build tag format examples from article sources config."""
    seen = set()
    examples = []
    for source in article_sources:
        tag = source["tag"]
        if tag in seen:
            continue
        seen.add(tag)
        examples.append(f"- [({tag})](url) for {source['name']}")
    return "\n".join(examples)


def link_articles_to_summary(client, summary_text, filtered_articles, link_prompt, article_sources=None):

    if not filtered_articles:
        print("No article metadata found, skipping link injection.")
        return summary_text, None

    # Build tag examples and fill in the prompt template
    if article_sources:
        tag_examples = build_tag_examples(article_sources)
    else:
        tag_examples = "- [(CM)](url) for Cyprus Mail\n- [(IC)](url) for In-Cyprus"
    prompt_with_tags = link_prompt.replace("[TAG_EXAMPLES]", tag_examples)

    # Build dynamic system prompt with actual tag names
    tags = [s["tag"] for s in article_sources] if article_sources else ["CM", "IC"]
    tag_list = " or ".join(f"({t})" for t in dict.fromkeys(tags))
    system_msg = f"You are a careful editor helping link summaries to matching newspaper articles. Do not alter text except to add a {tag_list} link. Preserve all ### section headers, bullet points, and markdown structure exactly as they appear in the input."

    linking_prompt = f"""{prompt_with_tags}

    SUMMARY:
    {summary_text}

    ARTICLES:
    {json.dumps(filtered_articles, ensure_ascii=False)}
    """

    print("Sending to OpenAI for article-linking...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": linking_prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip(), response.usage

def summarize_for_day(day, lang="en"):

    # --- Load required files ---
    output_folder = get_text_folder_for_day(day)
    log_context = {
        "date": day.isoformat(),
        "output_folder": output_folder,
        "lang": lang,
    }

    config = load_language_config()
    lang_cfg = config.get(lang, config["en"])

    date_heading = generate_date_heading(day, lang)

    summary_file = output_folder / lang_cfg["summary_without_links_filename"]
    output_file = output_folder / lang_cfg["summary_filename"]
    transcript_file = output_folder / "transcript_gr.txt"

    # Resolve prompt files with language-specific fallback
    prompt_file = _resolve_prompt_file("prompt", lang)
    first_chunk_file = _resolve_prompt_file("first_chunk_system_prompt", lang)
    followup_chunk_file = _resolve_prompt_file("followup_chunk_system_prompt", lang)
    headline_file = _resolve_prompt_file("headline_system_prompt", lang)

    with timing_step("summarize_read_transcript", **log_context, transcript_path=transcript_file):
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript_text = f.read()
    with timing_step("summarize_load_prompts", **log_context):
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip().replace("[DATE]", day.strftime('%A, %d %B %Y'))
        with open(LINK_PROMPT_FILE, "r", encoding="utf-8") as f:
            link_prompt = f.read().strip()
        with open(DEDUPLICATION_PROMPT_FILE, "r", encoding="utf-8") as f:
            deduplication_prompt = f.read().strip()

        with open(first_chunk_file, "r", encoding="utf-8") as f:
            first_chunk_system_prompt = f.read().strip()
        with open(followup_chunk_file, "r", encoding="utf-8") as f:
            followup_chunk_system_prompt = f.read().strip()
        with open(headline_file, "r", encoding="utf-8") as f:
            headline_system_prompt = f.read().strip()


    client = OpenAI()
    # --- Main Logic ---

    # Load ongoing topics for prompt injection
    topics_data = load_ongoing_topics()
    active_topics = topics_data.get("topics", [])
    ongoing_topics_section = build_ongoing_topics_section_entries(active_topics, lang=lang)
    # Add trailing newline so replacement works cleanly when topics exist
    if ongoing_topics_section:
        ongoing_topics_section = ongoing_topics_section + "\n"
    # Collect topic names for section ordering
    name_key = f"name_{lang}" if lang != "en" else "name_en"
    ongoing_topic_names = [t.get(name_key, t["name_en"]) for t in active_topics]

    summary_exists = os.path.exists(summary_file)
    if summary_exists:
        print(f"📄 Found existing summary: {summary_file}, skipping summarization.")
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = f.read().replace(date_heading + "\n\n", "", 1)
        usage1 = None
    else:
        with timing_step("summarize_generate_chunked", **log_context, summary_path=summary_file):
            summary, usage1 =  generate_chunked_summary(
                transcript_text,
                client,
                prompt_text,
                first_chunk_system_prompt,
                followup_chunk_system_prompt,
                headline_system_prompt,
                ongoing_topics_section=ongoing_topics_section,
                ongoing_topic_names=ongoing_topic_names,
            )

            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(date_heading + "\n\n" + summary)
            print(f"✅ Summary saved to {summary_file}")

    start_date = day - timedelta(days=1)
    end_date = day + timedelta(days=1)
    article_sources = get_article_sources(lang)
    filtered_articles = load_articles(start_date, end_date, article_sources)

    top_stories, main_summary = split_summary(summary)

    with timing_step("summarize_cleanup", **log_context):
        cleaned_main_summary, usage2 = cleanup_merged_summary(client, main_summary, deduplication_prompt)

    with timing_step("summarize_link_articles", **log_context):
        linked_main_summary, usage3 = link_articles_to_summary(client, cleaned_main_summary, filtered_articles, link_prompt, article_sources)

    final_output = date_heading + "\n\n" + top_stories + "\n\n" + linked_main_summary
    final_output = strip_summary_marker(final_output)

    with timing_step("summarize_write_output", **log_context, summary_path=output_file):
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_output)

    # --- Token usage & cost ---
    total_tokens = 0
    if usage1:
        total_tokens += usage1["prompt_tokens"] + usage1["completion_tokens"]
    if usage2:
        total_tokens += usage2.prompt_tokens + usage2.completion_tokens
    if usage3:
        total_tokens += usage3.prompt_tokens + usage3.completion_tokens

    COST_PER_1K_PROMPT = 0.005
    COST_PER_1K_COMPLETION = 0.015
    estimated_cost = (total_tokens / 1000) * ((COST_PER_1K_PROMPT + COST_PER_1K_COMPLETION) / 2)

    print(f"\n✅ Final {lang} summary with links saved to {output_file}")
    print(f"📊 Token usage: ~{total_tokens} total")
    print(f"💰 Estimated cost: ${estimated_cost:.4f} USD")
