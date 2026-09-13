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
