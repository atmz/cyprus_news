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
        return "το απογευματινό"
    elif cyprus_now.date() == (day_date + timedelta(days=1)) and cyprus_now.hour < 2:
        return "το απογευματινό"
    return "το χθεσινό"

def generate_date_heading(day, lang="en"):
    if lang == "el":
        day_name = GREEK_DAYS[day.weekday()]
        month_name = GREEK_MONTHS[day.month]
        date_str = f"{day_name}, {day.day} {month_name} {day.year}"
        heading = f"## 📰 Περίληψη Ειδήσεων για {date_str}\n\n"
        ref = _summary_reference_el(day)
        heading += (
            f"Αυτή είναι μια περίληψη {ref} "
            f"[δελτίο ειδήσεων στις 8μμ του ΡΙΚ](https://tv.rik.cy/show/eideseis-ton-8/). "
            f"Όπου είναι διαθέσιμοι, παρέχονται σύνδεσμοι σε σχετικά ελληνόγλωσσα άρθρα. "
            f"Σημειώστε ότι αυτή η περίληψη δημιουργήθηκε με τη βοήθεια AI και μπορεί να περιέχει ανακρίβειες."
        )
        return heading

    # English (default / current behavior)
    date_str = day.strftime('%A, %d %B %Y')
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
