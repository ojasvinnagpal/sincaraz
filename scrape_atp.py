"""
sincaraz.app — ATP Stats Scraper v8
Loads the ATP player stats page like a real user (passes Cloudflare),
then intercepts the internal JSON API calls the Angular app makes.
We know exactly which URLs to listen for from our earlier debugging.
"""

import asyncio
import json
import re
import os
from datetime import datetime, timezone
from playwright.async_api import async_playwright

PLAYERS = {
    "sinner":  {"id": "s0ag", "name": "Jannik Sinner",   "page": "https://www.atptour.com/en/players/jannik-sinner/s0ag/player-stats"},
    "alcaraz": {"id": "a0e2", "name": "Carlos Alcaraz",  "page": "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats"},
}

async def scrape_player(context, player_key):
    pid  = PLAYERS[player_key]["id"]
    name = PLAYERS[player_key]["name"]
    url  = PLAYERS[player_key]["page"]

    captured = {}

    async def handle_response(response):
        r_url = response.url
        # Only intercept the two ATP internal endpoints we care about
        if f"/players/hero/{pid}" in r_url or f"/stats/{pid}/" in r_url:
            try:
                data = await response.json()
                captured[r_url] = data
                print(f"  ✓ Captured: ...{r_url[-60:]}")
            except Exception:
                pass

    page = await context.new_page()
    page.on("response", handle_response)

    print(f"  Loading {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception:
        await page.wait_for_timeout(8000)

    await page.close()

    # Parse what we captured
    stats = {}
    for r_url, data in captured.items():
        if f"/players/hero/{pid}" in r_url:
            w = data.get("SglCareerWon", 0)
            l = data.get("SglCareerLost", 0)
            stats["career_wins"]      = w
            stats["career_losses"]    = l
            stats["career_wl"]        = f"{w}\u2013{l}"
            stats["career_win_pct"]   = round(w / (w + l) * 100, 1) if (w + l) else None
            stats["career_titles"]    = data.get("SglCareerTitles")
            stats["ranking"]          = data.get("SglRank")
            stats["career_high_rank"] = data.get("SglHiRank")
            stats["ytd_wins"]         = data.get("SglYtdWon")
            stats["ytd_losses"]       = data.get("SglYtdLost")
            stats["ytd_titles"]       = data.get("SglYtdTitles")
            stats["prize_ytd"]        = data.get("SglYtdPrizeFormatted")
            stats["prize_career"]     = data.get("CareerPrizeFormatted")
            stats["coach"]            = data.get("Coach")
            stats["turned_pro"]       = data.get("ProYear")
            print(f"  {name}: {w}–{l}, rank #{stats['ranking']}, {stats['prize_career']}")

        elif f"/stats/{pid}/" in r_url:
            s   = data.get("Stats", {})
            svc = s.get("ServiceRecordStats", {})
            ret = s.get("ReturnRecordStats", {})
            # Determine surface from URL
            surface = "career"
            for surf in ["hard", "clay", "grass"]:
                if f"/{surf}?" in r_url or r_url.endswith(f"/{surf}"):
                    surface = f"surface_{surf}"
                    break
            stats[surface] = {
                "aces":                   svc.get("Aces"),
                "double_faults":          svc.get("DoubleFaults"),
                "first_serve_pct":        svc.get("FirstServePercentage"),
                "first_serve_won_pct":    svc.get("FirstServePointsWonPercentage"),
                "second_serve_won_pct":   svc.get("SecondServePointsWonPercentage"),
                "bp_saved_pct":           svc.get("BreakPointsSavedPercentage"),
                "bp_faced":               svc.get("BreakPointsFaced"),
                "service_games_won_pct":  svc.get("ServiceGamesWonPercentage"),
                "service_points_won_pct": svc.get("ServicePointsWonPercentage"),
                "first_return_won_pct":   ret.get("FirstServeReturnPointsWonPercentage"),
                "second_return_won_pct":  ret.get("SecondServeReturnPointsWonPercentage"),
                "bp_opportunities":       ret.get("BreakPointsOpportunities"),
                "bp_converted_pct":       ret.get("BreakPointsConvertedPercentage"),
                "return_games_won_pct":   ret.get("ReturnGamesWonPercentage"),
                "return_points_won_pct":  ret.get("ReturnPointsWonPercentage"),
                "total_points_won_pct":   ret.get("TotalPointsWonPercentage"),
            }
            print(f"  {name} {surface}: aces={svc.get('Aces')}, "
                  f"1st serve={svc.get('FirstServePercentage')}%, "
                  f"bp_conv={ret.get('BreakPointsConvertedPercentage')}%")

    if not stats:
        print(f"  WARNING: No data captured for {name} — Cloudflare may have blocked the page load")

    return stats


def update_html(scraped):
    if not os.path.exists("index.html"):
        print("index.html not found — skipping")
        return

    with open("index.html", "r") as f:
        html = f.read()
    original = html

    def replace_nth(html, pattern, replacement, n=1):
        matches = list(re.finditer(pattern, html))
        if len(matches) >= n:
            m = matches[n - 1]
            return html[:m.start()] + m.group(1) + str(replacement) + m.group(2) + html[m.end():]
        return html

    sinner  = scraped.get("sinner", {})
    alcaraz = scraped.get("alcaraz", {})

    pat = r'(Career W/L</span><span class="ps-val">)[\d\u2013\-]+(</span>)'
    if sinner.get("career_wl"):
        html = replace_nth(html, pat, sinner["career_wl"], 1)
        print(f"  Sinner W/L → {sinner['career_wl']}")
    if alcaraz.get("career_wl"):
        html = replace_nth(html, pat, alcaraz["career_wl"], 2)
        print(f"  Alcaraz W/L → {alcaraz['career_wl']}")

    pat = r'(Win Ratio</span><span class="ps-val">)[\d.]+%(</span>)'
    if sinner.get("career_win_pct"):
        html = replace_nth(html, pat, f"{sinner['career_win_pct']}%", 1)
    if alcaraz.get("career_win_pct"):
        html = replace_nth(html, pat, f"{alcaraz['career_win_pct']}%", 2)

    pat = r'(Titles</span><span class="ps-val">)\d+(</span>)'
    if sinner.get("career_titles"):
        html = replace_nth(html, pat, sinner["career_titles"], 1)
    if alcaraz.get("career_titles"):
        html = replace_nth(html, pat, alcaraz["career_titles"], 2)

    pat = r'(Prize Money</span><span class="ps-val">)[^<]+(</span>)'
    if sinner.get("prize_career"):
        html = replace_nth(html, pat, sinner["prize_career"], 1)
    if alcaraz.get("prize_career"):
        html = replace_nth(html, pat, alcaraz["prize_career"], 2)

    today = datetime.now(timezone.utc).strftime("%-d %B %Y")
    html = re.sub(r'Last updated: [^<"]+', f'Last updated: {today}', html)

    if html != original:
        with open("index.html", "w") as f:
            f.write(html)
        print(f"  index.html saved ({today})")
    else:
        print("  index.html unchanged — check ps-val class names match your HTML")


async def main():
    print(f"=== sincaraz scraper v8 — {datetime.now(timezone.utc).isoformat()} ===\n")

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "method": "atp-xhr-intercept"
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for i, key in enumerate(["sinner", "alcaraz"]):
            print(f"\n--- {PLAYERS[key]['name']} ---")
            if i > 0:
                print("  Waiting 8s before next player...")
                await asyncio.sleep(8)

            # Fresh browser context per player — avoids Cloudflare token exhaustion
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                viewport={"width": 1280, "height": 800},
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)
            result[key] = await scrape_player(context, key)
            if not result[key]:
                print("  No data — retrying in 10s...")
                await asyncio.sleep(10)
                result[key] = await scrape_player(context, key)
            await context.close()

        await browser.close()

    print("\n=== SUMMARY ===")
    for key in ["sinner", "alcaraz"]:
        d = result.get(key, {})
        print(f"  {key}: W/L={d.get('career_wl')}, rank={d.get('ranking')}, "
              f"aces={d.get('career', {}).get('aces')}")

    with open("scraped_stats.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved scraped_stats.json")

    print("\nUpdating index.html...")
    update_html(result)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
