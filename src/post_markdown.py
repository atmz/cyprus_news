#!/usr/bin/env python3
"""
post_markdown.py — Post an arbitrary markdown file to Substack as a draft or published post.

Handles:
  - Headings (#, ##, ###, ...)
  - Bullet points (- item → •)
  - Inline links [label](url)
  - Paragraphs

Does NOT handle images. For the Cyprus News pipeline (with cover image insertion),
use post_to_substack.py instead.

Usage:
    python src/post_markdown.py post.md \\
        --substack-url "https://yourpub.substack.com/publish/post?type=newsletter" \\
        [--session ./data/substack_session.json] \\
        [--publish]
"""
import argparse
import re
import time
import platform
from pathlib import Path

from playwright.sync_api import sync_playwright

LINK_MOD = "Meta" if platform.system() == "Darwin" else "Control"
_markdown_link_re = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")


def extract_title_and_body(markdown_text: str) -> tuple[str, str]:
    """Return (title, body) from a markdown string.

    Title is extracted from the first '# ...' heading (stripped of leading
    '#' characters and the optional 📰 emoji).  Body is everything after
    that heading line.
    """
    lines = markdown_text.strip().splitlines()
    title = ""
    title_index = -1

    for i, line in enumerate(lines):
        if line.startswith("#"):
            title = re.sub(r"^#+\s*📰?\s*", "", line).strip()
            title_index = i
            break

    if title_index == -1:
        # No heading found — treat whole text as body
        return "", markdown_text.strip()

    body = "\n".join(lines[title_index + 1:]).strip()
    return title, body


def post_markdown(
    md_path: Path,
    substack_url: str,
    session_file: Path,
    publish: bool = False,
) -> bool:
    """Post *md_path* to Substack.

    Returns True if the post was published (publish=True and confirmed),
    False otherwise (draft saved or publish unconfirmed).
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")
    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    markdown = md_path.read_text(encoding="utf-8")
    title, body = extract_title_and_body(markdown)
    print(f"Title ({len(title)} chars): {title!r}")
    print(f"Body: {len(body)} chars")

    def log(msg: str):
        print(f"[substack] {msg}")

    def fast_type(page, text: str):
        if text:
            page.keyboard.insert_text(text)

    def rule_type(page, text: str):
        """Type text character-by-character to trigger editor markdown shortcuts."""
        if text:
            page.keyboard.type(text)

    def insert_link(page, label: str, url: str):
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

    def dismiss_error_dialog(page) -> bool:
        """Dismiss 'Draft not saved' / 'Post out of date' modal. Returns True if found."""
        for sel in ["text=Draft not saved", "text=Post out of date"]:
            try:
                if page.locator(sel).first.is_visible(timeout=1000):
                    log(f"Error dialog detected ({sel}), dismissing...")
                    ok = page.locator("button:has-text('OK'), button:has-text('Ok')").first
                    if ok.is_visible(timeout=2000):
                        ok.click()
                        page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
        return False

    def wait_for_success(page, timeout_s: int = 60) -> bool:
        deadline = time.time() + timeout_s
        success_texts = ["Published", "Your post is published", "View post", "Sent to everyone"]
        while time.time() < deadline:
            for text in success_texts:
                if page.locator(f"text={text}").first.is_visible():
                    log(f"Publish confirmed: {text!r}")
                    return True
            if "/publish/" not in page.url:
                log(f"Publish confirmed via URL: {page.url}")
                return True
            page.wait_for_timeout(500)
        log("Publish confirmation timed out.")
        try:
            snap = f"post_markdown_timeout_{int(time.time())}.html"
            Path(snap).write_text(page.content(), encoding="utf-8")
            log(f"Saved HTML snapshot: {snap}")
        except Exception:
            pass
        return False

    def publish_with_retry(page, max_attempts: int = 3) -> bool:
        """Attempt to publish, handling 'Post out of date' errors with reload+retry."""
        for attempt in range(max_attempts):
            if attempt > 0:
                log(f"Retry {attempt + 1}/{max_attempts} — reloading to sync draft...")
                page.reload()
                try:
                    page.wait_for_selector("textarea[placeholder='Title']", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)

            dismiss_error_dialog(page)
            page.wait_for_timeout(2000)

            try:
                log("Clicking Continue...")
                page.click("text=Continue", timeout=10000)
            except Exception as e:
                log(f"Could not click Continue (attempt {attempt + 1}): {e}")
                if attempt < max_attempts - 1:
                    continue
                raise

            page.wait_for_timeout(1000)
            dismiss_error_dialog(page)

            try:
                log("Clicking Send to everyone now...")
                page.click("text=Send to everyone now", timeout=10000)
            except Exception as e:
                log(f"Could not click 'Send to everyone now' (attempt {attempt + 1}): {e}")
                if attempt < max_attempts - 1:
                    continue
                raise

            page.wait_for_timeout(1500)

            if dismiss_error_dialog(page):
                log("'Post out of date' after clicking send — will reload and retry...")
                if attempt < max_attempts - 1:
                    continue
                return False

            if wait_for_success(page, timeout_s=60):
                return True

            log(f"Publish confirmation not received on attempt {attempt + 1}")
            if attempt < max_attempts - 1:
                continue

        return False

    with sync_playwright() as p:
        log("Launching browser...")
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(storage_state=session_file)
        page = context.new_page()

        log(f"Opening editor: {substack_url}")
        page.goto(substack_url)
        try:
            page.wait_for_selector("textarea[placeholder='Title']", timeout=15000)
        except Exception as e:
            page.screenshot(path="post_markdown_error.png", full_page=True)
            raise RuntimeError(f"Substack editor did not load. Screenshot saved. Error: {e}")

        log(f"Editor loaded. Setting title: {title!r}")
        page.fill("textarea[placeholder='Title']", title)

        log("Typing body...")
        editor = page.locator("[data-testid='editor'], div.ProseMirror").first
        editor.click()

        for paragraph in body.split("\n\n"):
            for raw_line in paragraph.splitlines():
                line = raw_line.strip()

                if line.startswith("- "):
                    fast_type(page, "• ")
                    line = line[2:].strip()

                pos = 0
                for m in _markdown_link_re.finditer(line):
                    start, end = m.span()
                    before = line[pos:start]
                    if before:
                        fast_type(page, before)
                    insert_link(page, m.group(1), m.group(2))
                    pos = end

                remaining = line[pos:]
                if remaining:
                    if remaining.startswith("#"):
                        rule_type(page, remaining)
                    else:
                        fast_type(page, remaining)

                page.keyboard.press("Enter")
            page.keyboard.press("Enter")

        log("Body entry complete.")

        if publish:
            log("Waiting for auto-save to settle before publishing...")
            page.wait_for_timeout(5000)
            try:
                if publish_with_retry(page, max_attempts=3):
                    log(f"Published. Final URL: {page.url}")
                    print("✅ Post published.")
                    browser.close()
                    return True
                else:
                    raise RuntimeError("Publish did not confirm success after all retries.")
            except Exception as e:
                log(f"Publish failed: {e}")
                page.screenshot(path="post_markdown_failed.png", full_page=True)
                print("⚠️ Publish failed — see post_markdown_failed.png")
        else:
            log("Draft mode: waiting for auto-save...")
            page.wait_for_timeout(10000)
            log(f"Draft saved. URL: {page.url}")
            print("✅ Draft saved.")

        browser.close()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Post a markdown file to Substack as a draft or published post.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("md_path", type=Path, help="Path to the markdown file")
    parser.add_argument(
        "--substack-url",
        required=True,
        help='Substack publish URL, e.g. "https://yourpub.substack.com/publish/post?type=newsletter"',
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=Path("./data/substack_session.json"),
        help="Path to saved Substack session JSON (default: ./data/substack_session.json)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish immediately instead of saving as draft",
    )
    args = parser.parse_args()
    post_markdown(args.md_path, args.substack_url, args.session, publish=args.publish)
