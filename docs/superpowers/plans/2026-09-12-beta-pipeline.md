# Beta Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parallel "beta" pipeline lane that re-summarizes the day's cached transcript via `claude -p` and publishes to a separate beta Substack, without touching production code.

**Architecture:** Three new modules — `claude_llm.py` (subprocess wrapper around `claude -p`), `summarize_beta.py` (fork of the English summarize path using Claude), `main_beta.py` (orchestrator) — driven by a new `config/beta.json`, plus a second cron line and Node/claude-code in the Docker image. Beta reads prod's outputs (transcript, cover, article JSONs, ongoing topics) and writes only `*_beta` files.

**Tech Stack:** Python 3 (repo `.venv`), Claude Code CLI (`claude -p`, verified v2.1.269), unittest via pytest, Docker (Playwright jammy base + Node 20).

**Spec:** `docs/superpowers/specs/2026-09-12-beta-pipeline-design.md`

## Global Constraints

- NEVER modify prod source: `src/main.py`, `src/summarize.py`, `src/lang_config.py`, `src/post_to_substack.py`, `config/languages.json`, `src/prompts/*`.
- Beta writes exactly three per-day files: `summary_without_links_beta.txt`, `summary_beta.txt`, `flag_beta.txt`. Everything prod-owned is read-only (transcript, `cover.png`, `data/*_articles.json`, `ongoing_topics.json`).
- Importing pure helpers from `summarize.py` (`combine_summaries`, `limit_headlines`, `load_articles`, `split_summary`, `strip_summary_marker`, `build_tag_examples`) is allowed and preferred (read-only reuse). Fork a helper into `summarize_beta.py` only when an experiment needs to change it.
- Run tests with: `.venv/bin/python -m pytest tests -v`. Two failures are pre-existing and out of scope: `test_combine_summaries_merges_and_orders_sections`, `test_parse_relative_time_returns_none`. Everything else must pass.
- Test files follow the repo pattern: `unittest.TestCase`, with `ROOT = Path(__file__).resolve().parents[1]; sys.path.append(str(ROOT / "src"))` at the top.
- `data/substack_session.json` must never be committed.
- Every commit message ends with:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011xHXpD41ZX6yAfmFCMEvZM
  ```
- Verified `claude -p` envelope (v2.1.269): top-level JSON object with `result` (string), `is_error` (bool), `total_cost_usd` (float), `usage.input_tokens` / `usage.output_tokens` (ints). `--tools ""` disables all tools; `--system-prompt <text>` sets the system prompt.

---

### Task 1: `claude_llm.py` — the `claude -p` backend

**Files:**
- Create: `src/claude_llm.py`
- Test: `tests/test_claude_llm.py`

**Interfaces:**
- Consumes: nothing from this repo.
- Produces: `complete(prompt: str, system_prompt: str | None = None, model: str = "claude-sonnet-5", timeout: int = 600, retries: int = 1) -> tuple[str, dict]` where the dict is `{"input_tokens": int, "output_tokens": int, "cost_usd": float}`. Raises `ClaudeCLIError` on failure after retries. Both names are imported by Tasks 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_llm.py`:

```python
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from claude_llm import complete, ClaudeCLIError


def make_envelope(result="hello", is_error=False, cost=0.01, in_tok=100, out_tok=50):
    return json.dumps({
        "result": result,
        "is_error": is_error,
        "total_cost_usd": cost,
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
    })


def make_proc(stdout, returncode=0, stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class CompleteTestCase(unittest.TestCase):
    @patch("claude_llm.subprocess.run")
    def test_happy_path_returns_text_and_usage(self, mock_run):
        mock_run.return_value = make_proc(make_envelope("  summary text  "))
        text, usage = complete("prompt here", system_prompt="be brief")
        self.assertEqual(text, "summary text")
        self.assertEqual(usage, {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01})
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0], "claude")
        self.assertIn("-p", cmd)
        self.assertIn("--tools", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-sonnet-5")
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "be brief")
        self.assertEqual(mock_run.call_args.kwargs["input"], "prompt here")

    @patch("claude_llm.subprocess.run")
    def test_no_system_prompt_flag_when_omitted(self, mock_run):
        mock_run.return_value = make_proc(make_envelope())
        complete("prompt")
        self.assertNotIn("--system-prompt", mock_run.call_args.args[0])

    @patch("claude_llm.subprocess.run")
    def test_is_error_envelope_raises_after_retries(self, mock_run):
        mock_run.return_value = make_proc(make_envelope(is_error=True))
        with self.assertRaises(ClaudeCLIError):
            complete("prompt", retries=1)
        self.assertEqual(mock_run.call_count, 2)

    @patch("claude_llm.subprocess.run")
    def test_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = make_proc("", returncode=1, stderr="auth expired")
        with self.assertRaises(ClaudeCLIError) as ctx:
            complete("prompt", retries=0)
        self.assertIn("auth expired", str(ctx.exception))

    @patch("claude_llm.subprocess.run")
    def test_malformed_json_raises(self, mock_run):
        mock_run.return_value = make_proc("not json at all")
        with self.assertRaises(ClaudeCLIError):
            complete("prompt", retries=0)

    @patch("claude_llm.subprocess.run")
    def test_timeout_is_retried_then_raises(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)
        with self.assertRaises(ClaudeCLIError):
            complete("prompt", retries=1)
        self.assertEqual(mock_run.call_count, 2)

    @patch("claude_llm.subprocess.run")
    def test_retry_succeeds_after_transient_failure(self, mock_run):
        mock_run.side_effect = [
            make_proc("", returncode=1, stderr="flake"),
            make_proc(make_envelope("ok")),
        ]
        text, _ = complete("prompt", retries=1)
        self.assertEqual(text, "ok")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_claude_llm.py -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'claude_llm'`

- [ ] **Step 3: Write the implementation**

Create `src/claude_llm.py`:

```python
"""LLM backend for the beta pipeline: shells out to the Claude Code CLI.

Auth comes from CLAUDE_CODE_OAUTH_TOKEN in the environment (see
docs/superpowers/specs/2026-09-12-beta-pipeline-design.md). Runs from a
neutral cwd so no CLAUDE.md or project settings leak into generations.
"""

import json
import subprocess
import tempfile


class ClaudeCLIError(Exception):
    pass


def _run_once(prompt, system_prompt, model, timeout):
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", ""]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=tempfile.gettempdir(),
    )
    if proc.returncode != 0:
        raise ClaudeCLIError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeCLIError(f"unparseable claude output ({e}): {proc.stdout[:500]}")
    if envelope.get("is_error") or "result" not in envelope:
        raise ClaudeCLIError(f"claude error envelope: {proc.stdout[:500]}")
    usage = envelope.get("usage", {})
    return envelope["result"].strip(), {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": envelope.get("total_cost_usd", 0.0),
    }


def complete(prompt, system_prompt=None, model="claude-sonnet-5", timeout=600, retries=1):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return _run_once(prompt, system_prompt, model, timeout)
        except (ClaudeCLIError, subprocess.TimeoutExpired) as e:
            last_error = e
            print(f"⚠️ claude -p attempt {attempt + 1}/{retries + 1} failed: {e}")
    raise ClaudeCLIError(f"claude -p failed after {retries + 1} attempts: {last_error}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_claude_llm.py -v`
Expected: all 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_llm.py tests/test_claude_llm.py
git commit -m "Add claude_llm: claude -p backend for the beta pipeline"
```

---

### Task 2: `config/beta.json` + loader

**Files:**
- Create: `config/beta.json`
- Create: `src/beta_config.py`
- Test: `tests/test_beta_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_beta_config(config_path=None) -> dict` in `beta_config.py`, reading `config/beta.json` by default. The committed config dict has keys: `enabled` (bool), `model` (str), `prompts_dir` (str), `title_prefix` (str), `article_sources` (list of `{"name","tag","file"}`), `summary_filename`, `summary_without_links_filename`, `flag_filename`, `substack_url`, `substack_session_file` (all str). Tasks 3 and 4 read these exact keys.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_beta_config.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from beta_config import load_beta_config

REQUIRED_KEYS = {
    "enabled", "model", "prompts_dir", "title_prefix", "article_sources",
    "summary_filename", "summary_without_links_filename", "flag_filename",
    "substack_url", "substack_session_file",
}


class BetaConfigTestCase(unittest.TestCase):
    def test_default_config_loads_with_required_keys(self):
        cfg = load_beta_config()
        self.assertTrue(REQUIRED_KEYS.issubset(cfg.keys()),
                        f"missing: {REQUIRED_KEYS - cfg.keys()}")

    def test_beta_filenames_do_not_collide_with_prod(self):
        cfg = load_beta_config()
        prod_filenames = {"summary.txt", "summary_without_links.txt", "flag.txt",
                          "summary_el.txt", "summary_without_links_el.txt", "flag_el.txt"}
        beta_filenames = {cfg["summary_filename"],
                          cfg["summary_without_links_filename"], cfg["flag_filename"]}
        self.assertFalse(beta_filenames & prod_filenames)

    def test_explicit_path_override(self):
        import json, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"enabled": True}, f)
        cfg = load_beta_config(f.name)
        self.assertTrue(cfg["enabled"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_beta_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'beta_config'`

- [ ] **Step 3: Write config and loader**

Create `config/beta.json` (`enabled` ships false — flipped to true in Task 6 once the beta publication URL and NAS token exist; `substack_url` placeholder is replaced at the same time):

```json
{
  "enabled": false,
  "model": "claude-sonnet-5",
  "prompts_dir": "src/prompts",
  "title_prefix": "🧪 ",
  "article_sources": [
    {"name": "Cyprus Mail", "tag": "CM", "file": "data/cyprus_articles.json"},
    {"name": "Cyprus Mail", "tag": "CM", "file": "data/cm_crime_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_articles.json"},
    {"name": "In-Cyprus", "tag": "IC", "file": "data/in_cyprus_local_economy_articles.json"},
    {"name": "Politis EN", "tag": "PE", "file": "data/en_politis_politics_articles.json"},
    {"name": "Politis EN", "tag": "PE", "file": "data/en_politis_economy_articles.json"},
    {"name": "Politis EN", "tag": "PE", "file": "data/en_politis_social_articles.json"}
  ],
  "summary_filename": "summary_beta.txt",
  "summary_without_links_filename": "summary_without_links_beta.txt",
  "flag_filename": "flag_beta.txt",
  "substack_url": "REPLACE_WITH_BETA_PUBLISH_URL",
  "substack_session_file": "substack_session.json"
}
```

Create `src/beta_config.py` (mirrors `lang_config.py`'s path convention):

```python
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "beta.json"


def load_beta_config(config_path=None):
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_beta_config.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add config/beta.json src/beta_config.py tests/test_beta_config.py
git commit -m "Add beta pipeline config (shipped disabled)"
```

---

### Task 3: `summarize_beta.py` — Claude-backed summarizer fork

**Files:**
- Create: `src/summarize_beta.py`
- Test: `tests/test_summarize_beta.py`

**Interfaces:**
- Consumes: `claude_llm.complete` (Task 1), `beta_config.load_beta_config` (Task 2), and from prod (read-only imports): `summarize.combine_summaries`, `summarize.limit_headlines`, `summarize.load_articles`, `summarize.split_summary`, `summarize.strip_summary_marker`, `summarize.build_tag_examples`; `helpers.get_text_folder_for_day`; `date_heading.generate_date_heading`; `ongoing_topics.load_ongoing_topics`, `ongoing_topics.build_ongoing_topics_section_entries`.
- Produces: `summarize_for_day_beta(day: date, cfg: dict | None = None) -> None` (writes the two beta summary files) and `apply_title_prefix(date_heading: str, prefix: str) -> str`. Task 4 calls `summarize_for_day_beta`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_summarize_beta.py`. The pipeline test mocks `claude_llm.complete` and redirects the day folder to a tmp dir:

```python
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from summarize_beta import apply_title_prefix, summarize_for_day_beta

FAKE_USAGE = {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001}

TEST_CFG = {
    "enabled": True,
    "model": "claude-sonnet-5",
    "prompts_dir": "src/prompts",
    "title_prefix": "🧪 ",
    "article_sources": [],
    "summary_filename": "summary_beta.txt",
    "summary_without_links_filename": "summary_without_links_beta.txt",
    "flag_filename": "flag_beta.txt",
    "substack_url": "unused",
    "substack_session_file": "unused",
}


def fake_complete(prompt, system_prompt=None, model=None, timeout=600, retries=1):
    # Headline call and chunk call both return valid sectioned markdown;
    # the cleanup call returns a recognizable cleaned body.
    if "SUMMARY:" in prompt:
        return "### Economy\n- cleaned bullet", FAKE_USAGE
    return "### Top stories\n- headline one\n\n### Economy\n- economy bullet", FAKE_USAGE


class ApplyTitlePrefixTestCase(unittest.TestCase):
    def test_prefix_inserted_after_h2_marker(self):
        heading = "## 📰 News Summary — Friday\n\nintro text"
        out = apply_title_prefix(heading, "🧪 ")
        self.assertTrue(out.startswith("## 🧪 📰 News Summary"))
        self.assertIn("intro text", out)

    def test_empty_prefix_is_noop(self):
        heading = "## 📰 News Summary"
        self.assertEqual(apply_title_prefix(heading, ""), heading)


class SummarizeForDayBetaTestCase(unittest.TestCase):
    def test_writes_beta_files_with_prefix_and_skips_linking_without_articles(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text(
                "Πρώτη παράγραφος.\n\nΔεύτερη παράγραφος.", encoding="utf-8"
            )
            with patch("summarize_beta.get_text_folder_for_day", return_value=txt), \
                 patch("summarize_beta.complete", side_effect=fake_complete), \
                 patch("summarize_beta.load_ongoing_topics",
                       return_value={"topics": [], "config": {}}):
                summarize_for_day_beta(day, cfg=TEST_CFG)

            without_links = (txt / "summary_without_links_beta.txt").read_text(encoding="utf-8")
            final = (txt / "summary_beta.txt").read_text(encoding="utf-8")
            self.assertIn("🧪", without_links.splitlines()[0])
            self.assertIn("🧪", final.splitlines()[0])
            self.assertIn("Top stories", final)
            self.assertIn("cleaned bullet", final)
            # beta must not touch prod filenames
            self.assertFalse((txt / "summary.txt").exists())
            self.assertFalse((txt / "summary_without_links.txt").exists())

    def test_existing_beta_summary_is_reused_not_regenerated(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_without_links_beta.txt").write_text(
                "## 🧪 heading\n\n### Top stories\n- old headline\n\n### Economy\n- old bullet",
                encoding="utf-8",
            )
            calls = []

            def counting_complete(prompt, **kwargs):
                calls.append(prompt)
                return "### Economy\n- cleaned bullet", FAKE_USAGE

            with patch("summarize_beta.get_text_folder_for_day", return_value=txt), \
                 patch("summarize_beta.complete", side_effect=counting_complete), \
                 patch("summarize_beta.load_ongoing_topics",
                       return_value={"topics": [], "config": {}}):
                summarize_for_day_beta(day, cfg=TEST_CFG)

            # Only the cleanup call should have hit the LLM (no chunk summarization)
            self.assertEqual(len(calls), 1)
            self.assertIn("SUMMARY:", calls[0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_summarize_beta.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'summarize_beta'`

- [ ] **Step 3: Write the implementation**

Create `src/summarize_beta.py`. This is a deliberate fork of `summarize.py`'s English path with `claude_llm.complete` as the backend — expected to diverge as experiments land. Structure (write it in full, following `summarize.py`'s originals closely):

```python
"""Beta summarizer: fork of summarize.py's English path, backed by claude -p.

This file is the beta lane's scratch space — it may freely diverge from
summarize.py. Pure helpers are imported from summarize (read-only reuse);
copy one in here only when an experiment needs to change it.
See docs/superpowers/specs/2026-09-12-beta-pipeline-design.md.
"""

import json
import os
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
            text, usage = complete(
                f"{user_prompt}\n\n{chunk}",
                system_prompt=headline_system_prompt,
                model=model,
            )
            headlines = limit_headlines(text)
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


def cleanup_merged_summary_beta(summary_text, deduplication_prompt, model):
    final_prompt = f"{deduplication_prompt}\n\nSUMMARY:\n{summary_text}\n"
    print("[beta] Sending to claude for cleanup...")
    return complete(final_prompt, model=model)


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
        f"headers, bullet points, and markdown structure exactly as they appear in the input."
    )
    linking_prompt = (
        f"{prompt_with_tags}\n\nSUMMARY:\n{summary_text}\n\n"
        f"ARTICLES:\n{json.dumps(filtered_articles, ensure_ascii=False)}\n"
    )
    print("[beta] Sending to claude for article-linking...")
    return complete(linking_prompt, system_prompt=system_msg, model=model)
```

Then `summarize_for_day_beta(day, cfg=None)`, mirroring `summarize.summarize_for_day` with these differences: config from `beta.json`; prompts from `cfg["prompts_dir"]` (English base names only: `prompt.txt`, `first_chunk_system_prompt.txt`, `followup_chunk_system_prompt.txt`, `headline_system_prompt.txt`, `link_prompt.txt`, `deduplication_prompt.txt`); date heading gets `apply_title_prefix`; output filenames from cfg; ongoing topics read-only; usage printed with real `cost_usd` from the CLI:

```python
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

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"\n✅ [beta] Final summary with links saved to {output_file}")
    print(f"📊 [beta] Token usage: {total_usage['input_tokens']} in / {total_usage['output_tokens']} out")
    print(f"💰 [beta] Cost (from claude CLI): ${total_usage['cost_usd']:.4f} USD")
```

Note for the implementer: the reused-summary test patches `summarize_beta.complete`, which works because `complete` is imported by name — keep the `from claude_llm import complete` import style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_summarize_beta.py -v`
Expected: 4 PASS

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `.venv/bin/python -m pytest tests -v`
Expected: only the two pre-existing failures listed in Global Constraints.

- [ ] **Step 6: Commit**

```bash
git add src/summarize_beta.py tests/test_summarize_beta.py
git commit -m "Add summarize_beta: claude-backed fork of the English summarize path"
```

---

### Task 4: `main_beta.py` — beta orchestrator

**Files:**
- Create: `src/main_beta.py`
- Test: `tests/test_main_beta.py`

**Interfaces:**
- Consumes: `beta_config.load_beta_config` (Task 2), `summarize_beta.summarize_for_day_beta` (Task 3), prod's `post_to_substack(md_path, publish, cover_path=..., substack_url=..., session_file=..., lang=...) -> bool` and `helpers.get_text_folder_for_day`.
- Produces: CLI entrypoint `python src/main_beta.py [date] [--draft] [--no-post] [--config PATH]`; internal functions `resolve_day(date_arg, now=None) -> date | None` and `run_beta(day, publish=True, no_post=False, cfg=None) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_beta.py`:

```python
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from main_beta import resolve_day, run_beta

CY_TZ = ZoneInfo("Europe/Nicosia")

BASE_CFG = {
    "enabled": True,
    "model": "claude-sonnet-5",
    "prompts_dir": "src/prompts",
    "title_prefix": "🧪 ",
    "article_sources": [],
    "summary_filename": "summary_beta.txt",
    "summary_without_links_filename": "summary_without_links_beta.txt",
    "flag_filename": "flag_beta.txt",
    "substack_url": "https://example.substack.com/publish/post",
    "substack_session_file": "substack_session.json",
}


class ResolveDayTestCase(unittest.TestCase):
    def test_explicit_date(self):
        self.assertEqual(resolve_day("2026-09-01"), date(2026, 9, 1))

    def test_before_start_hour_returns_none(self):
        now = datetime(2026, 9, 12, 5, 30, tzinfo=CY_TZ)
        self.assertIsNone(resolve_day(None, now=now))

    def test_after_start_hour_returns_yesterday(self):
        now = datetime(2026, 9, 12, 7, 0, tzinfo=CY_TZ)
        self.assertEqual(resolve_day(None, now=now), date(2026, 9, 11))


class RunBetaTestCase(unittest.TestCase):
    def test_disabled_config_does_nothing(self):
        with patch("main_beta.summarize_for_day_beta") as mock_summarize, \
             patch("main_beta.post_to_substack") as mock_post:
            run_beta(date(2026, 9, 1), cfg={**BASE_CFG, "enabled": False})
            mock_summarize.assert_not_called()
            mock_post.assert_not_called()

    def test_missing_transcript_exits_without_summarizing(self):
        with TemporaryDirectory() as tmp:
            with patch("main_beta.get_text_folder_for_day", return_value=Path(tmp)), \
                 patch("main_beta.summarize_for_day_beta") as mock_summarize, \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(date(2026, 9, 1), cfg=BASE_CFG)
                mock_summarize.assert_not_called()
                mock_post.assert_not_called()

    def test_summarizes_posts_and_touches_flag_on_success(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")

            def fake_summarize(d, cfg=None):
                (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")

            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.summarize_for_day_beta", side_effect=fake_summarize), \
                 patch("main_beta.post_to_substack", return_value=True) as mock_post:
                run_beta(day, cfg=BASE_CFG)
                mock_post.assert_called_once()
                kwargs = mock_post.call_args.kwargs
                self.assertEqual(kwargs["substack_url"], BASE_CFG["substack_url"])
                self.assertEqual(kwargs["lang"], "en")
                self.assertTrue((txt / "flag_beta.txt").exists())

    def test_failed_post_leaves_no_flag(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack", return_value=False):
                run_beta(day, cfg=BASE_CFG)
                self.assertFalse((txt / "flag_beta.txt").exists())

    def test_no_post_skips_posting(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, no_post=True, cfg=BASE_CFG)
                mock_post.assert_not_called()

    def test_existing_flag_skips_posting(self):
        day = date(2026, 9, 1)
        with TemporaryDirectory() as tmp:
            txt = Path(tmp)
            (txt / "transcript_gr.txt").write_text("κείμενο", encoding="utf-8")
            (txt / "summary_beta.txt").write_text("## 🧪 x", encoding="utf-8")
            (txt / "flag_beta.txt").touch()
            with patch("main_beta.get_text_folder_for_day", return_value=txt), \
                 patch("main_beta.post_to_substack") as mock_post:
                run_beta(day, cfg=BASE_CFG)
                mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_main_beta.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main_beta'`

- [ ] **Step 3: Write the implementation**

Create `src/main_beta.py`:

```python
"""Beta pipeline orchestrator — runs alongside main.py, never touches prod state.

Waits for prod's transcript, summarizes via claude -p (summarize_beta),
posts to the beta Substack. Idempotent via summary_beta.txt / flag_beta.txt.
See docs/superpowers/specs/2026-09-12-beta-pipeline-design.md.
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from beta_config import load_beta_config
from helpers import get_text_folder_for_day
from post_to_substack import post_to_substack
from summarize_beta import summarize_for_day_beta
from timing import timing_step

CY_TZ = ZoneInfo("Europe/Nicosia")
START_HOUR = 6  # match prod: don't process until 6am Cyprus time


def resolve_day(date_arg, now=None):
    if date_arg:
        return datetime.strptime(date_arg, "%Y-%m-%d").date()
    now_cy = now or datetime.now(CY_TZ)
    if now_cy.hour < START_HOUR:
        print(f"⏳ It's {now_cy.strftime('%H:%M')} in Cyprus — too early, waiting until {START_HOUR}:00.")
        return None
    return now_cy.date() - timedelta(days=1)


def run_beta(day, publish=True, no_post=False, cfg=None):
    cfg = cfg or load_beta_config()
    if not cfg.get("enabled", False):
        print("[beta] Disabled in config/beta.json — exiting.")
        return

    txt = get_text_folder_for_day(day)
    transcript = txt / "transcript_gr.txt"
    if not transcript.exists():
        print(f"⏳ [beta] {transcript} not found — waiting for prod transcript, exiting.")
        return

    summary_file = txt / cfg["summary_filename"]
    if not summary_file.exists():
        with timing_step("summarize_beta", date=day.isoformat()):
            summarize_for_day_beta(day, cfg=cfg)
    else:
        print(f"[beta] {summary_file} exists — skipping summarization.")

    if no_post:
        print("⏭️  [beta] --no-post specified, skipping Substack posting.")
        return

    flag_file = txt / cfg["flag_filename"]
    if summary_file.exists() and not flag_file.exists():
        cover_path = txt / "cover.png"
        secrets_root = Path(os.getenv("SECRETS_ROOT", "./data"))
        session_path = secrets_root / cfg["substack_session_file"]
        with timing_step("post_to_substack_beta", date=day.isoformat()):
            if post_to_substack(summary_file, publish, cover_path=cover_path,
                                substack_url=cfg["substack_url"],
                                session_file=str(session_path), lang="en"):
                flag_file.touch()


def main():
    parser = argparse.ArgumentParser(description="Generate and post beta Cyprus news summary.")
    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (defaults to yesterday)")
    parser.add_argument("--draft", action="store_true", help="Save draft instead of publishing")
    parser.add_argument("--no-post", action="store_true", help="Skip Substack posting entirely")
    parser.add_argument("--config", type=str, help="Path to an alternate beta config JSON")
    args = parser.parse_args()

    try:
        day = resolve_day(args.date)
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD (e.g. 2026-09-01).")
        return
    if day is None:
        return

    cfg = load_beta_config(args.config) if args.config else None
    run_beta(day, publish=not args.draft, no_post=args.no_post, cfg=cfg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_main_beta.py -v`
Expected: 9 PASS

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests -v`
Expected: only the two pre-existing failures.

- [ ] **Step 6: Commit**

```bash
git add src/main_beta.py tests/test_main_beta.py
git commit -m "Add main_beta: beta pipeline orchestrator"
```

---

### Task 5: Docker image + cron entry

**Files:**
- Modify: `Dockerfile` (after the existing `RUN apt-get update && apt-get install -y cron ffmpeg` line)
- Modify: `cyprus-news-cron` (add one line)

**Interfaces:**
- Consumes: `src/main_beta.py` CLI (Task 4).
- Produces: a container where `claude` is on PATH and cron runs beta at :30 hourly.

- [ ] **Step 1: Add Node 20 + Claude Code CLI to the Dockerfile**

Insert after the apt-get line:

```dockerfile
# Node 20 + Claude Code CLI for the beta pipeline (claude -p backend)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code
```

(The Playwright jammy base image ships `curl`.)

- [ ] **Step 2: Add the beta cron line**

Append to `cyprus-news-cron` (keep the trailing newline — crontab requires it):

```
30 * * * *  cd /app && export SECRETS_ROOT=/app/secrets && . /app/secrets/env.sh && xvfb-run -a python /app/src/main_beta.py >> /app/data/cyprus_news_beta_$(date +\%Y-\%m-\%d).log 2>&1
```

- [ ] **Step 3: Verify the image builds (if Docker is available locally)**

Run: `docker build -t cyprus_news_beta_check . 2>&1 | tail -5`
Expected: `naming to ...cyprus_news_beta_check` success line. Then verify the CLI: `docker run --rm --entrypoint claude cyprus_news_beta_check --version` → prints a version.
If Docker is not available on this machine: state that explicitly and defer build verification to the NAS deploy (operator step in Task 6); do not claim the build was verified.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile cyprus-news-cron
git commit -m "Install Claude Code CLI in image and add beta cron entry"
```

---

### Task 6: End-to-end validation + enablement

**Files:**
- Modify: `config/beta.json` (real `substack_url`, `enabled: true`) — only after operator setup
- Modify: `HANDOFF.md` (document the beta lane)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: a validated, enabled beta lane and updated handoff docs.

- [ ] **Step 1: Find a local day with a transcript**

Run: `ls summaries/*/txt/transcript_gr.txt 2>/dev/null`
If none exists, generate one for a recent date (requires `.env` sourced for the OpenAI key, and RIK still hosting the video — recent dates only):
`set -a && . .env && set +a && .venv/bin/python -c "from datetime import date; import sys; sys.path.insert(0,'src'); from main import generate_for_date; generate_for_date(date(2026, 9, 10))"` — or simply `.venv/bin/python src/main.py 2026-09-10 --no-post`. Note this costs ~$0.15 (transcription) and generates prod summary files locally too, which is fine (they're gitignored data).

- [ ] **Step 2: Dry-run the beta pipeline end-to-end (no posting)**

Create an enabled config copy in the scratchpad, then run with `--config`:

```bash
python3 - <<'EOF'
import json
cfg = json.load(open("config/beta.json"))
cfg["enabled"] = True
json.dump(cfg, open("/tmp/beta_e2e.json", "w"), indent=2)
EOF
.venv/bin/python src/main_beta.py <DATE_FROM_STEP_1> --no-post --config /tmp/beta_e2e.json
```

Expected: `summary_beta.txt` and `summary_without_links_beta.txt` appear in `summaries/<date>/txt/`, first line starts `## 🧪`, sections and article links look sane, cost line printed. Read the output file and sanity-check the content against the prod `summary.txt` for the same day. This is the real `claude -p` path — no OpenAI key needed for the beta half.

- [ ] **Step 3: OPERATOR GATE — wait for beta publication URL + NAS token**

Blocked on the user having: (a) created the beta publication under the same Substack account and provided its URL; (b) run `claude setup-token` and added `export CLAUDE_CODE_OAUTH_TOKEN=...` to the NAS `secrets/env.sh`. Do not proceed to Step 4 without (a). Ask if not yet provided.

- [ ] **Step 4: Draft-post test against the real beta publication**

Update `config/beta.json`: set `substack_url` to `https://<beta-pub>.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome` and `enabled` to `true`. Then:

Run: `.venv/bin/python src/main_beta.py <DATE_FROM_STEP_1> --draft`
Expected: a draft appears on the beta publication with the 🧪 title, cover image, and linked body; no `flag_beta.txt` blocker issues (draft mode still touches the flag on success — delete `summaries/<date>/txt/flag_beta.txt` afterwards if you want to re-test).

- [ ] **Step 5: Update HANDOFF.md**

Add a short "Beta pipeline" section: what it is (parallel claude-backed lane, `src/main_beta.py` + `src/summarize_beta.py` + `config/beta.json`, cron at :30), the isolation rules (prod state read-only, `*_beta` files only), how to disable it (`enabled: false`), and that `summarize_beta.py` is expected to diverge from `summarize.py`.

- [ ] **Step 6: Full suite + commit**

Run: `.venv/bin/python -m pytest tests -v` (only pre-existing failures) then:

```bash
git add config/beta.json HANDOFF.md
git commit -m "Enable beta pipeline against beta publication; document in handoff"
```

- [ ] **Step 7: OPERATOR — deploy**

On the NAS: pull, `docker compose build`, `docker compose up -d`. Next morning, check `data/cyprus_news_beta_<date>.log` and the beta publication for the first automated post. (Operator step — the implementing agent only reminds the user.)
