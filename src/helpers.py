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

def build_summary_with_note(summary_text: str, note_text: str) -> str:
    """Insert '*Editors note: ...*' as the first body line of a summary.

    The note goes immediately after the '## ' title line: post_to_substack
    takes the post title from that line and starts the body after it, so
    this makes the note the first paragraph of the published email.
    Returns summary_text unchanged when the note is empty.
    """
    note = " ".join((note_text or "").split())
    if not note:
        return summary_text
    note_line = f"*Editors note: {note}*"
    lines = summary_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("##"):
            return "\n".join(lines[: i + 1] + ["", note_line] + lines[i + 1 :])
    return note_line + "\n\n" + summary_text


def make_folders(day: date):
    paths = [
        get_root_folder_for_day(day),
        get_media_folder_for_day(day),
        get_text_folder_for_day(day),
    ]
    for path in paths:
        os.makedirs(path, exist_ok=True)