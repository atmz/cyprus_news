# Ongoing Topics: Persistent Top-Level Sections for Major Stories

## Problem

The LLM sometimes creates ad-hoc section headers (e.g. "Animal Disease Outbreak", "Health & Social Welfare") that fall outside the canonical section list. Major ongoing stories like the Iran-Israel conflict or foot-and-mouth epidemic get scattered across multiple canonical sections or create inconsistent headers day-to-day.

## Solution

A persistent `data/ongoing_topics.json` file that tracks major ongoing stories. These become dedicated `###` sections placed after Top Stories and before canonical sections. Topics are auto-detected via LLM after summarization, persist for 7 days without appearing, and are injected into prompts on subsequent days so the model creates them natively.

## Data Structure

`data/ongoing_topics.json` (human-editable):

```json
{
  "topics": [
    {
      "name_en": "Iran-Israel Conflict",
      "name_el": "Σύγκρουση Ιράν-Ισραήλ",
      "description": "Regional military conflict involving Iran, Israel, and impacts on Cyprus",
      "first_seen": "2026-02-28",
      "last_seen": "2026-03-01"
    }
  ],
  "config": {
    "expiry_days": 7
  }
}
```

- Names in each language for proper headers in all editions
- `description` helps the LLM classify bullets
- Topic order in file = display order in summary
- Topics with `(today - last_seen) > expiry_days` are removed automatically

## Pipeline Integration

After English summarization:

1. **Detect** - LLM call with today's summary + existing topics. Returns new topics + confirms which existing topics appeared today.
2. **Update** `ongoing_topics.json` - add new topics, bump `last_seen` for confirmed ones, expire stale topics.
3. **Restructure** (only if topics changed) - move matching bullets from canonical sections into topic sections. Skip topics with no matching bullets (no empty sections).
4. Continue with dedup, link injection, etc.

For Greek: topics (with `name_el`) injected into the Greek system prompt so the model creates them natively. Translated languages inherit topic sections from the English source.

## Prompt Injection

On days with active topics, dynamically append to system prompts:

```
ONGOING MAJOR STORIES:
The following are major ongoing stories. If today's news contains information
about any of these topics, create a dedicated ### section for it (using the
exact name provided) and place all related bullets there instead of in the
regular sections. Place these sections immediately after ### Top stories.

- Iran-Israel Conflict: Regional military conflict involving Iran, Israel, and impacts on Cyprus

If a topic has no news today, do not create a section for it.
```

## Detection Prompt

Small LLM call after summarization:

```
Given today's news summary, identify any major ongoing stories that:
1. Span multiple regular sections
2. Are significant enough to warrant their own dedicated section
3. Are likely to continue in the news for multiple days

Current ongoing topics (confirm if still active):
[list from ongoing_topics.json]

Return JSON with detected topics.
```

## Key Behaviors

- Detection runs once on English summary; results apply to all languages
- Restructuring skipped if no topic changes detected
- Empty topic sections never rendered
- Topics expire after 7 days without appearing
- File is human-editable for manual add/remove/reorder
