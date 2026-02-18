import json
import os
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# Dates appear as:
# - "Вчера в 15:47" (yesterday at 15:47)
# - "16 февраля" (16 February, no year)
# - "Сегодня в 10:00" (today at 10:00)
RUSSIAN_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

DATE_MONTH_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(RUSSIAN_MONTHS) + r")"
)
YESTERDAY_RE = re.compile(r"Вчера\s+в\s+(\d{1,2}):(\d{2})")
TODAY_RE = re.compile(r"Сегодня\s+в\s+(\d{1,2}):(\d{2})")


def parse_butterfly_date(text):
    """Parse Russian date formats into ISO format."""
    text = text.strip()

    m = TODAY_RE.search(text)
    if m:
        hour, minute = m.groups()
        today = datetime.now()
        return f"{today.year}-{today.month:02d}-{today.day:02d}T{int(hour):02d}:{int(minute):02d}:00"

    m = YESTERDAY_RE.search(text)
    if m:
        hour, minute = m.groups()
        yesterday = datetime.now() - timedelta(days=1)
        return f"{yesterday.year}-{yesterday.month:02d}-{yesterday.day:02d}T{int(hour):02d}:{int(minute):02d}:00"

    m = DATE_MONTH_RE.search(text)
    if m:
        day, month_name = m.groups()
        month = RUSSIAN_MONTHS[month_name]
        year = datetime.now().year
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

        page.wait_for_timeout(5000)

        # JS-rendered site: extract via evaluate
        # Structure: .blog-card__item2 contains a > .blog-card_title + .blog-card_date
        # Also check the featured card: .blog-card__container
        articles_data = page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            // Featured card
            const featured = document.querySelector('.blog-card__container');
            if (featured) {
                const a = featured.querySelector('a');
                const title = featured.querySelector('.blog-card_title');
                const date = featured.querySelector('.blog-card_date');
                if (a && title) {
                    const href = a.getAttribute('href');
                    if (!seen.has(href)) {
                        seen.add(href);
                        results.push({
                            href: href,
                            title: title.innerText.trim(),
                            date: date ? date.innerText.trim() : null,
                        });
                    }
                }
            }

            // Regular cards
            const cards = document.querySelectorAll('.blog-card__item2');
            cards.forEach(card => {
                const a = card.querySelector('a');
                const title = card.querySelector('.blog-card_title');
                const date = card.querySelector('.blog-card_date');
                if (a && title) {
                    const href = a.getAttribute('href');
                    if (!seen.has(href)) {
                        seen.add(href);
                        results.push({
                            href: href,
                            title: title.innerText.trim(),
                            date: date ? date.innerText.trim() : null,
                        });
                    }
                }
            });

            return results;
        }""")

        browser.close()

    seen_urls = set()
    for item in articles_data:
        href = item.get("href", "")
        if not href or href in known_urls or href in seen_urls:
            continue

        # Ensure absolute URL
        if not href.startswith("http"):
            if not href.startswith("/"):
                href = "/" + href
            href = "https://cyprusbutterfly.com.cy" + href

        seen_urls.add(href)

        title = item.get("title", "")
        if not title:
            continue

        dt = None
        if item.get("date"):
            dt = parse_butterfly_date(item["date"])

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


def refresh_cyprusbutterfly():
    _refresh_category(
        "https://cyprusbutterfly.com.cy/news/",
        "data/cyprusbutterfly_articles.json",
    )


if __name__ == "__main__":
    refresh_cyprusbutterfly()
