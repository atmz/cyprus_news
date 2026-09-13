import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "beta.json"


def load_beta_config(config_path=None):
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
