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
