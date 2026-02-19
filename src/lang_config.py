import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "languages.json"

def load_language_config(config_path=None):
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_enabled_languages(config=None):
    if config is None:
        config = load_language_config()
    return {k: v for k, v in config.items() if v.get("enabled", False)}

def get_translation_languages(config=None):
    """Return languages that derive from translating another language."""
    enabled = get_enabled_languages(config)
    return {k: v for k, v in enabled.items()
            if v["summary_source"].startswith("translate_from:")}

def get_native_summary_languages(config=None):
    """Return languages where summary_source == 'summarize_native'."""
    enabled = get_enabled_languages(config)
    return {k: v for k, v in enabled.items()
            if v["summary_source"] == "summarize_native"}

def get_source_language(lang_config):
    """Parse 'translate_from:en' -> 'en'."""
    return lang_config["summary_source"].split(":", 1)[1]
