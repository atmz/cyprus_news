import json
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def load_existing_articles(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def extract_background_image(style):
    if not style or "url(" not in style:
        return None
    start = style.find("url(") + 4
    end = style.find(")", start)
    return style[start:end].strip("'\"")

def fetch_new_articles(base_url, known_urls=None, max_clicks=20):
    known_urls = known_urls or set()
    new_articles = []
    seen_urls = set()
    click_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        print(f"🌐 Navigating to {base_url}")
        page.on("console", lambda msg: print(f"[Console] {msg.type}: {msg.text}"))
        page.on("response", lambda res: print(f"[Response] {res.status} - {res.url}"))
        page.on("requestfailed", lambda req: print(f"[Request Failed] {req.url}"))

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"❌ Failed to load page: {e}")
            try:
                page.screenshot(path="goto_failed.png", full_page=True, timeout=10000)
            except Exception:
                pass
            return []

        page.wait_for_timeout(2000)

        # Accept cookies if the popup exists
        try:
            accept_button = page.locator("text=Accept All")
            if accept_button.count() > 0:
                print("🍪 Clicking 'Accept All' cookies button")
                accept_button.first.click()
                page.wait_for_timeout(1000)
            else:
                print("🍪 No cookie banner found.")
        except Exception as e:
            print(f"⚠️ Cookie click error: {e}")
        while click_count < max_clicks:
            print(f"\n🔁 Scroll round {click_count+1}")
            # The cookie banner (and 'Load more') can trigger navigations; content()
            # raises if called mid-navigation, so settle and retry.
            html = None
            for _ in range(3):
                try:
                    page.wait_for_load_state("load", timeout=15000)
                    html = page.content()
                    break
                except Exception:
                    page.wait_for_timeout(1500)
            if html is None:
                print("⚠️ Could not read page content — stopping.")
                break
            soup = BeautifulSoup(html, "html.parser")
            article_blocks = soup.find_all("div", class_="td_module_flex")

            print(f"🔎 Found {len(article_blocks)} article blocks on page")

            new_this_round = 0
            for block in article_blocks:
                link = block.find("a", rel="bookmark")
                if not link or not link.has_attr("href"):
                    continue

                full_url = link["href"]
                if full_url in known_urls or full_url in seen_urls:
                    continue  # Don't exit — just skip

                seen_urls.add(full_url)

                title = link.get("title") or link.get_text(strip=True)
                abstract_tag = block.find("div", class_="td-excerpt")
                time_tag = block.find("time")
                thumb_span = block.find("span", class_="entry-thumb")
                style = thumb_span.get("style", "") if thumb_span else ""
                image_url = extract_background_image(style)

                article = {
                    "title": title,
                    "abstract": abstract_tag.get_text(strip=True) if abstract_tag else None,
                    "datetime": time_tag.get("datetime") if time_tag else None,
                    "url": full_url,
                    "image_url": image_url,
                }

                new_articles.append(article)
                new_this_round += 1

            print(f"✅ Added {new_this_round} new articles this round.")

            if new_this_round == 0:
                print("🛑 No new articles found in this round — stopping.")
                break

            # Click "Load more"
            try:
                load_more = page.locator("a.td_ajax_load_more_js")
                count = load_more.count()
                print(f"🔘 Load more button count: {count}")
                if count == 0:
                    print("⛔ No 'Load more' button found.")
                    break
                print("👆 Clicking 'Load more'...")
                load_more.first.click()
                page.wait_for_timeout(2000)
                click_count += 1
            except Exception as e:
                print(f"⚠️ Error clicking 'Load more': {e}")
                break

        browser.close()
    return new_articles

def refresh_ic():
    base_url = "https://in-cyprus.philenews.com/category/local/"
    json_path = "data/in_cyprus_local_articles.json"

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    existing_articles = load_existing_articles(json_path)
    existing_urls = {article["url"] for article in existing_articles}

    new_articles = fetch_new_articles(base_url, known_urls=existing_urls)
    all_articles = new_articles + existing_articles

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Done! Found {len(new_articles)} new articles.")
    print(f"📦 Total stored: {len(all_articles)}")


    base_url = "https://in-cyprus.philenews.com/category/insider/economy/"
    json_path = "data/in_cyprus_local_economy_articles.json"

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    existing_articles = load_existing_articles(json_path)
    existing_urls = {article["url"] for article in existing_articles}

    new_articles = fetch_new_articles(base_url, known_urls=existing_urls)
    all_articles = new_articles + existing_articles

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Done! Found {len(new_articles)} new articles.")
    print(f"📦 Total stored: {len(all_articles)}")

if __name__ == "__main__":
    refresh_ic()
