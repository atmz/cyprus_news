import argparse
from pathlib import Path
import re
import time
import os
from playwright.sync_api import sync_playwright
import platform

# --- CONFIG ---

SECRETS_ROOT = Path(os.getenv("SECRETS_ROOT", "./data"))
SESSION_FILE = SECRETS_ROOT / "substack_session.json"
SUBSTACK_NEW_POST_URL = "https://cyprusnews.substack.com/publish/post?type=newsletter&back=%2Fpublish%2Fhome"
TOP_STORIES_H3_RE = re.compile(r'(?im)^\s*#{3}\s*(?:Top\s*stories|Κύριες\s*Ειδήσεις)\b.*$')
markdown_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
LINK_MOD = "Meta" if platform.system() == "Darwin" else "Control"

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

def post_to_substack(md_path, publish=False, cover_path="cover.png",
                     substack_url=None, session_file=None):
    actual_url = substack_url or SUBSTACK_NEW_POST_URL
    actual_session = Path(session_file) if session_file else SESSION_FILE

    def log_info(message: str):
        print(f"SUBSTACK: {message}")

    def get_editor_locator(page):
        editor = page.locator("[data-testid='editor']")
        log_info(f"Editor locator test id count={editor.count()}")
        if editor.count() > 0:
            log_info("Using editor locator: [data-testid='editor']")
            return editor.first
        log_info("Falling back to editor locator: div.ProseMirror")
        return page.locator("div.ProseMirror").first

    def fast_type(page, text: str):
        if not text:
            return
        page.keyboard.insert_text(text)

    def rule_type(page, text: str):
        if not text:
            return
        page.keyboard.type(text)

    def insert_link(page, label: str, url: str):
        import time
        # Type the label
        fast_type(page, label)
        # Select the label we just typed (character-wise for reliability)
        for _ in range(len(label)):
            page.keyboard.down("Shift")
            page.keyboard.press("ArrowLeft")
            page.keyboard.up("Shift")
        # Open link dialog, type URL, confirm
        page.keyboard.down("Control"); page.keyboard.press("KeyK"); page.keyboard.up("Control")
        time.sleep(0.15)
        fast_type(page, url)
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
        editor = get_editor_locator(page)
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
            menu_item = page.locator("button:has-text('Image')").first

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

                page.wait_for_timeout(1000)
                # Place caret just under the image (no extra Enter/ArrowDown here)
                try:
                    box = new_node.bounding_box()
                    if box:
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] + 6)
                except Exception:
                    pass
                page.wait_for_timeout(1000)
                return

            page.wait_for_timeout(200)

        raise RuntimeError("Timed out waiting for image block to appear after upload.")

    def place_caret_after_last_image(page):
        result = page.evaluate(
            """() => {
                const editor = document.querySelector("[data-testid='editor']") || document.querySelector("div.ProseMirror");
                if (!editor) return "editor-missing";
                editor.focus();
                const selection = window.getSelection();
                if (!selection) return "selection-missing";
                const nodes = editor.querySelectorAll(
                    "div.captioned-image-container, figure, img, [data-testid='imageBlock'], [class*='imageBlock']"
                );
                if (!nodes.length) return "image-missing";
                const target = nodes[nodes.length - 1];
                const container = target.closest("div.captioned-image-container, figure") || target;
                let next = container.nextElementSibling;
                if (!next || next.tagName !== "P") {
                    const paragraph = document.createElement("p");
                    paragraph.appendChild(document.createElement("br"));
                    container.insertAdjacentElement("afterend", paragraph);
                    next = paragraph;
                }
                const range = document.createRange();
                range.setStart(next, 0);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
                return "ok";
            }"""
        )
        log_info(f"Placed caret after image block: {result}")
        return result

    def normalize_expected_text(text: str) -> str:
        normalized = markdown_link_pattern.sub(r"\1", text)
        normalized = re.sub(r"(?m)^\s*#{1,6}\s*", "", normalized)
        normalized = normalized.replace("- ", "• ")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        return normalized.strip()

    def collect_required_snippets(text: str, max_snippets: int = 6) -> list[str]:
        snippets = []
        for line in normalize_expected_text(text).splitlines():
            cleaned = line.strip()
            if len(cleaned) < 8:
                continue
            snippets.append(cleaned)
            if len(snippets) >= max_snippets:
                break
        return snippets

    def validate_editor_content(page, expected_title: str, expected_body: str):
        title_value = page.locator("textarea[placeholder='Title']").input_value()
        if expected_title and expected_title not in title_value:
            raise RuntimeError("Title field does not contain the expected title text.")

        editor_text = get_editor_locator(page).inner_text()
        required_snippets = collect_required_snippets(expected_body)
        missing = [snippet for snippet in required_snippets if snippet not in editor_text]
        if missing:
            log_info(f"Editor content missing snippets: {missing[:3]}")
            raise RuntimeError(
                "Editor content missing expected snippets: "
                + "; ".join(missing[:3])
            )

    def wait_for_publish_success(page, timeout_s: int = 30) -> bool:
        deadline = time.time() + timeout_s
        log_info(f"Waiting for publish confirmation (timeout={timeout_s}s)...")
        success_texts = [
            "Published",
            "Your post is published",
            "View post",
            "Sent to everyone",
        ]
        while time.time() < deadline:
            for text in success_texts:
                if page.locator(f"text={text}").first.is_visible():
                    log_info(f"Publish confirmation detected: {text}")
                    return True
            if "/publish/" not in page.url:
                log_info(f"Publish confirmation inferred from URL: {page.url}")
                return True
            page.wait_for_timeout(500)
        log_info("Publish confirmation timed out.")
        try:
            timestamp = int(time.time())
            html_path = f"substack_publish_timeout_{timestamp}.html"
            Path(html_path).write_text(page.content(), encoding="utf-8")
            log_info(f"Saved HTML snapshot for manual review: {html_path}")
        except Exception as e:
            log_info(f"Failed to save HTML snapshot: {e}")
        return False


    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    markdown = md_path.read_text(encoding="utf-8")
    title, body = extract_title_and_body(markdown)

    print_header_once = True  # optional: just here if you want to debug the match
    image_inserted = False
    log_info(f"Preparing to post. publish={publish}, md_path={md_path}, cover_path={cover_path}")
    log_info(f"Parsed title length={len(title)}, body length={len(body)}")

    with sync_playwright() as p:
        log_info("Launching browser for Substack editor...")
        browser = p.chromium.launch(headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        if not actual_session.exists():
            raise RuntimeError(f"Substack session file not found: {actual_session}")
        log_info(f"Using session file: {actual_session}")
        context = browser.new_context(storage_state=actual_session)
        page = context.new_page()

        log_info(f"Opening editor URL: {actual_url}")
        page.goto(actual_url)
        try:
            page.wait_for_selector("textarea[placeholder='Title']", timeout=15000)
        except Exception as e:
            log_info(f"Failed to find title field: {e}")
            page.screenshot(path="substack_title_missing.png", full_page=True)
            raise e
        log_info(f"Editor loaded. Current URL: {page.url}")
        log_info(f"Writing title: {title}")
        page.fill("textarea[placeholder='Title']", title)

        log_info("Writing body...")
        get_editor_locator(page).click()
        for paragraph in body.split("\n\n"):
            for raw_line in paragraph.splitlines():
                line = raw_line.strip()

                # Insert image immediately BEFORE typing the "### Top stories" header
                if (not image_inserted) and TOP_STORIES_H3_RE.match(line):
                    print("🪄 Found '### Top stories' — inserting cover image just before it...")

                    # 1) Insert the image at current caret position
                    insert_image_via_toolbar(page, cover_path)

                    # 2) Wait for image to fully upload (not just appear in DOM)
                    log_info("Waiting for image upload to complete...")
                    time.sleep(10)

                    # 3) Place caret after the image using JS
                    result = place_caret_after_last_image(page)
                    time.sleep(1)

                    # 4) If JS placement worked, just press Enter to create new line for content
                    if result == "ok":
                        page.keyboard.press("End")  # ensure we're at end of line
                        page.keyboard.press("Enter")
                    else:
                        # Fallback: click below image and navigate
                        log_info(f"Caret placement returned {result}, using fallback")
                        get_editor_locator(page).click()
                        page.keyboard.press("End")
                        page.keyboard.press("Enter")

                    time.sleep(1)
                    image_inserted = True
                    # (now typing continues and the very next line you type will be the H3 header)

                # Bullets -> dot
                if line.startswith("- "):
                    fast_type(page, "• ")
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
                        fast_type(page, before)

                    # Your old, working popup flow
                    
                    page.keyboard.down(LINK_MOD)
                    page.keyboard.press("KeyK")
                    page.keyboard.up(LINK_MOD)
                    time.sleep(0.2)
                    fast_type(page, label)
                    page.keyboard.press("Tab")
                    time.sleep(0.2)
                    fast_type(page, url)
                    time.sleep(0.2)
                    page.keyboard.press("Enter")
                    time.sleep(0.2)
                    page.keyboard.press("ArrowRight")

                    pos = end


                if pos < len(line):
                    remaining = line[pos:]
                    if remaining.startswith("#"):
                        rule_type(page, remaining)
                    else:
                        fast_type(page, remaining)

                page.keyboard.press("Enter")
        page.keyboard.press("Enter")
        log_info("Body entry complete.")
        log_info("Validating editor content...")
        try:
            validate_editor_content(page, title, body)
            log_info("Editor content validated.")
        except Exception as e:
            log_info(f"Editor content validation failed: {e}")
            page.screenshot(path="substack_content_validation_failed.png", full_page=True)
            raise
        # If we never saw the header, you can optionally insert at top/end:
        # if not image_inserted:
        #     print("ℹ️ '### Top stories' not found — inserting image at top.")
        #     page.keyboard.press("Home")
        #     insert_image_via_toolbar(page, cover_path)

        # Add a short delay before UI interaction
        page.wait_for_timeout(1000)
        try:
            # Open the Button dropdown
            page.click("button:has-text('Button')")
            # Click "Subscribe with caption"
            page.click("text=Subscribe w/ caption")
            log_info("Subscribe button inserted.")
        except Exception as e:
            log_info(f"Subscribe button insertion failed: {e}")

        if publish:
            log_info("Publish requested; attempting to publish.")
            try:
                log_info("Clicking Continue...")
                page.wait_for_timeout(500)
                page.click("text=Continue", timeout=5000)
                log_info("Clicking Send to everyone now...")
                page.wait_for_timeout(1000)
                page.click("text=Send to everyone now", timeout=5000)
                if not wait_for_publish_success(page, timeout_s=30):
                    raise RuntimeError("Publish flow did not confirm success before timeout.")
                log_info(f"Publish flow complete. Current URL: {page.url}")
                print("✅ Post published.")
                browser.close()
                return True
            except Exception as e:
                log_info(f"Publish flow failed: {e}")
                page.screenshot(path="substack_publish_failed.png", full_page=True)
                print("⚠️ Could not find Publish button — post might already be published.")
        else:
            log_info("Draft mode: waiting for auto-save (including image upload)...")
            page.wait_for_timeout(10000)
            log_info(f"Draft saved (not published). Current URL: {page.url}")
            print("✅ Draft saved (not published).")

        browser.close()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post a markdown file to Substack.")
    parser.add_argument("md_path", type=Path, help="Path to the markdown file")
    parser.add_argument("--publish", action="store_true", help="Actually publish instead of saving as draft")
    
    args = parser.parse_args()
    post_to_substack(args.md_path, publish=args.publish)
