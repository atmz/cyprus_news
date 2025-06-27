from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://substack.com/sign-in")
    print("👉 Please log in manually. Close the browser when done.")

    # Wait for manual login and CAPTCHA
    input("Press Enter after logging in...")

    # Save session for reuse
    context.storage_state(path="substack_session.json")
    browser.close()
