import argparse
from pathlib import Path
import re
import time
from playwright.sync_api import sync_playwright

# --- CONFIG ---
SESSION_FILE = "/app/secrets/substack_session.json"
SUBSTACK_NEW_POST_URL = "https://cyprusnews.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome"

def extract_title_and_body(markdown_text):
    lines = markdown_text.strip().splitlines()
    title = ""
    body_lines = []

    for line in lines:
        if line.startswith("#"):
            title = re.sub(r"^#+\s*📰?\s*", "", line).strip()
            break

    in_body = False
    for line in lines:
        if in_body:
            body_lines.append(line)
        elif line.startswith("##"):
            in_body = True

    return title, "\n".join(body_lines).strip()

def post_to_substack(md_path, publish=False):
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    markdown = md_path.read_text(encoding="utf-8")
    title, body = extract_title_and_body(markdown)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        print("📝 Opening Substack editor...")
        page.goto(SUBSTACK_NEW_POST_URL)
        page.wait_for_selector("textarea[placeholder='Title']", timeout=15000)

        print(f"✍️ Writing title: {title}")
        page.fill("textarea[placeholder='Title']", title)

        print("⌨️ Writing body...")
        page.click("div.ProseMirror")


        markdown_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
        for paragraph in body.split("\n\n"):
            for line in paragraph.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    page.keyboard.type("• ")
                    line = line[2:].strip()

                # Track cursor position through the line
                pos = 0
                for match in markdown_link_pattern.finditer(line):
                    
                    start, end = match.span()
                    before = line[pos:start]
                    label = match.group(1)
                    url = match.group(2)
                    print(f"Typing link: label={label}, url={url}")

                    if before:
                        page.keyboard.type(before)

                    # Trigger link insertion popup
                    page.keyboard.down("Meta")
                    page.keyboard.press("KeyK")
                    page.keyboard.up("Meta")
                    time.sleep(0.2)
                    page.keyboard.type(label)
                    page.keyboard.press("Tab")
                    time.sleep(0.2)
                    page.keyboard.type(url)
                    time.sleep(0.2)
                    page.keyboard.press("Enter")
                    time.sleep(0.2)
                    page.keyboard.press("ArrowRight")

                    pos = end

                # Type any remaining text after last link
                if pos < len(line):
                    page.keyboard.type(line[pos:])

                page.keyboard.press("Enter")
            page.keyboard.press("Enter")


        # Add a short delay before UI interaction
        page.wait_for_timeout(1000)

        # Open the Button dropdown
        page.click("button:has-text('Button')")

        # Click "Subscribe with caption"
        page.click("text=Subscribe w/ caption")
        print("📬 Subscribe button inserted.")
        if publish:
            print("📤 Clicking Publish now...")
            try:
                page.wait_for_timeout(500) 
                page.click("text=Continue", timeout=5000)
                page.wait_for_timeout(1000) 
                page.click("text=Send to everyone now", timeout=5000)
                page.wait_for_timeout(3000) 
                print("✅ Post published.")
            except:
                print("⚠️ Could not find Publish button — post might already be published.")
        else:
            print("💾 Waiting for auto-save (as draft)...")
            page.wait_for_timeout(4000)
            print("✅ Draft saved (not published).")

        browser.close()
