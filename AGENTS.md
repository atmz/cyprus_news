# AGENTS.md

## Scope
This file applies to the entire repository unless a more specific AGENTS.md exists in a subdirectory.

## Repository overview
- `src/main.py` orchestrates the daily pipeline: download the RIK news video, extract audio, transcribe, summarize, generate cover art, and optionally post to Substack.
- `src/summarize.py` handles chunked summarization and section ordering using prompt templates in `src/prompts/`.
- `src/transcribe.py` handles speech-to-text for the downloaded audio.
- `src/post_to_substack.py` uses Playwright and a saved session to publish to Substack.
- `summaries/` is the default output root for generated artifacts (override with `SUMMARIES_ROOT`).
- `cyprus-news-cron` shows the production cron invocation and required environment setup.

## Conventions & design notes
- Generated daily outputs live under `summaries/YYYY-MM-DD/{media,txt}` and are referenced by helpers in `src/helpers.py`.
- Prompts are plain text files in `src/prompts/`; when editing prompts, keep formatting consistent and avoid trailing whitespace.
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
