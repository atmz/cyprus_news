# AGENTS.md

## Scope
This file applies to the entire repository unless a more specific AGENTS.md exists in a subdirectory.

## Repository overview
- `src/main.py` orchestrates the daily pipeline: download the RIK news video, extract audio, transcribe, summarize, generate cover art, and optionally post to Substack.
- `src/summarize.py` handles chunked summarization and section ordering using prompt templates in `src/prompts/`.
- `src/transcribe.py` handles speech-to-text for the downloaded audio.
- `src/post_to_substack.py` uses Playwright and a saved session to publish to Substack. Handles RTL languages (Hebrew) with ArrowLeft instead of ArrowRight after link insertion.
- `config/languages.json` defines per-language settings (sources, prompts, Substack config).
- `src/translate.py` handles translating summaries to other languages using per-language prompt files.
- `src/lang_config.py` loads and queries the language configuration.
- `src/date_heading.py` generates localized date headings for summaries in all supported languages.
- `src/article_loaders/` contains per-source article scrapers (Playwright + BeautifulSoup, or JS `page.evaluate()` for JS-rendered sites).
- `summaries/` is the default output root for generated artifacts (override with `SUMMARIES_ROOT`).
- `cyprus-news-cron` shows the production cron invocation and required environment setup.

## Supported languages
- **English (en)**: Primary language. Summary generated from RIK transcript. Articles from Cyprus Mail, In-Cyprus.
- **Greek (el)**: Translated from English. Articles from Philenews (tag Φ), Sigmalive (SL), Politis (Π).
- **Russian (ru)**: Translated from English. Articles from EvropaKipr (ЕК), Cyprus Butterfly (CB).
- **Ukrainian (uk)**: Translated from English. Uses English article sources (no Ukrainian Cyprus news sites).
- **Turkish (tr)**: Translated from English. Articles from Kıbrıs Postası (KP) plus English sources. Turkish phrasing is politically sensitive — heading explicitly says "Republic of Cyprus public broadcaster RIK" (vetted wording).
- **Hebrew (he)**: Translated from English. Uses English article sources. RTL language — requires special handling in Substack posting (ArrowLeft for cursor movement, bidi marker stripping in validation).

## Multi-language pipeline
The pipeline flow for non-English languages:
1. English summary is generated from the RIK transcript
2. English summary is translated using `src/translate.py` with a language-specific prompt (`src/prompts/translate_prompt_{lang}.txt`)
3. Localized date heading is prepended (`src/date_heading.py`)
4. Language-specific article sources are scraped via `LANG_REFRESHERS` in `main.py`
5. Article links are injected into the translated summary
6. Final summary is posted to the language-specific Substack

Each language is wrapped in try/except so a failure in one language doesn't block others.

## Adding a new language
1. Add entry to `config/languages.json` with `summary_source: "translate_from:en"`, article sources, Substack URL, and filenames.
2. Create `src/prompts/translate_prompt_{lang}.txt` with section header translations and proper noun transliterations.
3. Add localized day/month names, `_summary_reference_{lang}()`, and heading block to `src/date_heading.py`.
4. Add the translated "Top stories" header to `TOP_STORIES_MARKERS` in `src/summarize.py` and `TOP_STORIES_H3_RE` in `src/post_to_substack.py`.
5. If the language has dedicated article sources, create a loader in `src/article_loaders/` and add it to `LANG_REFRESHERS` in `main.py`.
6. For RTL languages, add the lang code to `RTL_LANGUAGES` in `src/post_to_substack.py`.

## Article loaders
All loaders follow the same pattern:
- `fetch_articles(base_url, known_urls)` → scrapes articles, returns list of `{title, abstract, datetime, url}` dicts.
- `refresh_{source}()` → loads existing JSON, fetches new articles, merges, saves.
- URLs must be stored as **absolute URLs** (not relative paths). This avoids needing base_url/urljoin at load time.
- JS-rendered sites (e.g. Cyprus Butterfly) use `page.evaluate()` instead of BeautifulSoup.
- Relative date parsing (e.g. "5 dakika önce", "Вчера в 15:47") is resolved at scrape time; off-by-a-day is acceptable.

## Models
- Summarization and translation: `gpt-4.1`
- Transcription: `gpt-4o-transcribe`
- Cover image generation: `gpt-image-1`

## Known issues / gotchas
- Hebrew (RTL) link insertion in Substack requires `ArrowLeft` to advance cursor. The `(CM)`/`(IC)` article links in Hebrew may still render imperfectly due to mixed RTL/LTR content.
- Heading links should keep the link label short and LTR-only (e.g. `[RIK](url)`) to avoid RTL rendering issues.
- Unicode bidi control characters from Substack's editor are stripped during content validation.
- All headings include disclaimer: "may contain inaccuracies and was not reviewed by a human".
- Cached summary files must be deleted to regenerate after heading/disclaimer changes.

## Conventions & design notes
- Generated daily outputs live under `summaries/YYYY-MM-DD/{media,txt}` and are referenced by helpers in `src/helpers.py`.
- Prompts are plain text files in `src/prompts/`; when editing prompts, keep formatting consistent and avoid trailing whitespace.
- Per-language translate prompts: `src/prompts/translate_prompt_{lang}.txt` (falls back to generic `translate_prompt.txt`).
- Summaries expect canonical section headings (e.g., "Top stories", "Culture") in `summarize.combine_summaries`; update tests if you change the section list.
- Avoid adding new network calls inside tests; tests are expected to run offline.

## Environment & secrets
- `SECRETS_ROOT` points to a folder containing `env.sh` and `substack_session.json` (see `cyprus-news-cron`).
- `SUMMARIES_ROOT` overrides the default summaries output directory (see `src/helpers.py`).
- OpenAI credentials must be supplied via environment variables when running summarization or image generation.

## Testing
- Unit tests live in `tests/` and use `unittest`.
- Run the suite with `python -m unittest` from the repo root.

## PR notes
- Summaries should be concise and list user-visible changes.
- Call out changes to prompts or the publishing pipeline explicitly.
