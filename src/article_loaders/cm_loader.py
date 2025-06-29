import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin

def load_existing_articles(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def fetch_new_articles(base_url, known_urls=None):
    known_urls = known_urls or set()
    new_articles = []
    page = 1
    keep_going = True

    while keep_going and page<10:
        url = f"{base_url}/page/{page}"
        print(f"Fetching {url}...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        article_tags = soup.find_all("article")
        if not article_tags:
            break  # No more articles/pages

        for tag in article_tags:
            link_tag = tag.find("a", class_="_lnkTitle_cekga_5")
            if not link_tag:
                continue
            full_url = urljoin(base_url, link_tag.get("href"))
            if full_url in known_urls:
                keep_going = False
                break  # Stop fetching — we hit a known article

            title_tag = tag.find("h2")
            abstract_tag = tag.find("div", class_="abstract")
            time_tag = tag.find("time")
            author_tag = tag.find("div", class_="_authorsCnt_cekga_14")
            image_tag = tag.find("img")

            article = {
                "title": title_tag.text.strip() if title_tag else None,
                "abstract": abstract_tag.text.strip() if abstract_tag else None,
                "datetime": time_tag.get("datetime") if time_tag else None,
                "author": author_tag.text.strip().replace("By", "").strip() if author_tag else None,
                "url": full_url,
                "image_url": urljoin(base_url, image_tag.get("src")) if image_tag else None,
            }


        page += 1

    return new_articles

def refresh_cm():
    base_url = "https://cyprus-mail.com/category/cyprus"
    json_path = "data/cyprus_articles.json"

    # Load existing
    existing_articles = load_existing_articles(json_path)
    existing_urls = {article["url"] for article in existing_articles}

    # Fetch new until first known article
    new_articles = fetch_new_articles(base_url, known_urls=existing_urls)

    # Prepend new articles (to keep chronological order)
    all_articles = new_articles + existing_articles

    # Save
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"Found {len(new_articles)} new articles. Total stored: {len(all_articles)}")
    base_url = "https://cyprus-mail.com/category/crime"
    json_path = "data/cm_crime_articles.json"

    # Load existing
    existing_articles = load_existing_articles(json_path)
    existing_urls = {article["url"] for article in existing_articles}

    # Fetch new until first known article
    new_articles = fetch_new_articles(base_url, known_urls=existing_urls)

    # Prepend new articles (to keep chronological order)
    all_articles = new_articles + existing_articles

    # Save
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"Found {len(new_articles)} new articles. Total stored: {len(all_articles)}")
