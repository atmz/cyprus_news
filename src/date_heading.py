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
UKRAINIAN_DAYS = {
    0: "понеділок", 1: "вівторок", 2: "середа", 3: "четвер",
    4: "п'ятниця", 5: "субота", 6: "неділя"
}
UKRAINIAN_MONTHS = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}
HEBREW_DAYS = {
    0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי",
    4: "שישי", 5: "שבת", 6: "ראשון"
}
HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
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

def _summary_reference_uk(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "сьогоднішнього"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "сьогоднішнього"
    return "вчорашнього"

def _summary_reference_he(day):
    cyprus_now = datetime.now(ZoneInfo("Asia/Nicosia"))
    day_date = day.date() if isinstance(day, datetime) else day
    if cyprus_now.date() == day_date:
        return "של היום"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "של היום"
    return "של אתמול"

def generate_date_heading(day, lang="en"):
    if lang == "he":
        day_name = HEBREW_DAYS[day.weekday()]
        month_name = HEBREW_MONTHS[day.month]
        date_str = f"יום {day_name}, {day.day} ב{month_name} {day.year}"
        heading = f"## 📰 סיכום חדשות — {date_str}\n\n"
        ref = _summary_reference_he(day)
        heading += (
            f"סיכום {ref} [שידור חדשות הערב (20:00) של ערוץ RIK](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"במידת האפשר, צורפו קישורים לכתבות רלוונטיות. "
            f"הסיכום הוכן בסיוע AI ועשוי להכיל אי-דיוקים. "
            f"העורך אינו דובר עברית — אם הבחנתם בטעות, אנא דווחו לנו."
        )
        return heading

    if lang == "uk":
        day_name = UKRAINIAN_DAYS[day.weekday()]
        month_name = UKRAINIAN_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Огляд новин — {date_str}\n\n"
        ref = _summary_reference_uk(day)
        heading += (
            f"Огляд {ref} [вечірнього випуску новин (20:00) телеканалу РІК](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Де можливо, додано посилання на відповідні статті. "
            f"Огляд підготовлено за допомогою AI і може містити неточності. "
            f"Автор не володіє українською мовою — якщо ви помітили помилку, будь ласка, повідомте нас."
        )
        return heading

    if lang == "ru":
        day_name = RUSSIAN_DAYS[day.weekday()]
        month_name = RUSSIAN_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Обзор новостей — {date_str}\n\n"
        ref = _summary_reference_ru(day)
        heading += (
            f"Обзор {ref} [вечернего выпуска новостей (20:00) телеканала РИК](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Где возможно, приводятся ссылки на соответствующие статьи. "
            f"Обзор подготовлен с помощью AI и может содержать неточности. "
            f"Автор не владеет русским языком — если вы заметили ошибку, пожалуйста, сообщите нам."
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
