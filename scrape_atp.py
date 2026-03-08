"""
sincaraz.app — ATP Stats Scraper (v2 — fixed selectors)
Uses Playwright + regex to extract stats reliably.
Runs daily via GitHub Actions.
"""

import asyncio
import json
import re
import os
from datetime import datetime, timezone
from playwright.async_api import async_playwright

PLAYERS = {
    "sinner": "https://www.atptour.com/en/players/jannik-sinner/s0ag/overview",
    "alcaraz": "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/overview",
}

async def scrape_player(page, url, name):
    print(f"Scraping {name} from {url}")
    stats = {}

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        html = await page.content()

        # Career W/L — ATP embeds this as e.g. "328-88" or "328–88" near "Career"
        # Try multiple dash variants
        wl_patterns = [
            r'(\d{3,4})[–\u2013\-](\d{2,3})',
        ]
        found_wl = False
        for pat in wl_patterns:
            for m in re.finditer(pat, html):
                w, l = int(m.group(1)), int(m.group(2))
                if 150 < w < 700 and 40 < l < 250:
                    stats["career_wins"] = w
                    stats["career_losses"] = l
                    stats["career_wl"] = f"{w}\u2013{l}"
                    stats["career_win_pct"] = round(w / (w + l) * 100, 1)
                    found_wl = True
                    break
            if found_wl:
                break

        # Ranking — look for digits near "rank" in JSON blobs
        rank_m = re.search(r'"ranking"\s*:\s*["\']?(\d+)["\']?', html, re.IGNORECASE)
        if rank_m:
            stats["ranking"] = int(rank_m.group(1))

        # Titles
        title_m = re.search(r'"titles"\s*:\s*["\']?(\d+)["\']?', html, re.IGNORECASE)
        if title_m:
            stats["titles"] = int(title_m.group(1))

        # Prize money
        prize_m = re.search(r'\$([0-9,]+(?:\.\d+)?)\s*M', html)
        if prize_m:
            stats["prize_money"] = "$" + prize_m.group(1) + "M"

        # Slams — look for Grand Slam count
        slam_m = re.search(r'Grand Slam[^0-9]*(\d)', html, re.IGNORECASE)
        if slam_m:
            stats["grand_slams"] = int(slam_m.group(1))

    except Exception as e:
        print(f"  ERROR scraping {name}: {e}")

    print(f"  {name}: {stats}")
    return stats


async def main():
    scraped = {
        "sinner": {},
        "alcaraz": {},
        "scraped_at": datetime.now(timezone.utc).isoformat()
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = await context.new_page()

        for player_name, url in PLAYERS.items():
            stats = await scrape_player(page, url, player_name)
            scraped[player_name] = stats

        await browser.close()

    with open("scraped_stats.json", "w") as f:
        json.dump(scraped, f, indent=2)

    print("\n=== FINAL SCRAPED DATA ===")
    print(json.dumps(scraped, indent=2))

    update_html(scraped)


def update_html(scraped):
    if not os.path.exists("index.html"):
        print("index.html not found — skipping")
        return

    with open("index.html", "r") as f:
        html = f.read()

    sinner = scraped.get("sinner", {})
    alcaraz = scraped.get("alcaraz", {})

    # Update career W/L in profile cards
    if sinner.get("career_wl"):
        wl = sinner["career_wl"]
        html = re.sub(
            r'(Career W/L</span><span class="ps-val">)[\d\u2013\-]+(</span>)',
            lambda m, wl=wl: m.group(1) + wl + m.group(2),
            html, count=1
        )
        print(f"Set Sinner W/L = {wl}")

    if alcaraz.get("career_wl"):
        wl = alcaraz["career_wl"]
        matches = list(re.finditer(r'(Career W/L</span><span class="ps-val">)[\d\u2013\-]+(</span>)', html))
        if len(matches) >= 2:
            m = matches[1]
            html = html[:m.start()] + m.group(1) + wl + m.group(2) + html[m.end():]
            print(f"Set Alcaraz W/L = {wl}")

    # Update last-updated date
    today = datetime.now(timezone.utc).strftime("%-d %B %Y")
    html = re.sub(r'Last updated: [^<"]+', f'Last updated: {today}', html)
    print(f"Set last updated = {today}")

    with open("index.html", "w") as f:
        f.write(html)
    print("index.html saved.")


if __name__ == "__main__":
    asyncio.run(main())
