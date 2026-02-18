import json
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_relative_time(text):
    """Parse Turkish relative times like '5 dakika önce', '2 saat önce', '1 gün önce'."""
    text = text.strip().rstrip("|").strip()
    now = datetime.now()

    m = re.match(r"(\d+)\s+(dakika|saat|gün)\s+önce", text)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        if unit == "dakika":
            dt = now - timedelta(minutes=amount)
        elif unit == "saat":
            dt = now - timedelta(hours=amount)
        elif unit == "gün":
            dt = now - timedelta(days=amount)
        else:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Try absolute date like "08/02/26" (DD/MM/YY)
    m2 = re.match(r"(\d{2})/(\d{2})/(\d{2})", text)
    if m2:
        day, month, year = m2.groups()
        return f"20{year}-{month}-{day}T00:00:00"

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

    # Find all links pointing to articles in this category
    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Only article links (contain /nNNNNN-)
        if not re.search(r"/n\d+-", href):
            continue

        # Ensure absolute URL
        if href.startswith("/"):
            href = "https://www.kibrispostasi.com" + href

        if href in known_urls or href in seen_urls:
            continue

        # Find title in h3 or h5 inside the link
        title_tag = link.find(["h3", "h5"])
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        if not title:
            continue

        seen_urls.add(href)

        # Look for time text near the title
        dt = None
        time_span = link.find("span", string=re.compile(r"(dakika|saat|gün)\s+önce|\d{2}/\d{2}/\d{2}"))
        if time_span:
            dt = parse_relative_time(time_span.get_text(strip=True))

        new_articles.append({
            "title": title,
            "abstract": None,
            "datetime": dt,
            "url": href,
        })

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


def refresh_kibrispostasi():
    _refresh_category(
        "https://www.kibrispostasi.com/c35-KIBRIS_HABERLERI",
        "data/kibrispostasi_articles.json",
    )


if __name__ == "__main__":
    refresh_kibrispostasi()
