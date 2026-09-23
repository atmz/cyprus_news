import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from transcribe import transcribe_with_retry


def make_client(texts):
    """Client whose successive transcription calls return the given texts."""
    client = MagicMock()
    results = []
    for t in texts:
        r = MagicMock()
        r.text = t
        results.append(r)
    client.audio.transcriptions.create.side_effect = results
    return client


class TranscribeWithRetryTestCase(unittest.TestCase):
    def test_all_empty_attempts_returns_result_not_none(self):
        # A silent trailing segment returns "" every time; the caller must
        # still get a result object (this returned None and crashed the
        # 2026-09-22 run).
        client = make_client(["", "", ""])
        result = transcribe_with_retry(client, io.BytesIO(b"x"), retries=3)
        self.assertIsNotNone(result)
        self.assertEqual(result.text, "")

    def test_min_chars_zero_accepts_empty_immediately(self):
        client = make_client([""])
        result = transcribe_with_retry(client, io.BytesIO(b"x"), min_chars=0)
        self.assertIsNotNone(result)
        self.assertEqual(client.audio.transcriptions.create.call_count, 1)

    def test_good_result_returns_immediately(self):
        client = make_client(["α" * 300])
        result = transcribe_with_retry(client, io.BytesIO(b"x"))
        self.assertEqual(len(result.text), 300)
        self.assertEqual(client.audio.transcriptions.create.call_count, 1)

    def test_file_rewound_between_attempts(self):
        # Retries must not upload an exhausted (EOF) file handle.
        client = make_client(["", "α" * 300])
        audio = MagicMock(wraps=io.BytesIO(b"x"))
        transcribe_with_retry(client, audio)
        self.assertGreaterEqual(audio.seek.call_count, 2)
        audio.seek.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()
