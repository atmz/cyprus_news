from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

GREEK_DAYS = {
    0: "Δευτέρα", 1: "Τρίτη", 2: "Τετάρτη", 3: "Πέμπτη",
    4: "Παρασκευή", 5: "Σάββατο", 6: "Κυριακή"
}
GREEK_MONTHS = {
    1: "Ιανουαρίου", 2: "Φεβρουαρίου", 3: "Μαρτίου", 4: "Απριλίου",
    5: "Μαΐου", 6: "Ιουνίου", 7: "Ιουλίου", 8: "Αυγούστου",
    9: "Σεπτεμβρίου", 10: "Οκτωβρίου", 11: "Νοεμβρίου", 12: "Δεκεμβρίου"
}
RUSSIAN_DAYS = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье"
}
RUSSIAN_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

def _summary_reference(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "this evening's"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "this evening's"
    return "yesterday's"

def _summary_reference_el(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "του σημερινού"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "του σημερινού"
    return "του χθεσινού"

def _summary_reference_ru(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "сегодняшнего"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "сегодняшнего"
    return "вчерашнего"

def generate_date_heading(day, lang="en"):
    if lang == "ru":
        day_name = RUSSIAN_DAYS[day.weekday()]
        month_name = RUSSIAN_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Обзор новостей — {date_str}\n\n"
        ref = _summary_reference_ru(day)
        heading += (
            f"Обзор {ref} [вечернего выпуска новостей (20:00) телеканала РИК](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Где возможно, приводятся ссылки на соответствующие статьи. "
            f"Обзор подготовлен с помощью AI и может содержать неточности."
        )
        return heading

    if lang == "el":
        day_name = GREEK_DAYS[day.weekday()]
        month_name = GREEK_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Περίληψη Ειδήσεων — {date_str}\n\n"
        ref = _summary_reference_el(day)
        heading += (
            f"Περίληψη {ref} [βραδινού δελτίου ειδήσεων (8μμ) του ΡΙΚ](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Όπου υπάρχουν, περιλαμβάνονται σύνδεσμοι σε σχετικά άρθρα. "
            f"Η περίληψη δημιουργήθηκε με τη βοήθεια AI και ενδέχεται να περιέχει ανακρίβειες."
        )
        return heading

    # English (default / current behavior)
    date_str = day.strftime('%A, %-d %B %Y')
    heading = f"## 📰 News Summary for {date_str}\n\n"
    ref = _summary_reference(day)
    heading += (
        f"This is a summary of {ref} "
        f"[8pm RIK news broadcast](https://tv.rik.cy/show/eideseis-ton-8/). "
        f"Where available, links to related English-language articles from the Cyprus Mail "
        f"and In-Cyprus are provided for further reading. Please note that this summary was "
        f"generated with the assistance of AI and may contain inaccuracies."
    )
    return heading
