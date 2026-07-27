from playwright.sync_api import sync_playwright
import urllib.parse
import time

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        url = "https://www.google.com/maps/search/" + urllib.parse.quote("tiệm sửa xe máy Tân Bình")
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(5)
        feed = page.query_selector("div[role='feed']")
        print("Feed found:", bool(feed))
        if not feed:
            page.screenshot(path="maps_debug.png")
            print("Screenshot saved to maps_debug.png")
        browser.close()

test()
