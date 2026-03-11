"""
sincaraz.app — Vision-based ATP Stats Scraper
Strategy: Take screenshots of ATP stats pages, send to Claude Vision to extract
all stat values as structured JSON.

This is the fallback if API intercept doesn't work — it works on ANY website
since it reads the page like a human would, but costs ~$0.01/run.

Run: python scrape_vision.py
Requires: pip install playwright anthropic
"""

import asyncio
import base64
import json
import os
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright
import anthropic

ATP_PAGES = {
    "sinner": "https://www.atptour.com/en/players/jannik-sinner/s0ag/player-stats",
    "alcaraz": "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats",
}

VISION_PROMPT = """
You are looking at a screenshot of an ATP Tour player stats page for {player_name}.

Extract ALL visible statistics as a JSON object. Include every number you can see, such as:
- serve stats: service_games_won_pct, total_service_points_won_pct, aces, double_faults,
  first_serve_in_pct, first_serve_points_won_pct, second_serve_points_won_pct,
  break_points_saved_pct, break_points_faced
- return stats: return_games_won_pct, return_points_won_pct, total_points_won_pct,
  first_serve_return_won_pct, second_serve_return_won_pct,
  break_points_converted_pct, break_point_opportunities
- overview: ranking, career_wl, ytd_wl, titles, prize_money
- any other stat visible on the page

Return ONLY valid JSON, nothing else. Use snake_case keys.
If a stat is not visible (e.g. still loading), omit it.
Example format:
{
  "service_games_won_pct": 88.5,
  "aces": 312,
  "first_serve_in_pct": 64.2,
  ...
}
"""

async def take_screenshots(player_name, url):
    """Take full-page screenshot of the ATP stats page."""
    screenshots = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print(f"  Loading {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception:
            await page.wait_for_timeout(12000)

        # Take screenshot of visible viewport first
        path1 = f"/home/claude/{player_name}_viewport.png"
        await page.screenshot(path=path1)
        screenshots.append(path1)
        print(f"  Screenshot 1: {path1}")

        # Scroll down to capture stats section and take another
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(1000)
        path2 = f"/home/claude/{player_name}_scrolled.png"
        await page.screenshot(path=path2)
        screenshots.append(path2)
        print(f"  Screenshot 2: {path2}")

        await browser.close()

    return screenshots


def image_to_base64(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_stats_with_vision(player_name, screenshot_paths):
    """Send screenshots to Claude Vision to extract stats as JSON."""
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

    content = []
    for path in screenshot_paths:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_to_base64(path)
            }
        })

    content.append({
        "type": "text",
        "text": VISION_PROMPT.format(player_name=player_name)
    })

    print(f"  Sending {len(screenshot_paths)} screenshots to Claude Vision...")
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text
    print(f"  Raw response: {raw[:200]}...")

    # Parse JSON from response
    try:
        # Strip markdown fences if present
        clean = re.sub(r"```json|```", "", raw).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"  JSON parse error: {e}")
        return {"raw_response": raw}


async def main():
    print(f"=== sincaraz vision scraper — {datetime.now(timezone.utc).isoformat()} ===\n")

    result = {
        "sinner": {},
        "alcaraz": {},
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "method": "vision"
    }

    for player in ["sinner", "alcaraz"]:
        print(f"\n--- {player} ---")
        screenshots = await take_screenshots(player, ATP_PAGES[player])
        stats = extract_stats_with_vision(player, screenshots)
        result[player] = stats
        print(f"  Extracted {len(stats)} fields")

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2, default=str))

    with open("scraped_stats_vision.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
