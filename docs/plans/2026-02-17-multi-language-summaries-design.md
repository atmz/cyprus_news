# Multi-Language Summaries Design

## Goal

Extend the Cyprus news pipeline to produce Greek-language summaries (and be easily extensible to other languages), reusing the existing English summarization to save tokens.

## Approach

**Translate the English summary** rather than re-summarizing from transcript. This:
- Preserves the battle-tested English pipeline unchanged
- Is cheap (translation is a simple LLM task)
- Produces good Greek since the model handles EN->GR well

## Language Configuration

New file `config/languages.json` defines per-language settings:

- `summary_source: "transcript"` — primary language, summarizes from transcript (English)
- `summary_source: "translate_from:en"` — derives summary by translating another language's output
- `article_sources` — per-language list of news sources for link injection (empty for Greek initially, structure ready for Greek sites later)
- `substack_url` / `substack_session_file` — per-language Substack publishing config
- English: `cyprusnews.substack.com`
- Greek: `kyproseidiseis.substack.com` (same account, same session file)

## Pipeline Flow

1. Video download, audio extraction, transcription — unchanged
2. English summarization — unchanged, runs first
3. For each additional language (translate_from):
   - Read source language's summary_without_links file
   - Translate via single LLM call using `src/prompts/translate_prompt.txt`
   - Save translated summary_without_links file
   - Run link-injection with that language's article_sources (skip if empty)
   - Save final summary file
4. Cover art generation — unchanged, reuse same cover for all languages
5. Posting — iterate over enabled languages, post each to its configured Substack

## New Files

- `config/languages.json` — language configuration
- `src/prompts/translate_prompt.txt` — translation prompt
- `src/translate.py` — translation module

## Modified Files

- `src/main.py` — loop over languages for translate + post steps
- `src/summarize.py` — extract ARTICLE_SOURCES from config instead of hardcoded
- `src/post_to_substack.py` — accept Substack URL and session file as parameters

## Key Decisions

- Greek date heading localized (Greek day/month names, "Perilepsi Eidiseon" etc.)
- Same cover image reused across languages
- Same Substack session file for both publications (same account)
- Empty article_sources = skip link injection step
