import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Date formats: "17.02.2026" (big cards) or "13:28" (sidebar, time only)
DOT_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
TIME_ONLY_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_sigmalive_date(text):
    """Parse '17.02.2026' or '13:28' (today assumed) into ISO format."""
    m = DOT_DATE_RE.match(text.strip())
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}T00:00:00"

    tm = TIME_ONLY_RE.match(text.strip())
    if tm:
        hour, minute = tm.groups()
        today = datetime.now()
        return f"{today.year}-{today.month:02d}-{today.day:02d}T{int(hour):02d}:{int(minute):02d}:00"

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

    # Find all links to /news/ articles
    for a_tag in soup.find_all("a", href=re.compile(r"/news/")):
        href = urljoin(base_url, a_tag.get("href", ""))
        if not href or href in known_urls or href in seen_urls:
            continue

        # Must have a title (h2 for big cards, h3 for sidebar)
        title_tag = a_tag.find("h2") or a_tag.find("h3")
        if not title_tag:
            continue

        seen_urls.add(href)

        # Find date
        dt = None
        # Big cards: p with date inside the link
        date_p = a_tag.find("p", class_=re.compile(r"font-bold.*text-sm|text-sm.*font-bold"))
        if date_p:
            dt = parse_sigmalive_date(date_p.get_text(strip=True))

        # Sidebar: time is in a sibling p element
        if not dt:
            parent = a_tag.parent
            if parent:
                sibling_p = parent.find("p")
                if sibling_p and sibling_p != date_p:
                    dt = parse_sigmalive_date(sibling_p.get_text(strip=True))

        article = {
            "title": title_tag.get_text(strip=True),
            "abstract": None,
            "datetime": dt,
            "url": href,
        }
        new_articles.append(article)

    return new_articles


def _refresh_category(base_url, json_path):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    existing_articles = load_existing_articles(json_path)
    # Fix any previously stored relative URLs
    for a in existing_articles:
        if a.get("url") and not a["url"].startswith("http"):
            a["url"] = urljoin(base_url, a["url"])
    existing_urls = {a["url"] for a in existing_articles}

    new_articles = fetch_articles(base_url, known_urls=existing_urls)
    all_articles = new_articles + existing_articles

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"🎉 {base_url}: {len(new_articles)} new, {len(all_articles)} total")


def refresh_sigmalive():
    _refresh_category(
        "https://www.sigmalive.com/news/local",
        "data/sigmalive_local_articles.json",
    )


if __name__ == "__main__":
    refresh_sigmalive()
