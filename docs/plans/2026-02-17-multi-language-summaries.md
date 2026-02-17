# Multi-Language Summaries Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Greek-language summary generation by translating the English summary, with a config-driven language system extensible to future languages.

**Architecture:** A `config/languages.json` file defines per-language settings (source, article sources, Substack config). English runs first as today. Additional languages translate the English summary, optionally inject links from language-specific sources, and post to their own Substack. The existing English pipeline is unchanged.

**Tech Stack:** Python, OpenAI API (gpt-4o), Playwright, unittest

---

### Task 1: Add language config file and loader

**Files:**
- Create: `config/languages.json`
- Create: `src/lang_config.py`
- Test: `tests/test_lang_config.py`

**Step 1: Create `config/languages.json`**

```json
{
  "en": {
    "enabled": true,
    "summary_source": "transcript",
    "prompts_dir": "src/prompts",
    "article_sources": [
      {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
      {"name": "Cyprus Mail", "tag": "CM", "file": "data/cm_crime_articles.json"},
      {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
      {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_economy_articles.json"}
    ],
    "summary_filename": "summary.txt",
    "summary_without_links_filename": "summary_without_links.txt",
    "substack_url": "https://cyprusnews.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome",
    "substack_session_file": "substack_session.json",
    "flag_filename": "flag.txt"
  },
  "el": {
    "enabled": true,
    "summary_source": "translate_from:en",
    "article_sources": [],
    "summary_filename": "summary_el.txt",
    "summary_without_links_filename": "summary_without_links_el.txt",
    "substack_url": "https://kyproseidiseis.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome",
    "substack_session_file": "substack_session.json",
    "flag_filename": "flag_el.txt"
  }
}
```

**Step 2: Write the failing test for the config loader**

```python
# tests/test_lang_config.py
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lang_config import load_language_config

class LangConfigTestCase(unittest.TestCase):
    def test_load_returns_all_languages(self):
        config = load_language_config()
        self.assertIn("en", config)
        self.assertIn("el", config)

    def test_english_is_transcript_source(self):
        config = load_language_config()
        self.assertEqual(config["en"]["summary_source"], "transcript")

    def test_greek_translates_from_english(self):
        config = load_language_config()
        self.assertEqual(config["el"]["summary_source"], "translate_from:en")

    def test_each_language_has_required_keys(self):
        config = load_language_config()
        required = ["enabled", "summary_source", "summary_filename",
                     "summary_without_links_filename", "substack_url",
                     "substack_session_file", "flag_filename"]
        for lang, lc in config.items():
            for key in required:
                self.assertIn(key, lc, f"{lang} missing key {key}")

if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/test_lang_config.py -v`
Expected: FAIL (module not found)

**Step 4: Write `src/lang_config.py`**

```python
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "languages.json"

def load_language_config(config_path=None):
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_enabled_languages(config=None):
    if config is None:
        config = load_language_config()
    return {k: v for k, v in config.items() if v.get("enabled", False)}

def get_translation_languages(config=None):
    """Return languages that derive from translating another language."""
    enabled = get_enabled_languages(config)
    return {k: v for k, v in enabled.items()
            if v["summary_source"].startswith("translate_from:")}

def get_source_language(lang_config):
    """Parse 'translate_from:en' -> 'en'."""
    return lang_config["summary_source"].split(":", 1)[1]
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/test_lang_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add config/languages.json src/lang_config.py tests/test_lang_config.py
git commit -m "feat: add language config file and loader"
```

---

### Task 2: Add translation module and prompt

**Files:**
- Create: `src/prompts/translate_prompt.txt`
- Create: `src/translate.py`
- Test: `tests/test_translate.py`

**Step 1: Create `src/prompts/translate_prompt.txt`**

```
Translate the following English news summary into Greek.

Rules:
- Preserve the Markdown formatting exactly: section headers (###), bullet points (-), and links.
- Keep proper nouns (names of people, organizations, places) as they appear — do not transliterate English proper nouns into Greek unless they have a well-known Greek form.
- Translate section headers into Greek:
  - "Top stories" -> "Κύριες Ειδήσεις"
  - "Government & Politics" -> "Κυβέρνηση & Πολιτική"
  - "Cyprus Problem" -> "Κυπριακό"
  - "Crime & Justice" -> "Έγκλημα & Δικαιοσύνη"
  - "Foreign Affairs" -> "Εξωτερικές Υποθέσεις"
  - "Public Health & Safety" -> "Δημόσια Υγεία & Ασφάλεια"
  - "Energy & Infrastructure" -> "Ενέργεια & Υποδομές"
  - "Education" -> "Εκπαίδευση"
  - "Culture" -> "Πολιτισμός"
- Output only the translated text, no commentary.
```

**Step 2: Write `src/translate.py`**

```python
from pathlib import Path
from openai import OpenAI
from timing import timing_step

TRANSLATE_PROMPT_FILE = Path(__file__).parent / "prompts" / "translate_prompt.txt"

def load_translate_prompt():
    with open(TRANSLATE_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def translate_summary(client, english_summary, target_lang="el", model="gpt-4o"):
    """Translate an English summary to the target language."""
    prompt = load_translate_prompt()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": english_summary}
        ],
        temperature=0.2
    )

    translated = response.choices[0].message.content.strip()
    usage = response.usage
    return translated, usage
```

**Step 3: Write test**

```python
# tests/test_translate.py
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from translate import load_translate_prompt

class TranslateTestCase(unittest.TestCase):
    def test_translate_prompt_loads(self):
        prompt = load_translate_prompt()
        self.assertIn("Greek", prompt)
        self.assertIn("Markdown", prompt)

    def test_translate_prompt_contains_section_mappings(self):
        prompt = load_translate_prompt()
        self.assertIn("Κύριες Ειδήσεις", prompt)
        self.assertIn("Κυπριακό", prompt)

if __name__ == "__main__":
    unittest.main()
```

**Step 4: Run tests**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/test_translate.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/prompts/translate_prompt.txt src/translate.py tests/test_translate.py
git commit -m "feat: add translation module and prompt for Greek summaries"
```

---

### Task 3: Add Greek date heading generation

**Files:**
- Create: `src/date_heading.py`
- Test: `tests/test_date_heading.py`
- Modify: `src/summarize.py:299-316` (extract existing heading logic)

**Step 1: Write the failing test**

```python
# tests/test_date_heading.py
import sys
from pathlib import Path
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from date_heading import generate_date_heading

class DateHeadingTestCase(unittest.TestCase):
    def test_english_heading(self):
        heading = generate_date_heading(date(2026, 2, 17), "en")
        self.assertIn("News Summary", heading)
        self.assertIn("Tuesday", heading)
        self.assertIn("17 February 2026", heading)

    def test_greek_heading(self):
        heading = generate_date_heading(date(2026, 2, 17), "el")
        self.assertIn("Περίληψη Ειδήσεων", heading)
        self.assertIn("Τρίτη", heading)
        self.assertIn("Φεβρουαρίου", heading)

    def test_english_heading_contains_rik_link(self):
        heading = generate_date_heading(date(2026, 2, 17), "en")
        self.assertIn("tv.rik.cy", heading)

    def test_greek_heading_contains_rik_link(self):
        heading = generate_date_heading(date(2026, 2, 17), "el")
        self.assertIn("tv.rik.cy", heading)

if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/test_date_heading.py -v`
Expected: FAIL

**Step 3: Write `src/date_heading.py`**

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

GREEK_DAYS = {
    0: "Δευτέρα", 1: "Τρίτη", 2: "Τετάρτη", 3: "Πέμπτη",
    4: "Παρασκευή", 5: "Σάββατο", 6: "Κυριακή"
}
GREEK_MONTHS = {
    1: "Ιανουαρίου", 2: "Φεβρουαρίου", 3: "Μαρτίου", 4: "Απριλίου",
    5: "Μαΐου", 6: "Ιουνίου", 7: "Ιουλίου", 8: "Αυγούστου",
    9: "Σεπτεμβρίου", 10: "Οκτωβρίου", 11: "Νοεμβρίου", 12: "Δεκεμβρίου"
}

def _summary_reference(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "this evening's"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "this evening's"
    return "yesterday's"

def _summary_reference_el(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "το απογευματινό"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "το απογευματινό"
    return "το χθεσινό"

def generate_date_heading(day, lang="en"):
    if lang == "el":
        day_name = GREEK_DAYS[day.weekday()]
        month_name = GREEK_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Περίληψη Ειδήσεων για {date_str}\n\n"
        ref = _summary_reference_el(day)
        heading += (
            f"Αυτή είναι μια περίληψη {ref} "
            f"[δελτίο ειδήσεων στις 8μμ του ΡΙΚ](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Όπου είναι διαθέσιμοι, παρέχονται σύνδεσμοι σε σχετικά ελληνόγλωσσα άρθρα. "
            f"Σημειώστε ότι αυτή η περίληψη δημιουργήθηκε με τη βοήθεια AI και μπορεί να περιέχει ανακρίβειες."
        )
        return heading

    # English (default / current behavior)
    date_str = day.strftime('%A, %d %B %Y')
    heading = f"## 📰 News Summary for {date_str}\n\n"
    ref = _summary_reference(day)
    heading += (
        f"This is a summary of {ref} "
        f"[8pm RIK news broadcast](https://tv.rik.cy/show/eideseis-ton-8/). "
        f"Where available, links to related English-language articles from the Cyprus Mail "
        f"and In-Cyprus are provided for further reading. Please note that this summary was "
        f"generated with the assistance of AI and may contain inaccuracies."
    )
    return heading
```

**Step 4: Run tests**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/test_date_heading.py -v`
Expected: PASS

**Step 5: Update `src/summarize.py` to use `generate_date_heading`**

In `summarize_for_day`, replace the inline date heading construction (lines 308-316) with:
```python
from date_heading import generate_date_heading
# ...
date_heading = generate_date_heading(day, "en")
```

**Step 6: Run existing tests to verify no regression**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/date_heading.py tests/test_date_heading.py src/summarize.py
git commit -m "refactor: extract date heading generation, add Greek locale"
```

---

### Task 4: Wire ARTICLE_SOURCES from config in summarize.py

**Files:**
- Modify: `src/summarize.py:22-27` (replace hardcoded ARTICLE_SOURCES)

**Step 1: Modify `src/summarize.py`**

Replace the hardcoded `ARTICLE_SOURCES` list at the top of `summarize.py` with a function that loads from config:

```python
from lang_config import load_language_config

def get_article_sources(lang="en"):
    config = load_language_config()
    if lang in config:
        return config[lang].get("article_sources", [])
    return []
```

Update `load_articles` (line 200) to accept sources as a parameter instead of using the global:

```python
def load_articles(start_date, end_date, article_sources=None):
    if article_sources is None:
        article_sources = get_article_sources("en")
    results = []
    for source in article_sources:
        # ... rest unchanged
```

Update `summarize_for_day` call to `load_articles` (line 367):
```python
filtered_articles = load_articles(start_date, end_date, get_article_sources("en"))
```

**Step 2: Run existing tests**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/summarize.py
git commit -m "refactor: load article sources from language config"
```

---

### Task 5: Make post_to_substack configurable

**Files:**
- Modify: `src/post_to_substack.py:13-14` (accept URL and session as params)

**Step 1: Update `post_to_substack` function signature**

Change the function to accept optional `substack_url` and `session_file` parameters, falling back to current defaults:

```python
def post_to_substack(md_path, publish=False, cover_path="cover.png",
                     substack_url=None, session_file=None):
    # Use defaults if not provided
    actual_url = substack_url or SUBSTACK_NEW_POST_URL
    actual_session = Path(session_file) if session_file else SESSION_FILE
```

Then use `actual_url` instead of `SUBSTACK_NEW_POST_URL` (line 263) and `actual_session` instead of `SESSION_FILE` (lines 255-258).

**Step 2: Run existing tests (ensure nothing breaks)**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/post_to_substack.py
git commit -m "refactor: make substack URL and session file configurable"
```

---

### Task 6: Wire multi-language pipeline into main.py

**Files:**
- Modify: `src/main.py`

**Step 1: Update main.py**

After the existing `generate_for_date(day)` and English posting, add a loop for translation languages:

```python
from lang_config import load_language_config, get_translation_languages, get_source_language
from translate import translate_summary
from date_heading import generate_date_heading
from summarize import load_articles, link_articles_to_summary, cleanup_merged_summary, split_summary, strip_summary_marker

# ... in main(), after English posting ...

config = load_language_config()
translation_langs = get_translation_languages(config)

for lang, lang_config in translation_langs.items():
    source_lang = get_source_language(lang_config)
    source_summary_file = txt / config[source_lang]["summary_without_links_filename"]

    if not source_summary_file.exists():
        print(f"⚠️ Source summary for {source_lang} not found, skipping {lang}")
        continue

    target_summary_file = txt / lang_config["summary_without_links_filename"]
    target_output_file = txt / lang_config["summary_filename"]
    target_flag_file = txt / lang_config["flag_filename"]

    if target_output_file.exists():
        print(f"{target_output_file} exists — skipping {lang} translation.")
    else:
        # Read source summary (without the date heading)
        source_text = source_summary_file.read_text(encoding="utf-8")
        # Strip the English date heading (everything before first ###)
        import re
        body_match = re.search(r'(### .+)', source_text, re.DOTALL)
        source_body = body_match.group(1) if body_match else source_text

        print(f"Translating summary to {lang}...")
        client = OpenAI()
        with timing_step("translate_summary", date=day.isoformat(), lang=lang):
            translated, usage = translate_summary(client, source_body, target_lang=lang)

        # Generate localized date heading
        date_heading = generate_date_heading(day, lang)

        # Save translated summary without links
        target_summary_file.write_text(
            date_heading + "\n\n" + translated, encoding="utf-8"
        )
        print(f"✅ Translated summary saved to {target_summary_file}")

        # Link injection (if article sources configured)
        article_sources = lang_config.get("article_sources", [])
        if article_sources:
            start_date = day - timedelta(days=1)
            end_date = day + timedelta(days=1)
            filtered_articles = load_articles(start_date, end_date, article_sources)
            top_stories, main_summary = split_summary(translated)
            linked, _ = link_articles_to_summary(client, main_summary, filtered_articles, link_prompt)
            final = date_heading + "\n\n" + top_stories + "\n\n" + linked
        else:
            final = date_heading + "\n\n" + translated

        final = strip_summary_marker(final)
        target_output_file.write_text(final, encoding="utf-8")
        print(f"✅ Final {lang} summary saved to {target_output_file}")

    # Post to Substack for this language
    if not target_output_file.exists():
        continue
    substack_url = lang_config["substack_url"]
    session_path = SECRETS_ROOT / lang_config["substack_session_file"]
    post_flag = False if args.draft else True

    if not target_flag_file.exists():
        with timing_step("post_to_substack", date=day.isoformat(), lang=lang):
            if post_to_substack(target_output_file, post_flag,
                                cover_path=cover_path,
                                substack_url=substack_url,
                                session_file=str(session_path)):
                target_flag_file.touch()
```

**Step 2: Run full test suite**

Run: `cd /Users/alext/cyprus_news && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Manual smoke test (dry run)**

Run: `cd /Users/alext/cyprus_news && python src/main.py --draft 2026-02-16`
Verify: Greek summary file created in `summaries/2026-02-16/txt/summary_el.txt`

**Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: wire multi-language translation pipeline into main"
```

---

### Task 7: Update Dockerfile to include config directory

**Files:**
- Modify: `Dockerfile:10`

**Step 1: Add config COPY**

After `COPY src/ src/` add:
```dockerfile
COPY config/ config/
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "chore: copy config directory into Docker image"
```

---

### Task 8: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

**Step 1: Add multi-language notes**

Add to the "Repository overview" section:
```
- `config/languages.json` defines per-language settings (sources, prompts, Substack config).
- `src/translate.py` handles translating summaries to other languages.
- `src/lang_config.py` loads and queries the language configuration.
- `src/date_heading.py` generates localized date headings for summaries.
```

Add to "Conventions & design notes":
```
- To add a new language: add an entry to `config/languages.json` with `summary_source: "translate_from:en"` and the relevant Substack config.
```

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md with multi-language pipeline info"
```
