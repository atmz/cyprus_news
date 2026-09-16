"""Like login_to_ss.py, but needs no stdin: opens a headed browser on the
Substack sign-in page, polls for the auth cookie, and saves the session
automatically once you're logged in. Safe to run via the `!` prompt runner.
"""
import time

from playwright.sync_api import sync_playwright

TIMEOUT_S = 600  # give up after 10 minutes

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    )
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://substack.com/sign-in")
    print("👉 Log in in the browser window. The session saves itself — no keypress needed.")

    deadline = time.time() + TIMEOUT_S
    logged_in = False
    while time.time() < deadline:
        if any(c["name"] == "substack.sid" for c in context.cookies()):
            logged_in = True
            break
        time.sleep(3)

    if not logged_in:
        raise SystemExit("❌ Timed out waiting for login — session file NOT updated.")

    time.sleep(5)  # let post-login redirects and cookie refreshes settle
    context.storage_state(path="data/substack_session.json")
    print("✅ Session saved to data/substack_session.json")
    browser.close()
