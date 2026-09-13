# Handoff summary (written 2026-08-14)

Context summary for the next agent/session working on this repo.

## Repo: `/Users/alext/cyprus_news`

**What it is:** An automated daily news pipeline. It downloads the previous evening's 8pm RIK (Cyprus state TV) news bulletin, transcribes the Greek audio, summarizes it into sectioned markdown bullet points, links bullets to matching newspaper articles from scraped sources, generates a cover image, and publishes to two Substacks via Playwright browser automation: **kyproseidiseis.substack.com** (Greek) and **cyprusnews.substack.com** (English). Other languages (ru, uk, tr, he) exist in config but are currently disabled (commit `774a4d2`).

**Where it runs:** Production is a Docker container on a NAS (`docker_compose.yaml`), hourly cron (`cyprus-news-cron`) running `src/main.py` with secrets at `/app/secrets` (env.sh, `substack_session.json`). The local checkout is for development; `summaries/2026-02-24` is a dead symlink to the NAS volume (`/Volumes/dockerdata/...`, usually not mounted). Local dev: `.venv/bin/python`, API key in `.env` (source it before running anything that touches OpenAI). There is no local prod log access — diagnose prod issues via the published posts (Substack API: `https://<pub>.substack.com/api/v1/posts/<slug>` works unauthenticated via curl) or by running components locally.

**Key source files** (all in `src/`): `main.py` (orchestrator), `transcribe.py`, `summarize.py` (chunked summarization → dedup/cleanup → article linking), `translate.py`, `ongoing_topics.py`, `post_to_substack.py` (Playwright automation), `image.py` (covers), `article_loaders/` (one scraper per news site), `config/languages.json` (per-language article sources and tags), `src/prompts/` (all LLM prompts).

## Current model setup (deliberate, recently tuned — don't "fix")

- **`gpt-5.6-luna`** for summarization, cleanup, translation, ongoing topics — chosen for cost (~90% cheaper than the old gpt-4.1). **Luna rejects any `temperature` argument other than default**; all temperature args were removed.
- **`gpt-4.1` for article linking only** (`LINK_MODEL_NAME` in `summarize.py`). An A/B test on identical inputs showed Luna injects ~40% fewer article links (2-4 vs 4-7); gpt-4.1 was deliberately kept there. If posts show sparse links again, check this first.
- **`gpt-transcribe`** for audio ($0.0045/min), **`gpt-image-1`** for covers.
- Cost-estimate constants near the bottom of `summarize.py` are informational only and were updated for Luna.

## Fragile things and known failure modes

1. **Substack editor automation breaks when Substack ships UI changes.** Most recent: they removed `aria-label="Image"` from the toolbar button (fixed in `8d877cd` by matching `title='Insert image'` alone). Prefer `title=` attributes over aria-labels; Substack's aria-labels are unstable. To debug, probe the live editor headlessly using `data/substack_session.json` as `storage_state` (opening the editor URL creates a harmless draft). This is also captured in auto-memory (`substack-ui-debugging.md`).
2. **Scrapers break silently when sites rebuild.** Cyprus Mail uses CSS-module class hashes that rotate (e.g. `_lnkTitle_cekga_5` → `_lnkTitle_1gnys_25`); fixed in `84e35cf` by prefix-matching (`class_=lambda c: c and c.startswith("_lnkTitle_")`). Symptom of a dead scraper: posts lose that source's link tags — e.g. no (CM) links — while the pipeline otherwise succeeds. In-Cyprus now redirects to en.philenews.com but works.
3. **Session expiry:** if Substack redirects to login, re-run `login_to_ss.py` and copy the session file to the NAS secrets mount.
4. **Pre-existing test failures** (not regressions, confirmed via git stash): `test_combine_summaries_merges_and_orders_sections` (fuzzy-dedup thresholds eat "Item A"/"Item B" as near-duplicates) and `test_parse_relative_time_returns_none` (philenews loader). Everything else passes: `.venv/bin/python -m pytest tests`.

## Working tree state (as of this handoff)

`main` is in sync with `origin/main`; no source changes pending. Uncommitted noise only: refreshed `data/*.json` from local scraper test runs, debug screenshots, `.DS_Store` files. **`data/substack_session.json` is untracked and must never be committed** (it's a live login session); a `.gitignore` cleanup was offered but not done. Git committer identity on this machine is unconfigured (defaults to `alext@mac.lan`).

## Quality watch items

The Luna switch is recent (Aug 2026). Greek output verified good so far. If summary/translation quality degrades, the per-call `model=` defaults make it easy to bump individual steps back to gpt-4.1. A possible improvement never implemented: pass `language="el"` hints to `gpt-transcribe` in `transcribe.py` to improve Greek accuracy.

## Beta pipeline (added 2026-09-13)

A parallel experimentation lane for testing summarizer changes without touching prod. `src/main_beta.py` (orchestrator, cron at :30 hourly) waits for prod's `transcript_gr.txt`, then `src/summarize_beta.py` re-runs the English summarize→cleanup→link path via the Claude Code CLI (`claude -p`, wrapped in `src/claude_llm.py`), and posts to a separate beta Substack configured in `config/beta.json` (which also sets model, prompts dir, and the 🧪 title prefix). Auth: `CLAUDE_CODE_OAUTH_TOKEN` in the NAS secrets `env.sh`.

Rules: everything prod-owned is read-only to beta (transcript, `cover.png`, `data/*_articles.json`, `ongoing_topics.json` — beta never runs scrapers or topic detection); beta writes only `summary_beta.txt`, `summary_without_links_beta.txt`, `flag_beta.txt`, and its own `data/cyprus_news_beta_<date>.log`. Disable it with `"enabled": false` in `config/beta.json`. `summarize_beta.py` deliberately forks `summarize.py`'s LLM path and is expected to diverge — pure helpers are imported from `summarize.py`; graduating an experiment means porting the diff into prod deliberately. Design/spec: `docs/superpowers/specs/2026-09-12-beta-pipeline-design.md`.
