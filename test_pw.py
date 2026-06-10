from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://people.com/video")
    page.wait_for_selector("a[href*='/']")
    links = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(href => href.includes('people.com') && !href.includes('/video/'))")
    print("Links found:")
    for link in list(set(links))[:5]:
        print(link)
    browser.close()
