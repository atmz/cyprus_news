import os
from datetime import date
from pathlib import Path

# Configure root directory (defaults to ./summaries if not set)
SUMMARIES_ROOT = Path(os.getenv("SUMMARIES_ROOT", "./summaries"))

def get_root_folder_for_day(day: date) -> Path:
    return SUMMARIES_ROOT / day.strftime("%Y-%m-%d")

def get_media_folder_for_day(day: date) -> Path:
    return get_root_folder_for_day(day) / "media"

def get_text_folder_for_day(day: date) -> Path:
    return get_root_folder_for_day(day) / "txt"

def make_folders(day: date):
    paths = [
        get_root_folder_for_day(day),
        get_media_folder_for_day(day),
        get_text_folder_for_day(day),
    ]
    for path in paths:
        os.makedirs(path, exist_ok=True)