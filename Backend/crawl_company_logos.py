import json

from playwright.sync_api import sync_playwright

URL = "https://sharehubnepal.com/nepse/listed-securities"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(URL, wait_until="domcontentloaded")

    page.wait_for_selector(
        "table tbody tr td img",
        timeout=30000
    )

    input(
        "In the browser, set 'Items Per Page' to the largest value, "
        "scroll to the bottom, wait for the table to finish loading, "
        "then press Enter here... "
    )

    # Give ShareHub time to finish reloading/re-rendering
    page.wait_for_timeout(5000)

    # Wait until table rows are available again
    page.wait_for_selector(
        "table tbody tr",
        timeout=30000
    )

    rows = page.eval_on_selector_all(
        "table tbody tr",
        """trs => trs.map(tr => {
            const img = tr.querySelector('img');
            const cells = tr.querySelectorAll('td');

            return {
                symbol: cells.length
                    ? cells[0].innerText.trim().split(/\\s+/)[0]
                    : '',
                logo_url: img
                    ? (img.currentSrc || img.src)
                    : ''
            };
        })"""
    )

    browser.close()

rows = [
    r for r in rows
    if r["symbol"] and r["logo_url"]
]

with open("company_logos.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2)

print(f"Saved {len(rows)} companies")