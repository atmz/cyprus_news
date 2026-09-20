"""Beta summarizer: fork of summarize.py's English path, backed by claude -p.

This file is the beta lane's scratch space — it may freely diverge from
summarize.py. Pure helpers are imported from summarize (read-only reuse);
copy one in here only when an experiment needs to change it.
See docs/superpowers/specs/2026-09-12-beta-pipeline-design.md.

The deterministic guards below (_restore_section_headers, _strip_llm_preamble,
and the "### Top stories" fallback in generate_chunked_summary_beta) exist
because claude-sonnet-5 (vs prod's gpt models) tended to drop the Top stories
header, add commentary, and rewrite header levels in the 2026-02-24 E2E run.
"""

import json
import os
import re
import time
from datetime import timedelta

import tiktoken

from beta_config import load_beta_config
from claude_llm import complete
from date_heading import generate_date_heading
from helpers import get_text_folder_for_day
from ongoing_topics import build_ongoing_topics_section_entries, load_ongoing_topics
from summarize import (
    build_tag_examples,
    combine_summaries,
    limit_headlines,
    load_articles,
    split_summary,
    strip_hallucinated_links,
    strip_inline_emphasis as _strip_inline_emphasis,
    strip_summary_marker,
)
from timing import timing_step


def apply_title_prefix(date_heading, prefix):
    if not prefix:
        return date_heading
    return date_heading.replace("## ", f"## {prefix}", 1)


def _prompt_path(prompts_dir, base_name):
    return os.path.join(prompts_dir, f"{base_name}.txt")


def _count_tokens(text):
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def _add_usage(total, usage):
    if usage:
        total["input_tokens"] += usage.get("input_tokens", 0)
        total["output_tokens"] += usage.get("output_tokens", 0)
        total["cost_usd"] += usage.get("cost_usd", 0.0)


def _restore_section_headers(text):
    """Undo header downgrades: the linking/cleanup model sometimes rewrites
    "### " section headers down to "## ". Their inputs never contain the
    "## " date heading, so any "## " line here is a downgraded section
    header, and this deterministic rewrite is safe to always apply.
    """
    return re.sub(r"(?m)^## ", "### ", text)


def _strip_llm_preamble(text):
    """Drop chatty commentary the model sometimes prepends before the first
    section header (e.g. "Looking at the articles provided, I found...").
    A no-op when the text has no headers at all, or already starts with one.
    """
    if "### " in text and not text.strip().startswith("### "):
        idx = text.index("### ")
        return text[idx:]
    return text


# Minimal user instruction for the headline call: names the task (so it can't
# be mistaken for a summarization request) and pins the output language, which
# otherwise only lived in the general user_prompt we deliberately omit there.
HEADLINE_USER_INSTRUCTION = (
    "Extract the opening headlines from this transcript chunk, written in English."
)


def generate_chunked_summary_beta(
    transcript_text,
    user_prompt,
    first_chunk_system_prompt,
    followup_chunk_system_prompt,
    headline_system_prompt,
    model,
    chunk_separator="\n\n",
    max_chunk_size=3000,
    sleep_time=5,
    ongoing_topics_section="",
    ongoing_topic_names=None,
):
    # Chunking: identical to summarize.generate_chunked_summary
    paragraphs = transcript_text.split(chunk_separator)
    chunks = []
    current_chunk = []
    for para in paragraphs:
        current_chunk.append(para)
        if _count_tokens(chunk_separator.join(current_chunk)) > max_chunk_size:
            chunks.append(chunk_separator.join(current_chunk[:-1]))
            current_chunk = [para]
    if current_chunk:
        chunks.append(chunk_separator.join(current_chunk))

    first_chunk_system_prompt = first_chunk_system_prompt.replace(
        "[ONGOING_TOPIC_SECTIONS]\n", ongoing_topics_section)
    followup_chunk_system_prompt = followup_chunk_system_prompt.replace(
        "[ONGOING_TOPIC_SECTIONS]\n", ongoing_topics_section)

    all_summaries = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    for i, chunk in enumerate(chunks):
        is_first = (i == 0)
        if is_first:
            print(f"\n⏳ [beta] Summarizing headlines... ({_count_tokens(chunk)} tokens)")
            # Do NOT prefix the chunk with user_prompt: its "Summarize the
            # following Greek news transcript in English." contradicts
            # headline_system_prompt ("Output only the headlines... Begin with
            # `### Top stories`"), and claude-sonnet-5 follows the user message
            # over the system message — in the 2026-02-24 E2E runs that
            # returned a full sectioned summary and the Top stories section was
            # lost. But a bare chunk loses the ONLY English instruction, and
            # the 2026-09-12 run produced Greek headlines — so carry a minimal
            # headline-specific instruction instead.
            text, usage = complete(
                HEADLINE_USER_INSTRUCTION + "\n\n" + chunk,
                system_prompt=headline_system_prompt,
                model=model,
            )
            headlines = limit_headlines(text)
            if "### " not in headlines:
                headlines = "### Top stories\n" + headlines
            _add_usage(total_usage, usage)

        previous_summary = "".join(all_summaries)
        system_prompt = (first_chunk_system_prompt if is_first
                         else followup_chunk_system_prompt.replace("[PREVIOUS_SUMMARY]", previous_summary))

        if not is_first:
            overlap = " ".join(chunks[i - 1].strip().split()[-100:])
            chunk_with_overlap = overlap + " " + chunk
        else:
            chunk_with_overlap = chunk

        print(f"\n⏳ [beta] Summarizing chunk {i + 1}/{len(chunks)}... ({_count_tokens(chunk_with_overlap)} tokens)")
        summary, usage = complete(
            f"{user_prompt}\n\n{chunk_with_overlap}",
            system_prompt=system_prompt,
            model=model,
        )
        all_summaries.append(summary)
        _add_usage(total_usage, usage)

        if i < len(chunks) - 1 and sleep_time:
            time.sleep(sleep_time)

    all_summaries.insert(0, headlines)
    combined = combine_summaries(all_summaries, ongoing_topic_names=ongoing_topic_names or [])
    return combined, total_usage


# Word budget for the cleaned body (Top stories and the heading are added
# separately and contribute ~300 more words). Static budgets in the prompt
# alone were ignored across three attempts on the 2026-09-18 bulletin; the
# measured-feedback pass below is what actually lands the length.
CLEANUP_WORD_BUDGET = 1000


def cleanup_merged_summary_beta(summary_text, deduplication_prompt, model):
    final_prompt = f"{deduplication_prompt}\n\nSUMMARY:\n{summary_text}\n"
    print("[beta] Sending to claude for cleanup...")
    # NB: do not tell this call to "preserve all bullet points" — the system
    # prompt outranks the user message, and that wording made the model
    # ignore the length budget in the cleanup instructions entirely.
    system_prompt = (
        "You are the copy editor of a daily news email. Follow the cleanup "
        "instructions in the user message exactly — including the hard length "
        "budget, which requires dropping whole minor items. Keep the markdown "
        "conventions (### section headers, '- ' bullets). Output ONLY the "
        "finished summary — no preamble, no explanations, no closing remarks."
    )
    text, usage = complete(final_prompt, system_prompt=system_prompt, model=model)
    text = _restore_section_headers(text)
    text = _strip_llm_preamble(text)

    words = len(text.split())
    if words > CLEANUP_WORD_BUDGET:
        print(f"[beta] Cleaned summary is {words} words (budget {CLEANUP_WORD_BUDGET}) — running a corrective pass...")
        corrective_prompt = (
            f"This news summary is {words} words; the hard budget is "
            f"{CLEANUP_WORD_BUDGET} words. Cut it to under the budget: first "
            "drop whole minor items (ceremonial appearances, routine visits, "
            "previews, minor international items), then compress remaining "
            "minor items to one sentence. Keep the day's major stories at "
            "full detail — attributed positions, figures, quotes — and keep "
            "all markdown formatting and links exactly as they are.\n\n"
            f"SUMMARY:\n{text}\n"
        )
        text2, usage2 = complete(corrective_prompt, system_prompt=system_prompt, model=model)
        text2 = _restore_section_headers(text2)
        text2 = _strip_llm_preamble(text2)
        # Keep the corrected version only if it actually shrank sensibly:
        # a failed correction (empty, or barely changed) falls back.
        if 0 < len(text2.split()) < words:
            text = text2
        if usage and usage2:
            usage = {k: usage.get(k, 0) + usage2.get(k, 0) for k in set(usage) | set(usage2)}
        print(f"[beta] After corrective pass: {len(text.split())} words.")
    return text, usage


def link_articles_to_summary_beta(summary_text, filtered_articles, link_prompt,
                                  article_sources, model):
    if not filtered_articles:
        print("[beta] No article metadata found, skipping link injection.")
        return summary_text, None

    tag_examples = build_tag_examples(article_sources)
    prompt_with_tags = link_prompt.replace("[TAG_EXAMPLES]", tag_examples)
    tags = [s["tag"] for s in article_sources]
    tag_list = " or ".join(f"({t})" for t in dict.fromkeys(tags))
    system_msg = (
        f"You are a careful editor helping link summaries to matching newspaper articles. "
        f"Do not alter text except to add a {tag_list} link. Preserve all ### section "
        f"headers, bullet points, and markdown structure exactly as they appear in the input. "
        f"Output ONLY the modified summary — no preamble, no explanations, no closing remarks."
    )
    linking_prompt = (
        f"{prompt_with_tags}\n\nSUMMARY:\n{summary_text}\n\n"
        f"ARTICLES:\n{json.dumps(filtered_articles, ensure_ascii=False)}\n"
    )
    print("[beta] Sending to claude for article-linking...")
    text, usage = complete(linking_prompt, system_prompt=system_msg, model=model)
    text = _restore_section_headers(text)
    text = _strip_llm_preamble(text)
    return strip_hallucinated_links(text, filtered_articles), usage


def summarize_for_day_beta(day, cfg=None):
    cfg = cfg or load_beta_config()
    model = cfg["model"]
    prompts_dir = cfg["prompts_dir"]
    output_folder = get_text_folder_for_day(day)
    log_context = {"date": day.isoformat(), "output_folder": output_folder, "lang": "en-beta"}

    date_heading = apply_title_prefix(
        generate_date_heading(day, "en"), cfg.get("title_prefix", ""))

    summary_file = output_folder / cfg["summary_without_links_filename"]
    output_file = output_folder / cfg["summary_filename"]
    transcript_file = output_folder / "transcript_gr.txt"

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_text = f.read()
    with open(_prompt_path(prompts_dir, "prompt"), "r", encoding="utf-8") as f:
        prompt_text = f.read().strip().replace("[DATE]", day.strftime('%A, %d %B %Y'))
    with open(_prompt_path(prompts_dir, "link_prompt"), "r", encoding="utf-8") as f:
        link_prompt = f.read().strip()
    with open(_prompt_path(prompts_dir, "deduplication_prompt"), "r", encoding="utf-8") as f:
        deduplication_prompt = f.read().strip()
    with open(_prompt_path(prompts_dir, "first_chunk_system_prompt"), "r", encoding="utf-8") as f:
        first_chunk_system_prompt = f.read().strip()
    with open(_prompt_path(prompts_dir, "followup_chunk_system_prompt"), "r", encoding="utf-8") as f:
        followup_chunk_system_prompt = f.read().strip()
    with open(_prompt_path(prompts_dir, "headline_system_prompt"), "r", encoding="utf-8") as f:
        headline_system_prompt = f.read().strip()

    # Ongoing topics: read-only (prod owns detection/updates)
    topics_data = load_ongoing_topics()
    active_topics = topics_data.get("topics", [])
    ongoing_topics_section = build_ongoing_topics_section_entries(active_topics, lang="en")
    if ongoing_topics_section:
        ongoing_topics_section = ongoing_topics_section + "\n"
    ongoing_topic_names = [t.get("name_en", t["name_en"]) for t in active_topics]

    total_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    if os.path.exists(summary_file):
        print(f"📄 [beta] Found existing summary: {summary_file}, skipping summarization.")
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = f.read().replace(date_heading + "\n\n", "", 1)
    else:
        with timing_step("summarize_beta_generate_chunked", **log_context, summary_path=summary_file):
            summary, usage = generate_chunked_summary_beta(
                transcript_text,
                prompt_text,
                first_chunk_system_prompt,
                followup_chunk_system_prompt,
                headline_system_prompt,
                model,
                ongoing_topics_section=ongoing_topics_section,
                ongoing_topic_names=ongoing_topic_names,
            )
            _add_usage(total_usage, usage)
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(date_heading + "\n\n" + summary)
            print(f"✅ [beta] Summary saved to {summary_file}")

    article_sources = cfg.get("article_sources", [])
    filtered_articles = load_articles(day - timedelta(days=1), day + timedelta(days=1),
                                      article_sources) if article_sources else []

    top_stories, main_summary = split_summary(summary)

    with timing_step("summarize_beta_cleanup", **log_context):
        cleaned_main_summary, usage2 = cleanup_merged_summary_beta(
            main_summary, deduplication_prompt, model)
        _add_usage(total_usage, usage2)

    with timing_step("summarize_beta_link_articles", **log_context):
        linked_main_summary, usage3 = link_articles_to_summary_beta(
            cleaned_main_summary, filtered_articles, link_prompt, article_sources, model)
        _add_usage(total_usage, usage3)

    final_output = date_heading + "\n\n" + top_stories + "\n\n" + linked_main_summary
    final_output = strip_summary_marker(final_output)
    final_output = _strip_inline_emphasis(final_output)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"\n✅ [beta] Final summary with links saved to {output_file}")
    print(f"📊 [beta] Token usage: {total_usage['input_tokens']} in / {total_usage['output_tokens']} out")
    print(f"💰 [beta] Cost (from claude CLI): ${total_usage['cost_usd']:.4f} USD")
