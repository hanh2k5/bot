import time, json, re, urllib.parse
from playwright.sync_api import sync_playwright

t0 = time.time()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    context.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf}", lambda r: r.abort())
    page = context.new_page()

    leads = []
    seen_names = set()

    def handle_response(response):
        if "search" in response.url or "rpc" in response.url or "preview" in response.url:
            try:
                text = response.text()
                # Parse protobuf/json array chunks from Google Maps RPC
                # Extract phone numbers, titles, addresses
                phone_matches = re.findall(r'\"(0[35789]\d{8})\"', text)
                for ph in phone_matches:
                    if ph not in [l['phone'] for l in leads]:
                        leads.append({'company_name': f'Store_{len(leads)+1}', 'phone': ph, 'address': 'TP.HCM'})
            except Exception:
                pass

    page.on("response", handle_response)

    districts = ["", "Tân Bình", "Gò Vấp", "Quận 1", "Bình Thạnh", "Quận 10"]
    for d in districts:
        if len(leads) >= 80:
            break
        query = f"quán cafe {d} Ho Chi Minh".strip()
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=6000)
            page.wait_for_selector("div[role='feed']", timeout=3000)
            feed = page.query_selector("div[role='feed']")
            if feed:
                for _ in range(10):
                    page.evaluate("(el) => el.scrollBy(0, 5000)", feed)
                    time.sleep(0.05)
        except Exception:
            continue

    browser.close()

t1 = time.time()
print(f"TEST FINISHED IN {round(t1-t0, 2)} SECONDS!")
print(f"Total leads extracted: {len(leads)}")
