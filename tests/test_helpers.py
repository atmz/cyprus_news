import importlib
import os
from datetime import date
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))


class HelpersTestCase(unittest.TestCase):
    def test_make_folders_creates_expected_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["SUMMARIES_ROOT"] = tmpdir
            helpers = importlib.import_module("helpers")
            helpers = importlib.reload(helpers)

            target_day = date(2024, 1, 15)
            helpers.make_folders(target_day)

            root = Path(tmpdir) / "2024-01-15"
            self.assertTrue(root.exists())
            self.assertTrue((root / "media").exists())
            self.assertTrue((root / "txt").exists())

    def test_get_root_folder_for_day_uses_env_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["SUMMARIES_ROOT"] = tmpdir
            helpers = importlib.import_module("helpers")
            helpers = importlib.reload(helpers)

            target_day = date(2024, 5, 20)
            expected = Path(tmpdir) / "2024-05-20"
            self.assertEqual(helpers.get_root_folder_for_day(target_day), expected)


if __name__ == "__main__":
    unittest.main()
