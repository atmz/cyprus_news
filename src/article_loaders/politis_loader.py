import json
import os
import re
import requests
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


# ---------------------------------------------------------------------------
# English Politis (en.politis.com.cy)
# ---------------------------------------------------------------------------
# The English site uses the same <article>/<h3>/<time> structure, but each
# featured card has a category <a> before the <h3>, so we find article links
# via the <h3> element rather than the first <a> in the article.

_EN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}


def fetch_en_politis_articles(base_url, known_urls=None):
    known_urls = known_urls or set()

    print(f"🌐 Fetching {base_url}")
    try:
        response = requests.get(base_url, headers=_EN_HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch {base_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Collect into a dict keyed by URL so that when the same article appears
    # in both a large featured card (no <time>) and a small card (<time>
    # present), we keep the version that has the datetime.
    articles_by_url = {}

    for article_tag in soup.find_all("article"):
        # Article link is always inside <h3>; skip category link that may
        # appear before it in featured cards.
        h3_tag = article_tag.find("h3")
        if not h3_tag:
            continue
        link_tag = h3_tag.find("a", href=True)
        if not link_tag:
            continue

        href = urljoin(base_url, link_tag["href"])
        if href in known_urls:
            continue

        title = link_tag.get_text(strip=True)
        if not title:
            continue

        # Abstract from <h4> (featured cards only; small cards have a
        # one-word category label in <h4> which we discard)
        h4_tag = article_tag.find("h4")
        abstract = None
        if h4_tag:
            candidate = h4_tag.get_text(strip=True)
            if " " in candidate:  # skip "POLITICS", "ECONOMY", etc.
                abstract = candidate

        # Date from <time> (small cards only; no datetime attr on the element)
        dt = None
        time_tag = article_tag.find("time")
        if time_tag:
            dt = parse_politis_date(time_tag.get_text(strip=True))

        if href not in articles_by_url:
            articles_by_url[href] = {
                "title": title,
                "abstract": abstract,
                "datetime": dt,
                "url": href,
            }
        elif dt is not None and articles_by_url[href]["datetime"] is None:
            # Upgrade the existing entry with the datetime from the small card
            articles_by_url[href]["datetime"] = dt

    return list(articles_by_url.values())


def refresh_en_politis():
    categories = [
        ("https://en.politis.com.cy/politics", "data/en_politis_politics_articles.json"),
        ("https://en.politis.com.cy/economy",  "data/en_politis_economy_articles.json"),
        ("https://en.politis.com.cy/social-lens", "data/en_politis_social_articles.json"),
    ]
    for base_url, json_path in categories:
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        existing = load_existing_articles(json_path)
        for a in existing:
            if a.get("url") and not a["url"].startswith("http"):
                a["url"] = urljoin(base_url, a["url"])
        existing_urls = {a["url"] for a in existing}
        new_articles = fetch_en_politis_articles(base_url, known_urls=existing_urls)
        all_articles = new_articles + existing
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, ensure_ascii=False, indent=2)
        print(f"🎉 {base_url}: {len(new_articles)} new, {len(all_articles)} total")


if __name__ == "__main__":
    refresh_politis()
