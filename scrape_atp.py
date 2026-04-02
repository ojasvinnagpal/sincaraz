"""
sincaraz.app — ATP Stats Scraper v10
Four data sources covering every stat in the master wishlist:

  1. ATP XHR intercept     → career W/L, rankings, prize money, ALL serve/return stats
                             (+ fields previously captured but not written to HTML)
  2. JeffSackmann CSV      → H2H, surface splits, YTD, sets won/lost computed
  3. Vision: ATP W/L page  → ALL situational records, ratings, vs-opponent splits
  4. Vision: Wikipedia     → Grand Slam counts per slam, weeks/days at #1, year-end rankings
  5. Vision: TennisStats   → avg match duration, wins from behind, breaks/set, streaks
  6. Computed              → age (live from DOB), avg aces/match, sets ratio, big titles
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
        "h2h_losses":  12,
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
        "h2h_wins":    12,
        "h2h_losses":  6,
        "page_stats":  "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats",
        "page_wl":     "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/atp-win-loss",
        "wiki_stats":  "https://en.wikipedia.org/wiki/Carlos_Alcaraz_career_statistics",
        "tennisstats": "https://www.flashscore.com/player/alcaraz-carlos/W2Bkdnhj/",
    },
}

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
                "atp_points":     data.get("SglRankPts"),
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


# ─── Source 2: JeffSackmann CSV ───────────────────────────────────────────────

def fetch_csv(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sincaraz/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  CSV error {url}: {e}")
        return None


def pmatch(name_str, key):
    return name_str.lower().strip() in (SINNER_NAMES if key == "sinner" else ALCARAZ_NAMES)


def score_sets(score, won):
    sw = sl = 0
    for part in score.replace("(", " ").replace(")", " ").split():
        if "-" not in part:
            continue
        h = part.split("-")
        if len(h) != 2:
            continue
        try:
            a, b = int(h[0]), int(h[1])
            if won:
                sw += 1 if a > b else 0
                sl += 1 if b > a else 0
            else:
                sw += 1 if b > a else 0
                sl += 1 if a > b else 0
        except ValueError:
            pass
    return sw, sl


def scrape_sackmann():
    print("\n[Sackmann CSV]")
    yr = datetime.now().year
    rows = []
    for y in [yr - 2, yr - 1, yr]:
        url = f"{SACKMANN_BASE}/atp_matches_{y}.csv"
        print(f"  Fetching {url}")
        t = fetch_csv(url)
        if t:
            r = list(csv.DictReader(io.StringIO(t)))
            rows.extend(r)
            print(f"  → {len(r)} matches in {y}")
        else:
            print(f"  → no data for {y}")
    print(f"  Total rows loaded: {len(rows)}")

    result = {}
    yr_s = str(yr)
    for key in ["sinner", "alcaraz"]:
        opp = "alcaraz" if key == "sinner" else "sinner"
        w = l = yw = yl = hw = hl = cw = cl = gw = gl = h2w = h2l = 0
        sw_tot = sl_tot = ss_wins = 0

        for row in rows:
            winner  = row.get("winner_name", "")
            loser   = row.get("loser_name", "")
            surface = row.get("surface", "").lower()
            tdate   = row.get("tourney_date", "")
            score   = row.get("score", "")
            is_w    = pmatch(winner, key)
            is_l    = pmatch(loser, key)
            if not is_w and not is_l:
                continue
            sw, sl = score_sets(score, is_w)
            sw_tot += sw
            sl_tot += sl
            if is_w:
                w += 1
                if tdate.startswith(yr_s): yw += 1
                if surface == "hard":   hw += 1
                elif surface == "clay": cw += 1
                elif surface == "grass":gw += 1
                if pmatch(loser, opp):  h2w += 1
                if sl == 0 and sw > 0:  ss_wins += 1
            else:
                l += 1
                if tdate.startswith(yr_s): yl += 1
                if surface == "hard":   hl += 1
                elif surface == "clay": cl += 1
                elif surface == "grass":gl += 1
                if pmatch(winner, opp): h2l += 1

        tot = w + l
        yrt = yw + yl
        st  = sw_tot + sl_tot
        result[key] = {
            "csv_career_wl":            f"{w}\u2013{l}",
            "csv_career_wins":          w,
            "csv_career_losses":        l,
            "csv_career_win_pct":       round(w / tot * 100, 1) if tot else None,
            "csv_ytd_wl":               f"{yw}\u2013{yl}",
            "csv_ytd_win_pct":          round(yw / yrt * 100, 1) if yrt else None,
            "csv_hard_wl":              f"{hw}\u2013{hl}",
            "csv_hard_win_pct":         round(hw / (hw+hl) * 100, 1) if (hw+hl) else None,
            "csv_clay_wl":              f"{cw}\u2013{cl}",
            "csv_clay_win_pct":         round(cw / (cw+cl) * 100, 1) if (cw+cl) else None,
            "csv_grass_wl":             f"{gw}\u2013{gl}",
            "csv_grass_win_pct":        round(gw / (gw+gl) * 100, 1) if (gw+gl) else None,
            "csv_h2h_wins":             h2w,
            "csv_h2h_losses":           h2l,
            "csv_sets_won":             sw_tot,
            "csv_sets_lost":            sl_tot,
            "csv_sets_ratio":           round(sw_tot / st * 100, 1) if st else None,
            "csv_straight_set_wins_pct": round(ss_wins / w * 100, 1) if w else None,
        }
        d = result[key]
        print(f"  {key}: {d['csv_career_wl']} | YTD {d['csv_ytd_wl']} | "
              f"H2H {h2w}-{h2l} | Sets {sw_tot}-{sl_tot} | SS wins {d['csv_straight_set_wins_pct']}%")
    return result


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
    data = vision(img_blocks(paths), WIKI_PROMPT.format(name=name))
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


# ─── Source 6: Computed ───────────────────────────────────────────────────────

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
            "ao": 2, "rg": 0, "wim": 1, "uso": 1, "m1k": 6,
            "weeks_no1": 66, "fastest_serve_kmh": 220, "fastest_serve_mph": 137,
        },
        "alcaraz": {
            "ao": 1, "rg": 2, "wim": 2, "uso": 2, "m1k": 6,
            "weeks_no1": 65, "fastest_serve_kmh": 220, "fastest_serve_mph": 137,
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
        "weeks_at_no1":           wiki.get("weeks_at_no1") or ts.get("weeks_at_no1") or floor.get("weeks_no1"),
        "days_at_no1":            wiki.get("days_at_no1") or ts.get("days_at_no1"),
        "longest_win_streak":     ts.get("longest_win_streak") or wiki.get("longest_win_streak"),
        "current_win_streak":     wiki.get("current_win_streak"),
        "year_end_rankings":      wiki.get("year_end_rankings"),
        "fastest_serve_kmh":      ts.get("fastest_serve_kmh") or wiki.get("fastest_serve_kmh") or floor.get("fastest_serve_kmh"),
        "fastest_serve_mph":      ts.get("fastest_serve_mph") or wiki.get("fastest_serve_mph") or floor.get("fastest_serve_mph"),
        "wins_straight_sets_pct": ts.get("wins_straight_sets_pct") or csv_d.get("csv_straight_set_wins_pct"),
        "wins_from_behind_pct":   after_lose_pct or ts.get("wins_from_behind_pct"),
        "after_winning_first_set_pct": after_win_pct,
        "after_losing_first_set_pct":  after_lose_pct,
        "tiebreaks_won_pct":      tb_pct,
        "deciding_sets_won_pct":  ds_pct,
        "breaks_per_set":         ts.get("breaks_per_set"),
        "tiebreaks_per_match":    ts.get("tiebreaks_per_match"),
        "avg_match_duration_str": ts.get("avg_match_duration_str"),
        "avg_match_duration_mins":ts.get("avg_match_duration_mins"),
        "current_form_str":       ts.get("current_form_str"),
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
    new_html = re.sub(r"Last updated: [^<\"]+", f"Last updated: {today}", html)
    if new_html != html:
        with open("index.html", "w") as f:
            f.write(new_html)
        print(f"  ✅ Last updated timestamp → {today}")
    else:
        print("  Timestamp unchanged")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print(f"=== sincaraz.app scraper v10 — {datetime.now(timezone.utc).isoformat()} ===\n")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        print("⚠  ANTHROPIC_API_KEY not set — vision sources skipped\n")

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

        if has_key:
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

            # Source 5: TennisStats
            print("\n[4/4] Vision — TennisStats")
            for i, key in enumerate(["sinner", "alcaraz"]):
                print(f"\n  {PLAYERS[key]['name']}")
                if i > 0: await asyncio.sleep(5)
                ctx = await make_context(browser)
                result[key]["vision_ts"] = await scrape_ts_vision(ctx, key)
                await ctx.close()
        else:
            print("\n[2-4/4] Vision sources skipped (no ANTHROPIC_API_KEY)")

        await browser.close()

    # Source 2: Sackmann CSV
    print("\n[CSV] JeffSackmann matches")
    csv_data = scrape_sackmann()
    for key in ["sinner", "alcaraz"]:
        result[key]["csv"] = csv_data.get(key, {})

    # Source 6: Computed
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
