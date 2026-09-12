# Beta pipeline design

**Date:** 2026-09-12
**Status:** Approved design, pending implementation plan

## Purpose

Add a "beta" lane to the daily Cyprus news pipeline so summarizer changes
(prompts, models, logic) can be tested in production conditions without
touching the production lane. Beta runs in the same container, on the same
git SHA, reuses production's cached transcript, and publishes a complete
English post to a separate beta Substack publication every day. The first
experiment: replace the OpenAI API with the Claude Code CLI (`claude -p`)
as the LLM backend.

## Non-goals

- No Greek/translation beta lanes (English only).
- No beta cover image or ongoing-topic restructuring — beta reuses prod's
  cover and reads ongoing topics without writing them.
- No changes to production source files (`main.py`, `summarize.py`,
  `lang_config.py`, `languages.json`, `post_to_substack.py` all untouched).
- No shared abstraction between prod and beta summarizers. Beta forks the
  code; divergence is the point. Graduating an experiment means porting the
  diff into `summarize.py` deliberately, in a separate task.

## Architecture

Two independent lanes in one container, offset cron schedules:

```
:00  main.py       download → transcribe → summarize (OpenAI) → cover → post to prod Substacks
:30  main_beta.py  [wait for transcript] → summarize (claude -p) → post to beta Substack
```

Beta is a separate process. A beta crash, hang, or broken `claude` install
cannot affect production. Both lanes are idempotent via output-file
existence checks and retried by the hourly cron.

### New files

**`src/main_beta.py`** — beta orchestrator (~100 lines). CLI mirrors
`main.py`: optional `date` (YYYY-MM-DD, defaults to yesterday), `--draft`,
`--no-post`. Flow:

1. Load `config/beta.json`; exit 0 if `enabled` is false.
2. Resolve day: given date, else yesterday (Europe/Nicosia), and exit
   quietly before 06:00 local, same rule as prod.
3. If `summaries/<day>/text/transcript_gr.txt` does not exist, exit 0 with
   a "waiting for prod transcript" message.
4. If `summary_beta.txt` does not exist, call
   `summarize_beta.summarize_for_day_beta(day)`.
5. Unless `--no-post`: if `summary_beta.txt` exists and `flag_beta.txt`
   does not, call the existing `post_to_substack()` with beta's
   `substack_url`, the shared session file, prod's `cover.png`, and
   `lang="en"`. Touch `flag_beta.txt` only on success.

**`src/summarize_beta.py`** — beta summarizer. Initially a fork of
`summarize.py`'s English path: chunked summarization → merge/dedup cleanup
→ article linking, with all LLM calls routed through `claude_llm.complete()`
using the model from `beta.json`. Differences from prod:

- Reads prompt files from `beta.json`'s `prompts_dir` (initially
  `src/prompts`, later a `src/prompts_beta/` copy for prompt experiments).
- Writes `summary_without_links_beta.txt` and `summary_beta.txt`.
- Prepends `title_prefix` (default "🧪 ") to the post's H1 so beta emails
  are unmistakable.
- Reads `ongoing_topics.json` for prompt injection but never writes it.
- Loads articles from the same `data/*_articles.json` files prod refreshes;
  beta never runs scrapers.

This file is expected to diverge from `summarize.py` over time.

**`src/claude_llm.py`** — the `claude -p` backend, one public function:

```python
def complete(prompt, system_prompt=None, model="claude-sonnet-5", timeout=600) -> (text, usage)
```

- Invokes `claude -p --model <model> --output-format json` with the prompt
  on stdin and tools disabled, from a neutral working directory (so no
  CLAUDE.md or project skills leak into generations).
- System prompt passed via the CLI's system-prompt flag; if the installed
  CLI version lacks it, prepend the system text to the prompt.
- Parses the JSON envelope: returns result text plus usage/cost info.
- Raises on nonzero exit, `is_error: true`, malformed JSON, or timeout.
  One retry, then propagate — the next cron hour retries the whole run.
- Auth via `CLAUDE_CODE_OAUTH_TOKEN` env var (long-lived token from
  `claude setup-token`, stored in the NAS secrets `env.sh`); uses the
  operator's Claude subscription, not API billing.

### Modified files

**`Dockerfile`** — install Node 20 (NodeSource) and
`npm install -g @anthropic-ai/claude-code`.

**`cyprus-news-cron`** — add:

```
30 * * * *  cd /app && export SECRETS_ROOT=/app/secrets && . /app/secrets/env.sh && xvfb-run -a python /app/src/main_beta.py >> /app/data/cyprus_news_beta_$(date +\%Y-\%m-\%d).log 2>&1
```

(`xvfb-run` mirrors prod: beta posts through the same Playwright
automation.)

### New config: `config/beta.json`

```json
{
  "enabled": true,
  "model": "claude-sonnet-5",
  "prompts_dir": "src/prompts",
  "title_prefix": "🧪 ",
  "article_sources": [ /* copy of languages.json "en" article_sources */ ],
  "summary_filename": "summary_beta.txt",
  "summary_without_links_filename": "summary_without_links_beta.txt",
  "flag_filename": "flag_beta.txt",
  "substack_url": "https://<beta-pub>.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome",
  "substack_session_file": "substack_session.json"
}
```

Read only by `main_beta.py`/`summarize_beta.py`. `lang_config.py` and
`languages.json` never see it. The beta publication lives under the same
Substack account, so the existing shared `substack_session.json` publishes
to it without a new login.

## Shared-state rules

Beta treats all prod-owned state as read-only: the transcript, `cover.png`,
`data/*_articles.json`, `ongoing_topics.json`. Beta writes exactly three
files per day (`summary_without_links_beta.txt`, `summary_beta.txt`,
`flag_beta.txt`) plus its own log.

## Error handling

- `claude -p`: returncode + `is_error` check, 10-minute per-call timeout,
  one retry, then fail the run; hourly cron provides the outer retry loop.
- Posting reuses `post_to_substack` unchanged, including its
  clicked-but-unconfirmed-publish handling; the flag file is the only
  success marker.
- Missing/expired `CLAUDE_CODE_OAUTH_TOKEN` fails loudly in the beta log;
  prod is unaffected.

## Testing

- Unit tests, subprocess mocked, for `claude_llm.complete`: happy path,
  `is_error` envelope, nonzero exit, malformed JSON, timeout, retry.
- Unit test: `main_beta.py` exits cleanly when the transcript is absent,
  and when `enabled` is false.
- Local end-to-end before deploy: run `main_beta.py` for a past date with
  an existing transcript, first `--no-post`, then `--draft` against the
  real beta publication.
- Existing pytest suite stays green (no prod source changes). The two
  pre-existing failures documented in HANDOFF.md remain out of scope.

## One-time operator setup

1. Create the beta publication on Substack under the same account; put its
   publish URL in `beta.json`.
2. `claude setup-token` on the dev Mac; add
   `export CLAUDE_CODE_OAUTH_TOKEN=...` to the NAS `secrets/env.sh`.
3. Rebuild and redeploy the container.
