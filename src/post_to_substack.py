import argparse
from pathlib import Path
import re
import time
import os
from playwright.sync_api import sync_playwright

# --- CONFIG ---

SECRETS_ROOT = Path(os.getenv("SECRETS_ROOT", "./data"))
SESSION_FILE = f"{SECRETS_ROOT}/substack_session.json"
SUBSTACK_NEW_POST_URL = "https://cyprusnews.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome"
TOP_STORIES_H3_RE = re.compile(r'(?im)^\s*#{3}\s*Top\s*stories\b.*$')  # exactly "### Top stories" (any case)
markdown_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")

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

def post_to_substack(md_path, publish=False, cover_path="cover.png"):
    def insert_link(page, label: str, url: str):
        import time
        # Type the label
        page.keyboard.type(label)
        # Select the label we just typed (character-wise for reliability)
        for _ in range(len(label)):
            page.keyboard.down("Shift")
            page.keyboard.press("ArrowLeft")
            page.keyboard.up("Shift")
        # Open link dialog, type URL, confirm
        page.keyboard.down("Control"); page.keyboard.press("KeyK"); page.keyboard.up("Control")
        time.sleep(0.15)
        page.keyboard.type(url)
        time.sleep(0.05)
        page.keyboard.press("Enter")
        time.sleep(0.05)
        # Move caret after the link node
        page.keyboard.press("ArrowRight")
    def insert_image_via_toolbar(page, image_path):
        from pathlib import Path
        import re, time

        abs_path = str(Path(image_path).expanduser().resolve())
        print(f"🖼️ Inserting cover image via toolbar: {abs_path}")

        # Ensure editor focus / toolbar visible
        editor = page.locator("div.ProseMirror").first
        editor.wait_for(state="visible", timeout=10000)
        editor.click()

        # Count existing image-like nodes inside editor
        visuals_sel = (
            "div.ProseMirror img, "
            "div.ProseMirror figure, "
            "div.ProseMirror [data-testid='imageBlock'], "
            "div.ProseMirror [class*='imageBlock']"
        )
        visuals = page.locator(visuals_sel)
        before_count = visuals.count()

        # Open toolbar image menu → Add image → native file chooser
        image_btn = page.locator("button[aria-label='Image'][title='Insert image']").first
        image_btn.wait_for(state="visible", timeout=5000)
        image_btn.click()

        try:
            menu_item = page.get_by_role("menuitem", name=re.compile(r"Add image", re.I))
            menu_item.wait_for(state="visible", timeout=5000)
        except Exception:
            menu_item = page.locator("button:has-text('Add image')").first

        with page.expect_file_chooser() as fc_info:
            menu_item.click()
        fc_info.value.set_files(abs_path)

        # Wait for a NEW image block to appear
        deadline = time.time() + 30
        while time.time() < deadline:
            cur_count = visuals.count()
            if cur_count > before_count:
                new_node = visuals.nth(cur_count - 1)
                try:
                    new_node.scroll_into_view_if_needed()
                except Exception:
                    pass

                # Place caret just under the image (no extra Enter/ArrowDown here)
                try:
                    box = new_node.bounding_box()
                    if box:
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] + 6)
                except Exception:
                    pass
                return

            page.wait_for_timeout(200)

        raise RuntimeError("Timed out waiting for image block to appear after upload.")


    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    markdown = md_path.read_text(encoding="utf-8")
    title, body = extract_title_and_body(markdown)

    print_header_once = True  # optional: just here if you want to debug the match
    image_inserted = False

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

        print("Writing body...")
        page.click("div.ProseMirror")
        for paragraph in body.split("\n\n"):
            for raw_line in paragraph.splitlines():
                line = raw_line.strip()

                # Insert image immediately BEFORE typing the "### Top stories" header
                if (not image_inserted) and TOP_STORIES_H3_RE.match(line):
                    print("🪄 Found '### Top stories' — inserting cover image just before it...")

                    # 1) Create an empty paragraph *here* and move caret onto it
                    page.keyboard.press("Enter")      # make a blank line at current spot
                    page.keyboard.press("ArrowUp")    # put caret on that blank (anchor)

                    # 2) Insert the image at the anchored caret
                    insert_image_via_toolbar(page, cover_path)

                    # 3) Ensure caret is *below* the image (one gentle nudge)
                    page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")

                    image_inserted = True
                    # (now typing continues and the very next line you type will be the H3 header)

                # Bullets -> dot
                if line.startswith("- "):
                    page.keyboard.type("• ")
                    line = line[2:].strip()

                # Type text with labeled links
                pos = 0
                for m in markdown_link_pattern.finditer(line):
                    start, end = m.span()
                    before = line[pos:start]
                    label = m.group(1)
                    url   = m.group(2)
                    print(f"Typing link: label={label}, url={url}")
                    if before:
                        page.keyboard.type(before)

                    # Your old, working popup flow
                    page.keyboard.down("Control")
                    page.keyboard.press("KeyK")
                    page.keyboard.up("Control")
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


                if pos < len(line):
                    page.keyboard.type(line[pos:])

                page.keyboard.press("Enter")
        page.keyboard.press("Enter")
        # If we never saw the header, you can optionally insert at top/end:
        # if not image_inserted:
        #     print("ℹ️ '### Top stories' not found — inserting image at top.")
        #     page.keyboard.press("Home")
        #     insert_image_via_toolbar(page, cover_path)

        # Add a short delay before UI interaction
        page.wait_for_timeout(1000)

        # Open the Button dropdown
        page.click("button:has-text('Button')")

        # Click "Subscribe with caption"
        page.click("text=Subscribe w/ caption")
        print("📬 Subscribe button inserted.")

        if False:#publish:
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post a markdown file to Substack.")
    parser.add_argument("md_path", type=Path, help="Path to the markdown file")
    parser.add_argument("--publish", action="store_true", help="Actually publish instead of saving as draft")
    
    args = parser.parse_args()
    post_to_substack(args.md_path, publish=args.publish)