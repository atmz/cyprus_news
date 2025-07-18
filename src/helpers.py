import os
from datetime import date

def get_root_folder_for_day(day: date):
    return f"/app/summaries/{day.strftime('%Y-%m-%d')}/"

def get_media_folder_for_day(day: date):
    return f"/app/summaries/{day.strftime('%Y-%m-%d')}/media/"

def get_text_folder_for_day(day: date):
    return f"/app/summaries/{day.strftime('%Y-%m-%d')}/txt/"

def make_folders(day: date):
    paths = [
        get_root_folder_for_day(day),
        get_media_folder_for_day(day),
        get_text_folder_for_day(day),
    ]
    for path in paths:
        os.makedirs(path, exist_ok=True)