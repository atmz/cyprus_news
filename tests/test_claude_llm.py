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
