"""
sincaraz.app — ATP Stats Scraper v11
Five data sources covering every stat in the master wishlist:

  1. ATP XHR intercept     → career W/L, rankings, prize money, ALL serve/return stats
                             (+ fields previously captured but not written to HTML)
  2. JeffSackmann CSV      → H2H, surface splits, YTD, sets won/lost computed
  3. Vision: ATP W/L page  → ALL situational records, ratings, vs-opponent splits
  4. Vision: Wikipedia     → Grand Slam counts per slam, weeks/days at #1, year-end rankings
  5. Vision: TennisStats   → avg match duration, wins from behind, breaks/set, streaks
  6. Vision: ATP H2H page  → match-by-match H2H results, scores, surfaces
  7. Computed              → age (live from DOB), avg aces/match, sets ratio, big titles
"""

import asyncio
import base64
import csv
import io
import json
import re
import os
import urllib.request
from datetime import datetime, date, timezone
from playwright.async_api import async_playwright
import anthropic

PLAYERS = {
    "sinner": {
        "id":          "s0ag",
        "name":        "Jannik Sinner",
        "dob":         date(2001, 8, 16),
        # H2H as of Apr 2026 — update manually after each meeting
        "h2h_wins":    6,
        "h2h_losses":  10,
        "page_stats":  "https://www.atptour.com/en/players/jannik-sinner/s0ag/player-stats",
        "page_wl":     "https://www.atptour.com/en/players/jannik-sinner/s0ag/atp-win-loss",
        "wiki_stats":  "https://en.wikipedia.org/wiki/Jannik_Sinner_career_statistics",
        "tennisstats": "https://www.flashscore.com/player/sinner-jannik/WmrNaFhB/",
    },
    "alcaraz": {
        "id":          "a0e2",
        "name":        "Carlos Alcaraz",
        "dob":         date(2003, 5, 3),
        # H2H as of Apr 2026 — update manually after each meeting
        "h2h_wins":    10,
        "h2h_losses":  6,
        "page_stats":  "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats",
        "page_wl":     "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/atp-win-loss",
        "wiki_stats":  "https://en.wikipedia.org/wiki/Carlos_Alcaraz_career_statistics",
        "tennisstats": "https://www.flashscore.com/player/alcaraz-carlos/W2Bkdnhj/",
    },
}

H2H_URL = "https://www.atptour.com/en/players/atp-head-2-head/jannik-sinner-vs-carlos-alcaraz/s0ag/a0e2"

SACKMANN_BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
SINNER_NAMES  = {"jannik sinner", "sinner j.", "sinner"}
ALCARAZ_NAMES = {"carlos alcaraz", "alcaraz c.", "alcaraz"}


# ─── Browser helpers ──────────────────────────────────────────────────────────

async def make_context(browser, wide=False):
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        viewport={"width": 1400 if wide else 1280, "height": 900},
    )
    await ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome={runtime:{}};"
    )
    return ctx


async def screenshots(page, n=3, step=700, prefix="/tmp/shot"):
    paths = []
    for i in range(n):
        await page.evaluate(f"window.scrollTo(0, {i * step})")
        await page.wait_for_timeout(700)
        p = f"{prefix}_{i}.png"
        await page.screenshot(path=p)
        paths.append(p)
    return paths


def img_blocks(paths):
    blocks = []
    for path in paths:
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        blocks.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64}})
    return blocks


def vision(img_b, prompt):
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": img_b + [{"type": "text", "text": prompt}]}],
    )
    raw = resp.content[0].text.strip()
    try:
        return json.loads(re.sub(r"```json|```", "", raw).strip())
    except Exception as e:
        print(f"  Vision JSON parse error: {e} | raw: {raw[:200]}")
        return {}


# ─── Source 1: ATP XHR ────────────────────────────────────────────────────────

async def scrape_xhr(context, key):
    pid  = PLAYERS[key]["id"]
    name = PLAYERS[key]["name"]
    url  = PLAYERS[key]["page_stats"]
    cap  = {}

    async def handle(r):
        u = r.url
        if f"/players/hero/{pid}" in u or f"/stats/{pid}/" in u:
            try:
                cap[u] = await r.json()
                print(f"    ✓ {u[-55:]}")
            except Exception:
                pass

    page = await context.new_page()
    page.on("response", handle)
    print(f"  Loading {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception:
        await page.wait_for_timeout(8000)
    await page.close()

    stats = {}
    for u, data in cap.items():
        if f"/players/hero/{pid}" in u:
            w  = data.get("SglCareerWon", 0) or 0
            l  = data.get("SglCareerLost", 0) or 0
            yw = data.get("SglYtdWon", 0) or 0
            yl = data.get("SglYtdLost", 0) or 0
            stats.update({
                "career_wins":    w,
                "career_losses":  l,
                "career_wl":      f"{w}\u2013{l}",
                "career_win_pct": round(w / (w + l) * 100, 1) if (w + l) else None,
                "career_titles":  data.get("SglCareerTitles"),
                "ranking":        data.get("SglRank"),
                "atp_points":     data.get("SglRankPts") or data.get("RankPoints") or data.get("Points"),
                "ytd_wins":       yw,
                "ytd_losses":     yl,
                "ytd_wl":         f"{yw}\u2013{yl}",
                "ytd_win_pct":    round(yw / (yw + yl) * 100, 1) if (yw + yl) else None,
                "ytd_titles":     data.get("SglYtdTitles"),
                "prize_career":   data.get("CareerPrizeFormatted"),
                "coach":          data.get("Coach"),
            })
            print(f"  {name}: {w}–{l}, #{stats['ranking']}, {stats['prize_career']}, YTD {yw}–{yl}")

        elif f"/stats/{pid}/" in u:
            s   = data.get("Stats", {})
            svc = s.get("ServiceRecordStats", {})
            ret = s.get("ReturnRecordStats", {})
            surface = "career"
            for surf in ["hard", "clay", "grass"]:
                if f"/{surf}?" in u or u.endswith(f"/{surf}"):
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
                "service_games_played":   svc.get("ServiceGamesPlayed"),
                "service_games_won_pct":  svc.get("ServiceGamesWonPercentage"),
                "service_points_won_pct": svc.get("ServicePointsWonPercentage"),
                "first_return_won_pct":   ret.get("FirstServeReturnPointsWonPercentage"),
                "second_return_won_pct":  ret.get("SecondServeReturnPointsWonPercentage"),
                "bp_converted_pct":       ret.get("BreakPointsConvertedPercentage"),
                "bp_opportunities":       ret.get("BreakPointsOpportunities"),
                "return_games_played":    ret.get("ReturnGamesPlayed"),
                "return_games_won_pct":   ret.get("ReturnGamesWonPercentage"),
                "return_points_won_pct":  ret.get("ReturnPointsWonPercentage"),
                "total_points_won_pct":   ret.get("TotalPointsWonPercentage"),
            }
    if not stats:
        print(f"  WARNING: No XHR data for {name}")
    return stats


# ─── Source 3: Vision — ATP Win/Loss Index ────────────────────────────────────

WL_PROMPT = """ATP Tour Win/Loss Index page for {name}. Extract ALL visible stats as JSON.

IMPORTANT: This page shows CAREER stats by default. Make sure you are reading the CAREER
tab/view, NOT the YTD (year to date) tab. Career overall_wl should be in the hundreds of wins.
If overall_wl shows fewer than 100 wins, you are reading the wrong tab — scroll up and find
the career totals.

RATINGS (numbers): serve_rating, return_rating, under_pressure_rating
PERCENTAGES (numbers, no % sign):
  tiebreaks_won_pct, deciding_sets_won_pct, bp_saved_pct, bp_converted_pct
  after_winning_first_set_pct, after_losing_first_set_pct
WIN-LOSS RECORDS (format "W-L") — CAREER TOTALS ONLY:
  overall_wl, finals_wl, grand_slams_wl, masters_wl
  indoor_wl, outdoor_wl, carpet_wl
  vs_top5_wl, vs_top10_wl, vs_top20_wl, vs_top50_wl
  vs_lefthanded_wl, vs_righthanded_wl
  tiebreak_wl, deciding_set_wl, fifth_set_wl
  on_hard_wl, on_clay_wl, on_grass_wl
OTHER: fastest_serve_kmh (number), fastest_serve_mph (number)

Return ONLY valid JSON. Omit fields not visible."""

async def scrape_wl_vision(ctx, key):
    name = PLAYERS[key]["name"]
    url  = PLAYERS[key]["page_wl"]
    print(f"  Loading {url}")
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception:
        await page.wait_for_timeout(10000)
    # Click "Career" tab if present, wait for data to load
    try:
        career_tab = page.locator("text=Career").first
        await career_tab.click(timeout=3000)
        await page.wait_for_timeout(2000)
    except Exception:
        await page.wait_for_timeout(1000)
    paths = await screenshots(page, n=5, step=600, prefix=f"/tmp/{key}_wl")
    await page.close()
    data = vision(img_blocks(paths), WL_PROMPT.replace("{name}", name))
    print(f"  → {len(data)} fields")
    return data


# ─── Source 4: Vision — Wikipedia ─────────────────────────────────────────────

WIKI_PROMPT = """Wikipedia career statistics page for {name}.

Look carefully at the Grand Slam tournament results table (usually near the top of the page).
Count ONLY cells/rows marked "W" which means the player WON that tournament that year.
Do NOT count F (finalist), SF (semifinalist), or other results.

Extract as JSON:
  ao_wins        (integer — Australian Open WINS only, count "W" cells in AO row)
  rg_wins        (integer — Roland Garros WINS only)
  wimbledon_wins (integer — Wimbledon WINS only)
  uso_wins       (integer — US Open WINS only)
  weeks_at_no1   (integer — total weeks at World No. 1, look for "Weeks at No. 1" text)
  days_at_no1    (integer — total days at No. 1 if shown)
  masters_titles (integer — ATP Masters 1000 titles ONLY, NOT counting Grand Slams or 500s)
  longest_win_streak (integer — longest single winning streak)
  year_end_rankings  (object — {"2022": 1, "2023": 2} format)

IMPORTANT: Carlos Alcaraz won the 2026 Australian Open. Jannik Sinner won AO 2024 and AO 2025.
Return ONLY valid JSON. Be very precise."""

async def scrape_wiki_vision(ctx, key):
    name = PLAYERS[key]["name"]
    url  = PLAYERS[key]["wiki_stats"]
    print(f"  Loading {url}")
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception:
        await page.wait_for_timeout(6000)
    # Extra wait for Wikipedia to fully render
    await page.wait_for_timeout(2000)
    paths = await screenshots(page, n=5, step=700, prefix=f"/tmp/{key}_wiki")
    await page.close()
    data = vision(img_blocks(paths), WIKI_PROMPT.replace("{name}", name))
    # Safely coerce year_end_rankings — vision sometimes returns years as top-level keys
    yer = data.get("year_end_rankings")
    if not isinstance(yer, dict):
        # Try to pull year-like keys (4-digit numbers) into a nested dict
        year_keys = {k: v for k, v in data.items() if str(k).isdigit() and len(str(k)) == 4}
        if year_keys:
            data["year_end_rankings"] = year_keys
            for k in year_keys:
                data.pop(k, None)
    print(f"  → {len(data)} fields")
    return data


# ─── Source 5: Vision — TennisStats.com ──────────────────────────────────────

TS_PROMPT = """TennisStats.com player page for {name}. Extract as JSON:
  wins_straight_sets_pct   (number, % wins without dropping a set)
  wins_from_behind_pct     (number, % wins after losing first set)
  breaks_per_set           (number)
  tiebreaks_per_match      (number)
  avg_match_duration_mins  (integer)
  avg_match_duration_str   (string e.g. "1h 52m")
  sets_per_match           (number)
  current_form_str         (string e.g. "W W L W W")
  longest_win_streak       (integer)
  fastest_serve_kmh        (number)
  fastest_serve_mph        (number)
  days_at_no1              (integer, if shown)
  weeks_at_no1             (integer, if shown)
Return ONLY valid JSON. Omit fields not visible."""

async def scrape_ts_vision(ctx, key):
    name = PLAYERS[key]["name"]
    url  = PLAYERS[key]["tennisstats"]
    print(f"  Loading {url}")
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception:
        await page.wait_for_timeout(6000)
    paths = await screenshots(page, n=3, step=600, prefix=f"/tmp/{key}_ts")
    await page.close()
    data = vision(img_blocks(paths), TS_PROMPT.replace("{name}", name))
    print(f"  → {len(data)} fields")
    return data


# ─── Source 6: Vision — ATP H2H page ─────────────────────────────────────────

H2H_PROMPT = """ATP Head-to-Head page for Sinner vs Alcaraz. Extract every match listed.

Return JSON with this exact structure:
{
  "sinner_wins": <integer>,
  "alcaraz_wins": <integer>,
  "matches": [
    {
      "date": "<Mon YYYY>",
      "tournament": "<tournament name>",
      "surface": "<hard|clay|grass>",
      "round": "<Final|SF|QF|R16|R32|etc>",
      "score": "<set scores separated by spaces>",
      "winner": "<sinner|alcaraz>"
    }
  ]
}

List matches in reverse chronological order (most recent first).
Surface must be lowercase: hard, clay, or grass.
Winner must be lowercase: sinner or alcaraz.
For the score, use the exact set scores shown (e.g. "6-3 6-7(7) 6-7(0) 7-5 6-3").
Return ONLY valid JSON."""

async def scrape_h2h_vision(ctx):
    print(f"  Loading {H2H_URL}")
    page = await ctx.new_page()
    try:
        await page.goto(H2H_URL, wait_until="networkidle", timeout=45000)
    except Exception:
        await page.wait_for_timeout(10000)
    # Scroll down to reveal all matches
    await page.wait_for_timeout(2000)
    paths = await screenshots(page, n=6, step=600, prefix="/tmp/h2h")
    await page.close()
    data = vision(img_blocks(paths), H2H_PROMPT)
    matches = data.get("matches", [])
    print(f"  → {len(matches)} matches, Sinner {data.get('sinner_wins')}, Alcaraz {data.get('alcaraz_wins')}")
    return data


def compute_h2h_derived(matches):
    """Compute sets won, last-5/last-10 from match list."""
    sinner_sets = 0
    alcaraz_sets = 0
    for m in matches:
        score = m.get("score", "")
        if "ret" in score.lower() or "w/o" in score.lower():
            continue
        sets = re.split(r'\s+', score.strip())
        for s in sets:
            # Parse "6-3" or "7-6(4)" → extract games before and after dash
            sm = re.match(r'(\d+)-(\d+)', s)
            if not sm:
                continue
            g1, g2 = int(sm.group(1)), int(sm.group(2))
            winner = m.get("winner", "")
            if g1 > g2:
                # First player in the score won this set
                # On ATP H2H pages, the winner's score is listed first
                if winner == "sinner":
                    sinner_sets += 1
                else:
                    alcaraz_sets += 1
            elif g2 > g1:
                if winner == "sinner":
                    alcaraz_sets += 1
                else:
                    sinner_sets += 1

    # Last N records
    last5_s = sum(1 for m in matches[:5] if m.get("winner") == "sinner")
    last5_a = sum(1 for m in matches[:5] if m.get("winner") == "alcaraz")
    last10_s = sum(1 for m in matches[:10] if m.get("winner") == "sinner")
    last10_a = sum(1 for m in matches[:10] if m.get("winner") == "alcaraz")

    return {
        "sinner_sets_won": sinner_sets,
        "alcaraz_sets_won": alcaraz_sets,
        "last5_sinner": last5_s,
        "last5_alcaraz": last5_a,
        "last10_sinner": last10_s,
        "last10_alcaraz": last10_a,
    }


# ─── Source 7: Computed ───────────────────────────────────────────────────────

def compute(key, atp, csv_d, wiki, ts, vision_wl=None):
    dob   = PLAYERS[key]["dob"]
    today = date.today()
    age   = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    career  = atp.get("career", {})
    aces    = career.get("aces") or 0
    dfs     = career.get("double_faults") or 0
    matches = (atp.get("career_wins", 0) or 0) + (atp.get("career_losses", 0) or 0)

    # Known correct values as fallbacks — update after each slam/milestone
    GS_FLOOR = {
        "sinner":  {
            "ao": 2, "rg": 0, "wim": 1, "uso": 1, "m1k": 7,
            "weeks_no1": 66,
        },
        "alcaraz": {
            "ao": 1, "rg": 2, "wim": 2, "uso": 2, "m1k": 8,
            "weeks_no1": 65,
        },
    }
    floor = GS_FLOOR.get(key, {})
    ao  = wiki.get("ao_wins")  if wiki.get("ao_wins")  is not None else floor.get("ao", 0)
    rg  = wiki.get("rg_wins")  if wiki.get("rg_wins")  is not None else floor.get("rg", 0)
    wim = wiki.get("wimbledon_wins") if wiki.get("wimbledon_wins") is not None else floor.get("wim", 0)
    uso = wiki.get("uso_wins") if wiki.get("uso_wins")  is not None else floor.get("uso", 0)
    # Sanity check: use floor for any slam where wiki returns 0 but floor says > 0
    # Also use floor if total is less than known minimum
    wiki_total = ao + rg + wim + uso
    known_total = floor.get("ao",0) + floor.get("rg",0) + floor.get("wim",0) + floor.get("uso",0)
    if wiki_total < known_total:
        ao  = max(ao,  floor.get("ao", 0))
        rg  = max(rg,  floor.get("rg", 0))
        wim = max(wim, floor.get("wim", 0))
        uso = max(uso, floor.get("uso", 0))
    # Per-slam floor: never show 0 if floor says player has won it
    ao  = max(ao,  floor.get("ao", 0))
    rg  = max(rg,  floor.get("rg", 0))
    wim = max(wim, floor.get("wim", 0))
    uso = max(uso, floor.get("uso", 0))
    gs  = ao + rg + wim + uso
    # Masters titles: Wikipedia often confuses total titles with Masters titles
    # Use floor value unless wiki returns something reasonable (<=12)
    raw_m1k = wiki.get("masters_titles") or 0
    m1k = raw_m1k if (0 < raw_m1k <= 10) else floor.get("m1k", 0)
    big = gs + m1k

    # Parse W/L strings into percentages
    def wl_pct(s):
        if not s: return None
        try:
            w, l = (int(x) for x in str(s).replace('–','-').split('-'))
            return round(w/(w+l)*100, 1) if (w+l) else None
        except: return None

    vwl = vision_wl or {}
    after_win_pct   = wl_pct(vwl.get("after_winning_first_set_wl"))
    after_lose_pct  = wl_pct(vwl.get("after_losing_first_set_wl"))
    tb_wl           = vwl.get("tiebreak_wl")
    tb_pct          = wl_pct(tb_wl)
    ds_wl           = vwl.get("deciding_set_wl")
    ds_pct          = wl_pct(ds_wl)

    return {
        "age":                    age,
        "avg_aces_match":         round(aces / matches, 2) if matches else None,
        "avg_df_match":           round(dfs / matches, 2) if matches else None,
        "gs_ao":                  ao,
        "gs_rg":                  rg,
        "gs_wimbledon":           wim,
        "gs_uso":                 uso,
        "gs_total":               gs or None,
        "masters_titles":         m1k or None,
        "big_titles":             big or None,
        "weeks_at_no1":           wiki.get("weeks_at_no1") or vwl.get("weeks_at_no1") or ts.get("weeks_at_no1") or floor.get("weeks_no1"),
        "days_at_no1":            wiki.get("days_at_no1") or ts.get("days_at_no1") or ((wiki.get("weeks_at_no1") or floor.get("weeks_no1", 0)) * 7) or None,

        "year_end_rankings":      wiki.get("year_end_rankings"),

        "after_winning_first_set_pct": vwl.get("after_winning_first_set_pct") or after_win_pct,
        "after_losing_first_set_pct":  vwl.get("after_losing_first_set_pct") or after_lose_pct,
        "tiebreaks_won_pct":      tb_pct,
        "deciding_sets_won_pct":  ds_pct,
    }


# ─── JSON output (HTML now loads stats dynamically) ──────────────────────────

def fmt_short(prize_str):
    if not prize_str:
        return None
    digits = re.sub(r"[^\d]", "", str(prize_str))
    return f"${int(digits) / 1_000_000:.1f}M" if digits else None


def update_html(scraped):
    """
    The HTML now fetches scraped_stats.json dynamically at page load.
    We only need to update the last-updated timestamp in the HTML.
    All stat values are populated by JavaScript from scraped_stats.json.
    """
    if not os.path.exists("index.html"):
        return
    with open("index.html", "r") as f:
        html = f.read()
    today = datetime.now(timezone.utc).strftime("%-d %B %Y")
    new_html = re.sub(r'(id="last-updated">)Last updated: [^<]+', rf'\1Last updated: {today}', html)
    if new_html != html:
        with open("index.html", "w") as f:
            f.write(new_html)
        print(f"  ✅ Last updated timestamp → {today}")
    else:
        print("  Timestamp unchanged")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print(f"=== sincaraz.app scraper v11 — {datetime.now(timezone.utc).isoformat()} ===\n")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        print("⚠  ANTHROPIC_API_KEY not set — vision sources skipped\n")

    # Load previous stats to detect if a match was played since last run
    prev_totals = {}
    prev_scraped_at = None
    try:
        with open("scraped_stats.json") as f:
            prev = json.load(f)
        for key in ["sinner", "alcaraz"]:
            w = prev.get(key, {}).get("career_wins", 0) or 0
            l = prev.get(key, {}).get("career_losses", 0) or 0
            prev_totals[key] = w + l
        prev_scraped_at = prev.get("scraped_at")
        # Preserve existing h2h_matches/h2h_derived so they survive XHR-only runs
        prev_h2h_matches  = prev.get("h2h_matches", [])
        prev_h2h_derived  = prev.get("h2h_derived")
        prev_h2h_wins_s   = prev.get("sinner", {}).get("h2h_wins")
        prev_h2h_wins_a   = prev.get("alcaraz", {}).get("h2h_wins")
    except Exception:
        prev_h2h_matches, prev_h2h_derived = [], None
        prev_h2h_wins_s, prev_h2h_wins_a = None, None

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sinner": {
            "h2h_wins":   PLAYERS["sinner"]["h2h_wins"],
            "h2h_losses": PLAYERS["sinner"]["h2h_losses"],
        },
        "alcaraz": {
            "h2h_wins":   PLAYERS["alcaraz"]["h2h_wins"],
            "h2h_losses": PLAYERS["alcaraz"]["h2h_losses"],
        },
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Source 1: ATP XHR
        print("[1/4] ATP XHR Intercept")
        for i, key in enumerate(["sinner", "alcaraz"]):
            print(f"\n  {PLAYERS[key]['name']}")
            if i > 0:
                print("  Waiting 8s...")
                await asyncio.sleep(8)
            ctx   = await make_context(browser)
            stats = await scrape_xhr(ctx, key)
            if not stats:
                print("  Retrying in 10s...")
                await asyncio.sleep(10)
                stats = await scrape_xhr(ctx, key)
            result[key].update(stats)
            await ctx.close()

        # Smart skip: only run vision if a match was played or weekly refresh due
        match_played = False
        for key in ["sinner", "alcaraz"]:
            new_total = (result[key].get("career_wins", 0) or 0) + (result[key].get("career_losses", 0) or 0)
            old_total = prev_totals.get(key, 0)
            if old_total and new_total != old_total:
                match_played = True
                print(f"\n  📍 Match detected: {PLAYERS[key]['name']} total matches {old_total} → {new_total}")

        weekly_due = True
        if prev_scraped_at:
            try:
                last = datetime.fromisoformat(prev_scraped_at)
                weekly_due = (datetime.now(timezone.utc) - last).days >= 7
            except Exception:
                pass

        run_vision = has_key and (match_played or weekly_due)
        if has_key and not run_vision:
            print(f"\n⏭  No match played and weekly refresh not due — skipping vision (saves ~15 min + API cost)")
            print(f"   Preserving existing H2H data ({len(prev_h2h_matches)} matches)")
            # Restore previous H2H/vision data so the JSON stays complete
            if prev_h2h_matches:
                result["h2h_matches"] = prev_h2h_matches
            if prev_h2h_derived:
                result["h2h_derived"] = prev_h2h_derived
            if prev_h2h_wins_s is not None:
                result["sinner"]["h2h_wins"] = prev_h2h_wins_s
            if prev_h2h_wins_a is not None:
                result["alcaraz"]["h2h_wins"] = prev_h2h_wins_a
            # Also restore vision fields so the site doesn't lose data
            for key in ["sinner", "alcaraz"]:
                for field in ["vision_wl", "vision_wiki"]:
                    val = prev.get(key, {}).get(field)
                    if val:
                        result[key][field] = val

        if run_vision:
            # Source 3: ATP W/L vision
            print("\n[2/4] Vision — ATP Win/Loss Index")
            for i, key in enumerate(["sinner", "alcaraz"]):
                print(f"\n  {PLAYERS[key]['name']}")
                if i > 0: await asyncio.sleep(8)
                ctx = await make_context(browser, wide=True)
                result[key]["vision_wl"] = await scrape_wl_vision(ctx, key)
                await ctx.close()

            # Source 4: Wikipedia
            print("\n[3/4] Vision — Wikipedia")
            for i, key in enumerate(["sinner", "alcaraz"]):
                print(f"\n  {PLAYERS[key]['name']}")
                if i > 0: await asyncio.sleep(5)
                ctx = await make_context(browser)
                result[key]["vision_wiki"] = await scrape_wiki_vision(ctx, key)
                await ctx.close()

            # Source 6: ATP H2H vision
            print("\n[4/4] Vision — ATP H2H")
            ctx = await make_context(browser, wide=True)
            h2h_data = await scrape_h2h_vision(ctx)
            await ctx.close()
            h2h_matches = h2h_data.get("matches", [])
            if h2h_matches:
                result["h2h_matches"] = h2h_matches
                # Override hardcoded H2H wins with scraped values
                sw = h2h_data.get("sinner_wins")
                aw = h2h_data.get("alcaraz_wins")
                if sw is not None:
                    result["sinner"]["h2h_wins"] = sw
                    result["sinner"]["h2h_losses"] = aw or PLAYERS["sinner"]["h2h_losses"]
                if aw is not None:
                    result["alcaraz"]["h2h_wins"] = aw
                    result["alcaraz"]["h2h_losses"] = sw or PLAYERS["alcaraz"]["h2h_losses"]
                # Compute derived H2H stats
                result["h2h_derived"] = compute_h2h_derived(h2h_matches)
            else:
                print("  ⚠ No matches extracted — keeping hardcoded H2H values")
        elif not has_key:
            print("\n[2-4/4] Vision sources skipped (no ANTHROPIC_API_KEY)")

        await browser.close()

    # CSV source removed — surface W/L comes from ATP W/L vision instead
    for key in ["sinner", "alcaraz"]:
        result[key]["csv"] = {}

    # Source 7: Computed
    for key in ["sinner", "alcaraz"]:
        result[key]["computed"] = compute(
            key,
            result[key],
            result[key].get("csv", {}),
            result[key].get("vision_wiki", {}),
            result[key].get("vision_ts", {}),
            result[key].get("vision_wl", {}),
        )

    print("\n=== SUMMARY ===")
    for key in ["sinner", "alcaraz"]:
        d  = result[key]
        cx = d.get("computed", {})
        print(
            f"  {key}: {d.get('career_wl')} | CSV {d.get('csv',{}).get('csv_career_wl')} | "
            f"Age {cx.get('age')} | GS {cx.get('gs_total')} "
            f"(AO={cx.get('gs_ao')} RG={cx.get('gs_rg')} "
            f"W={cx.get('gs_wimbledon')} US={cx.get('gs_uso')}) | "
            f"WL={len(d.get('vision_wl',{}))}f Wiki={len(d.get('vision_wiki',{}))}f "
            f"TS={len(d.get('vision_ts',{}))}f"
        )

    with open("scraped_stats.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print("\n✅ scraped_stats.json saved")

    print("\nUpdating index.html...")
    update_html(result)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
