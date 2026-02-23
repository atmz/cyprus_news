# Cyprus News

An automated pipeline that turns the RIK evening news broadcast into a daily newsletter — published to Substack in six languages, entirely without human intervention.

## What it does

Every evening, [RIK](https://tv.rik.cy) airs the main Cyprus news bulletin in Greek. This project:

1. Downloads the broadcast recording automatically after it airs
2. Extracts the audio and transcribes it using OpenAI's Whisper speech-to-text model
3. Summarizes the transcript into a structured digest (organized into sections like Government & Politics, Justice, Economy, etc.)
4. Scrapes English and local-language news articles to add source links to each story
5. Generates an AI cover image based on the day's top stories
6. Posts the finished newsletter to Substack — in up to six languages

The whole process runs on a cron schedule and produces a published post without any manual steps.

## Languages

| Language | Substack | Method |
|----------|----------|--------|
| English | [cyprusnews.substack.com](https://cyprusnews.substack.com) | Summarized from transcript |
| Greek | [kyproseidiseis.substack.com](https://kyproseidiseis.substack.com) | Summarized natively from transcript |
| Russian | [kiprnovosti.substack.com](https://kiprnovosti.substack.com) | Translated from English |
| Ukrainian | [kiprnovyny.substack.com](https://kiprnovyny.substack.com) | Translated from English |
| Turkish | [rikhaberleri.substack.com](https://rikhaberleri.substack.com) | Translated from English |
| Hebrew | [kiprnews.substack.com](https://kiprnews.substack.com) | Translated from English |

## Pipeline overview

```
RIK broadcast (MP4)
        │
        ▼
  Audio extraction (ffmpeg)
        │
        ▼
  Transcription (Whisper / gpt-4o-transcribe)
        │
        ▼
  Summarization (GPT-4.1)          ◄── Article scraping (Cyprus Mail, In-Cyprus,
        │                               Philenews, Sigmalive, Politis,
        │                               EvropaKipr, Kıbrıs Postası, ...)
        ▼
  Article linking (GPT-4.1)
        │
        ├──► Greek: native summarization from transcript
        │
        ├──► Russian / Ukrainian / Turkish / Hebrew: translation (GPT-4.1)
        │
        ▼
  Cover image generation (gpt-image-1)
        │
        ▼
  Substack publishing (Playwright)
```

## Project structure

```
src/
  main.py                  — Orchestrates the daily pipeline
  summarize.py             — Chunked summarization and article linking
  transcribe.py            — Speech-to-text
  translate.py             — Summary translation for non-English editions
  post_to_substack.py      — Publishes the Cyprus News newsletter (with cover image)
  post_markdown.py         — General-purpose: post any markdown file to Substack
  image.py                 — Cover image generation
  date_heading.py          — Localized date headings for each language
  lang_config.py           — Loads and queries config/languages.json
  article_loaders/         — Per-source article scrapers
  prompts/                 — GPT prompt templates (one set per language)

config/
  languages.json           — Per-language settings (sources, Substack URLs, filenames)

data/                      — Saved Substack sessions and scraped article caches
summaries/                 — Generated daily outputs (YYYY-MM-DD/txt/, YYYY-MM-DD/media/)
docs/                      — Subscriber-facing about pages
tests/                     — Unit tests (run with: python -m unittest)
```

## Running it

```bash
# Generate and publish yesterday's summary (all languages)
python src/main.py

# Generate a specific date
python src/main.py 2026-02-20

# Save as draft instead of publishing
python src/main.py --draft

# Generate summaries only, skip posting
python src/main.py --no-post

# Run one language only
python src/main.py --lang el
```

## Posting arbitrary markdown to Substack

`src/post_markdown.py` is a standalone utility for posting any markdown file to Substack — not just Cyprus News summaries. It handles headings, bullet points, and inline links. No cover image.

```bash
python src/post_markdown.py my_post.md \
    --substack-url "https://yourpub.substack.com/publish/post?type=newsletter" \
    [--session ./data/substack_session.json] \
    [--publish]
```

## Environment and secrets

```bash
SECRETS_ROOT   # folder containing substack_session.json files (default: ./data)
SUMMARIES_ROOT # output root for generated artifacts (default: ./summaries)
OPENAI_API_KEY # required for summarization, translation, and image generation
```

The Substack session file is obtained by logging into Substack in a browser and saving the session state via Playwright. See `data/substack_session.json`.

## Dependencies

- Python 3.11+
- [Playwright](https://playwright.dev/python/) (browser automation for Substack posting and article scraping)
- [OpenAI Python SDK](https://github.com/openai/openai-python) (GPT-4.1, Whisper, gpt-image-1)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) (HTML parsing in article loaders)
- ffmpeg (audio extraction from video)

```bash
pip install -r requirements.txt
playwright install chromium
```
