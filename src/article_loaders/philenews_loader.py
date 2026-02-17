import json
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

GREEK_MONTHS = {
    "Ιανουαρίου": 1, "Φεβρουαρίου": 2, "Μαρτίου": 3, "Απριλίου": 4,
    "Μαΐου": 5, "Ιουνίου": 6, "Ιουλίου": 7, "Αυγούστου": 8,
    "Σεπτεμβρίου": 9, "Οκτωβρίου": 10, "Νοεμβρίου": 11, "Δεκεμβρίου": 12,
}

DATE_RE = re.compile(
    r"(\d{1,2})\s+("
    + "|".join(GREEK_MONTHS)
    + r")\s+(\d{4}),?\s*(\d{1,2}):(\d{2})"
)


RELATIVE_RE = re.compile(r"Πριν\s*(\d+)\s*(λεπτ|ώρ|ωρ)")
# "Updated: 17 Φεβρουαρίου - 8:52" (no year)
UPDATED_RE = re.compile(
    r"(\d{1,2})\s+("
    + "|".join(GREEK_MONTHS)
    + r")\s*-\s*(\d{1,2}):(\d{2})"
)


def parse_greek_datetime(text):
    """Parse '17 Φεβρουαρίου 2026, 9:33' or 'Πριν 48 λεπτά' into ISO format."""
    m = DATE_RE.search(text)
    if m:
        day, month_name, year, hour, minute = m.groups()
        month = GREEK_MONTHS[month_name]
        return f"{year}-{month:02d}-{int(day):02d}T{int(hour):02d}:{int(minute):02d}:00"

    # Handle "Updated: 17 Φεβρουαρίου - 8:52" (no year, assume current)
    um = UPDATED_RE.search(text)
    if um:
        day, month_name, hour, minute = um.groups()
        month = GREEK_MONTHS[month_name]
        year = datetime.now().year
        return f"{year}-{month:02d}-{int(day):02d}T{int(hour):02d}:{int(minute):02d}:00"

    # Handle relative times: "Πριν 48 λεπτά", "Πριν 2 ώρες"
    rm = RELATIVE_RE.search(text)
    if rm:
        amount = int(rm.group(1))
        unit = rm.group(2)
        now = datetime.now()
        if unit.startswith("λεπτ"):
            dt = now - timedelta(minutes=amount)
        else:
            dt = now - timedelta(hours=amount)
        return dt.strftime("%Y-%m-%dT%H:%M:00")

    return None


def load_existing_articles(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def fetch_articles(base_url, known_urls=None):
    known_urls = known_urls or set()
    new_articles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        print(f"🌐 Navigating to {base_url}")

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"❌ Failed to load page: {e}")
            browser.close()
            return []

        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    # Structure: div.card-wrapper > a[href] > div.card > div.card-info
    card_wrappers = soup.find_all("div", class_="card-wrapper")
    print(f"🔎 Found {len(card_wrappers)} card wrappers")

    for wrapper in card_wrappers:
        link_tag = wrapper.find("a")
        if not link_tag or not link_tag.get("href"):
            continue

        full_url = link_tag["href"]
        if full_url in known_urls:
            continue

        card = link_tag.find("div", class_="card")
        if not card:
            continue

        title_tag = card.find("h3")
        time_div = card.find("div", class_="time")
        author_tag = card.find("h4", class_="author")

        dt = None
        if time_div:
            dt = parse_greek_datetime(time_div.get_text(strip=True))

        article = {
            "title": title_tag.get_text(strip=True) if title_tag else None,
            "abstract": None,
            "datetime": dt,
            "url": full_url,
            "author": author_tag.get_text(strip=True) if author_tag else None,
        }
        new_articles.append(article)

    return new_articles


def _refresh_category(base_url, json_path):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    existing_articles = load_existing_articles(json_path)
    existing_urls = {a["url"] for a in existing_articles}

    new_articles = fetch_articles(base_url, known_urls=existing_urls)
    all_articles = new_articles + existing_articles

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"🎉 {base_url}: {len(new_articles)} new, {len(all_articles)} total")


def refresh_philenews():
    _refresh_category(
        "https://www.philenews.com/kipros/",
        "data/philenews_kipros_articles.json",
    )
    _refresh_category(
        "https://www.philenews.com/oikonomia/",
        "data/philenews_oikonomia_articles.json",
    )


if __name__ == "__main__":
    refresh_philenews()
