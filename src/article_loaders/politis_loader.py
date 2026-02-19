import json
import os
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Politis dates come as "17.02.2026 13:31" in display text,
# but the <time> element has a proper datetime attribute: "2026-02-17T11:31:00.000Z"
POLITIS_DATE_RE = re.compile(
    r"^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):(\d{2})$"
)


def parse_politis_date(text):
    """Parse '17.02.2026 13:31' into ISO format."""
    m = POLITIS_DATE_RE.match(text.strip())
    if m:
        day, month, year, hour, minute = m.groups()
        return f"{year}-{month}-{day}T{int(hour):02d}:{int(minute):02d}:00"
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

    for article_tag in soup.find_all("article"):
        link_tag = article_tag.find("a", href=True)
        if not link_tag:
            continue

        href = urljoin(base_url, link_tag["href"])
        if href in known_urls:
            continue

        title_tag = article_tag.find("h3")
        if not title_tag:
            continue

        dt = None
        time_tag = article_tag.find("time")
        if time_tag:
            # Prefer the visible text (local Cyprus time) over the UTC datetime attr
            dt = parse_politis_date(time_tag.get_text(strip=True))

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


def refresh_politis():
    _refresh_category(
        "https://www.politis.com.cy/politis-news/cyprus",
        "data/politis_cyprus_articles.json",
    )


if __name__ == "__main__":
    refresh_politis()
