#!/usr/bin/env python3
"""
Sincaraz ATP Scraper — Free, no AI API needed
Uses Playwright (real Chromium browser) to navigate ATP Tour pages,
waits for JS to render, then reads stats directly from the DOM.
Runs daily via GitHub Actions.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# pip install playwright && playwright install chromium
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────────────────────
# ATP page URLs
# ─────────────────────────────────────────────────────────────
PLAYERS = {
    "sinner": {
        "overview":  "https://www.atptour.com/en/players/jannik-sinner/s0ag/overview",
        "winloss":   "https://www.atptour.com/en/players/jannik-sinner/s0ag/atp-win-loss?tourType=Tour",
        "stats":     "https://www.atptour.com/en/players/jannik-sinner/s0ag/player-stats?year=0&surface=all&statsType=SERVE",
    },
    "alcaraz": {
        "overview":  "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/overview",
        "winloss":   "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/atp-win-loss?tourType=Tour",
        "stats":     "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats?year=0&surface=all&statsType=SERVE",
    },
}

# ─────────────────────────────────────────────────────────────
# Browser helpers
# ─────────────────────────────────────────────────────────────

def make_browser(p):
    """Launch Chromium with realistic settings to avoid bot detection."""
    return p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
    )

def new_page(browser):
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
    )
    page = ctx.new_page()
    # Hide webdriver flag
    page.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return page

def goto_wait(page, url: str, wait_selector: str, timeout=20000):
    """Navigate and wait for a selector to appear (content rendered)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(wait_selector, timeout=timeout)
        return True
    except PWTimeout:
        print(f"  Timeout waiting for {wait_selector} on {url}")
        return False

def text(page, selector: str, default="N/A") -> str:
    try:
        return page.inner_text(selector).strip()
    except Exception:
        return default

def texts(page, selector: str) -> list[str]:
    try:
        return [el.inner_text().strip() for el in page.query_selector_all(selector)]
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────
# Scrapers
# ─────────────────────────────────────────────────────────────

def scrape_overview(page, url: str, player: str) -> dict:
    print(f"    Scraping overview: {player}")
    if not goto_wait(page, url, ".player-profile-hero-name", timeout=15000):
        return {}

    data = {}

    # Ranking
    try:
        rank_text = text(page, ".player-ranking-position .stat-value")
        data["ranking"] = f"#{rank_text}" if rank_text != "N/A" else "N/A"
    except Exception:
        pass

    # Age, nationality, height, weight from player profile
    try:
        profile_items = page.query_selector_all(".player-profile-hero-table tr")
        for row in profile_items:
            cells = row.query_selector_all("td")
            if len(cells) >= 2:
                label = cells[0].inner_text().strip().lower()
                val   = cells[1].inner_text().strip()
                if "age" in label:       data["age"] = val
                if "height" in label:    data["height"] = val
                if "weight" in label:    data["weight"] = val
                if "plays" in label:     data["plays"] = val
                if "turned pro" in label:data["turned_pro"] = val
                if "coach" in label:     data["coach"] = val
    except Exception:
        pass

    # Career stats summary cards
    try:
        stat_cards = page.query_selector_all(".player-profile-hero-stats .stat-value")
        stat_labels = page.query_selector_all(".player-profile-hero-stats .stat-label")
        for val_el, lbl_el in zip(stat_cards, stat_labels):
            val = val_el.inner_text().strip()
            lbl = lbl_el.inner_text().strip().lower()
            if "title" in lbl:           data["titles"] = val
            if "prize" in lbl:           data["prize_money"] = val
            if "win" in lbl and "%" in val: data["career_pct"] = val
    except Exception:
        pass

    print(f"    Overview data: {data}")
    return data


def scrape_winloss(page, url: str, player: str) -> dict:
    print(f"    Scraping win/loss: {player}")
    if not goto_wait(page, url, ".player-stats-table", timeout=15000):
        return {}

    data = {}

    try:
        # The ATP Win/Loss Index table — rows are: Overall, Grand Slams, Masters 1000, etc.
        rows = page.query_selector_all(".player-stats-table tbody tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if not cells:
                continue
            label = cells[0].inner_text().strip().lower()
            # Career W/L is in "Career W/L" column (index 2 or 3)
            if len(cells) >= 4:
                career_wl = cells[2].inner_text().strip()  # Career W/L column
                career_idx = cells[3].inner_text().strip() # Career index

                if label == "overall":
                    data["career_wl"] = career_wl
                    data["career_index"] = career_idx
                elif "grand slam" in label:
                    data["slam_wl"] = career_wl
                elif "masters 1000" in label:
                    data["masters_wl"] = career_wl
                elif "tie break" in label or "tiebreak" in label:
                    data["tiebreak_wl"] = career_wl
                    data["tiebreak_pct"] = career_idx
                elif "deciding set" in label:
                    data["deciding_set_wl"] = career_wl
                elif "5th set" in label:
                    data["fifth_set_wl"] = career_wl
                elif "final" in label:
                    data["finals_wl"] = career_wl
                elif "top 10" in label:
                    data["top10_wl"] = career_wl
                elif "clay" in label:
                    data["clay_wl"] = career_wl
                elif "grass" in label:
                    data["grass_wl"] = career_wl
                elif "hard" in label and "indoor" not in label:
                    data["hard_wl"] = career_wl
                elif "indoor" in label:
                    data["indoor_wl"] = career_wl

    except Exception as e:
        print(f"    Win/loss table error: {e}")

    print(f"    WL data: {data}")
    return data


def scrape_serve_stats(page, url: str, player: str) -> dict:
    print(f"    Scraping serve stats: {player}")
    if not goto_wait(page, url, ".player-stats-table", timeout=15000):
        return {}

    data = {}

    try:
        rows = page.query_selector_all(".player-stats-table tbody tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].inner_text().strip().lower()
            # Career value is in last or second-to-last column
            career_val = cells[-1].inner_text().strip()

            if "1st serve %" in label:        data["first_serve_pct"] = career_val
            elif "1st serve points won" in label: data["first_serve_pts_won"] = career_val
            elif "2nd serve points won" in label: data["second_serve_pts_won"] = career_val
            elif "aces" in label:              data["aces_per_match"] = career_val
            elif "double fault" in label:      data["df_per_match"] = career_val
            elif "break points saved" in label: data["bp_saved_pct"] = career_val
            elif "service games won" in label:  data["service_games_won"] = career_val
    except Exception as e:
        print(f"    Serve stats error: {e}")

    print(f"    Serve data: {data}")
    return data

# ─────────────────────────────────────────────────────────────
# HTML updater
# ─────────────────────────────────────────────────────────────

def update_profile_stat(html: str, player_class: str, label: str, new_val: str) -> tuple[str, bool]:
    """Update a stat in a specific player's profile card."""
    # Find the player's card section
    start = html.find(f'profile-card {player_class}')
    if start == -1:
        start = html.find(f'class="{player_class}"')
    if start == -1:
        return html, False

    # Find next profile-card as end boundary
    end = html.find('profile-card', start + 20)
    if end == -1:
        end = len(html)

    segment = html[start:end]
    pattern = (
        r'(<span class="ps-label">' + re.escape(label) +
        r'</span><span class="ps-val">)[^<]+(</span>)'
    )
    new_seg, n = re.subn(pattern, r'\g<1>' + re.escape(new_val) + r'\2', segment)
    if n > 0:
        return html[:start] + new_seg + html[end:], True
    return html, False


def update_all_stats(html: str, sinner: dict, alcaraz: dict) -> tuple[str, list]:
    """Apply all scraped stats to the HTML."""
    changes = []

    # Map: (html_label, sinner_dict_key, alcaraz_dict_key)
    profile_fields = [
        ("Career W/L",   "career_wl",    "career_wl"),
        ("Titles",       "titles",       "titles"),
        ("Prize Money",  "prize_money",  "prize_money"),
        ("Coach",        "coach",        "coach"),
        ("Age",          "age",          "age"),
        ("Height",       "height",       "height"),
    ]

    for label, s_key, a_key in profile_fields:
        s_val = sinner.get(s_key)
        a_val = alcaraz.get(a_key)
        if s_val and s_val != "N/A":
            html, changed = update_profile_stat(html, "sinner", label, s_val)
            if changed:
                changes.append(f"Sinner {label}: {s_val}")
        if a_val and a_val != "N/A":
            html, changed = update_profile_stat(html, "alcaraz", label, a_val)
            if changed:
                changes.append(f"Alcaraz {label}: {a_val}")

    # Update comparison table rows
    comp_updates = [
        ("Career Win/Loss", sinner.get("career_wl"), alcaraz.get("career_wl")),
    ]
    for row_label, s_val, a_val in comp_updates:
        if s_val and a_val:
            pattern = re.compile(
                r'(<td>' + re.escape(row_label) + r'</td>\s*<td class="sv">)[^<]+(</td>\s*<td class="av">)[^<]+(</td>)'
            )
            html, n = pattern.subn(
                r'\g<1>' + s_val + r'\2' + a_val + r'\3', html
            )
            if n:
                changes.append(f"Table {row_label}: {s_val} / {a_val}")

    # Inject rankings into hero area
    for player, data, flag in [("sinner", sinner, "🇮🇹 Italy"), ("alcaraz", alcaraz, "🇪🇸 Spain")]:
        rank = data.get("ranking")
        if rank and rank != "N/A":
            rank_num = rank.replace("#", "")
            old = re.compile(r'(' + re.escape(flag) + r' · World No\. )\d+')
            new_html = old.sub(r'\g<1>' + rank_num, html)
            if new_html != html:
                html = new_html
                changes.append(f"{player.title()} ranking: #{rank_num}")

    # Update timestamp
    ts = datetime.now(timezone.utc).strftime("%-d %B %Y")
    html = re.sub(
        r'(id="last-updated"[^>]*>)[^<]*(</)',
        r'\g<1>Stats updated: ' + ts + r'\2',
        html
    )

    return html, changes

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"Sincaraz ATP Scraper  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}\n")

    sinner_data  = {}
    alcaraz_data = {}

    with sync_playwright() as p:
        browser = make_browser(p)

        try:
            # ── Sinner ──
            print("▶ Scraping Sinner...")
            page = new_page(browser)
            sinner_data.update(scrape_overview(page,  PLAYERS["sinner"]["overview"],  "sinner"))
            page.close()

            page = new_page(browser)
            sinner_data.update(scrape_winloss(page,   PLAYERS["sinner"]["winloss"],   "sinner"))
            page.close()

            page = new_page(browser)
            sinner_data.update(scrape_serve_stats(page, PLAYERS["sinner"]["stats"],   "sinner"))
            page.close()

            # ── Alcaraz ──
            print("▶ Scraping Alcaraz...")
            page = new_page(browser)
            alcaraz_data.update(scrape_overview(page,  PLAYERS["alcaraz"]["overview"],  "alcaraz"))
            page.close()

            page = new_page(browser)
            alcaraz_data.update(scrape_winloss(page,   PLAYERS["alcaraz"]["winloss"],   "alcaraz"))
            page.close()

            page = new_page(browser)
            alcaraz_data.update(scrape_serve_stats(page, PLAYERS["alcaraz"]["stats"],   "alcaraz"))
            page.close()

        finally:
            browser.close()

    # Save scraped data as JSON (useful for debugging)
    out = {"sinner": sinner_data, "alcaraz": alcaraz_data,
           "scraped_at": datetime.now(timezone.utc).isoformat()}
    Path("scraped_stats.json").write_text(json.dumps(out, indent=2))
    print(f"\nScraped JSON saved to scraped_stats.json")

    # Load HTML
    html_path = Path("index.html")
    if not html_path.exists():
        print("ERROR: index.html not found. Run from repo root.")
        sys.exit(1)

    html = html_path.read_text(encoding="utf-8")
    original = html

    # Apply updates
    print("\nApplying updates to index.html...")
    html, changes = update_all_stats(html, sinner_data, alcaraz_data)

    if html != original:
        html_path.write_text(html, encoding="utf-8")
        print(f"\n✅ Updated index.html with {len(changes)} change(s):")
        for c in changes:
            print(f"  • {c}")
    else:
        print("\n⚪ No changes — stats are already current.")

    print(f"\nDone at {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n")


if __name__ == "__main__":
    main()
