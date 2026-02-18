import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Dates appear as "18 February 2026" in English month names
MONTHS_EN = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(MONTHS_EN) + r")\s+(\d{4})"
)


def parse_evropakipr_date(text):
    """Parse '18 February 2026' into ISO format."""
    m = DATE_RE.search(text.strip())
    if m:
        day, month_name, year = m.groups()
        month = MONTHS_EN[month_name]
        return f"{year}-{month:02d}-{int(day):02d}T00:00:00"
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

    seen_urls = set()

    # Structure: div.post-c-wrap > h4.title > a[href], div.post-date
    for wrap in soup.find_all("div", class_="post-c-wrap"):
        title_h4 = wrap.find("h4", class_="title")
        if not title_h4:
            continue

        link = title_h4.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        # Ensure absolute URL
        if href.startswith("/"):
            href = "https://evropakipr.com" + href

        if href in known_urls or href in seen_urls:
            continue
        seen_urls.add(href)

        dt = None
        date_div = wrap.find("div", class_="post-date")
        if date_div:
            dt = parse_evropakipr_date(date_div.get_text(strip=True))

        article = {
            "title": link.get_text(strip=True),
            "abstract": None,
            "datetime": dt,
            "url": href,
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


def refresh_evropakipr():
    _refresh_category(
        "https://evropakipr.com/novosti",
        "data/evropakipr_novosti_articles.json",
    )


if __name__ == "__main__":
    refresh_evropakipr()
