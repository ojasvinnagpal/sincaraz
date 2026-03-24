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
        "page_stats":  "https://www.atptour.com/en/players/jannik-sinner/s0ag/player-stats",
        "page_wl":     "https://www.atptour.com/en/players/jannik-sinner/s0ag/atp-win-loss",
        "wiki_stats":  "https://en.wikipedia.org/wiki/Jannik_Sinner_career_statistics",
        "tennisstats": "https://tennisstats.com/players/jannik-sinner",
    },
    "alcaraz": {
        "id":          "a0e2",
        "name":        "Carlos Alcaraz",
        "dob":         date(2003, 5, 3),
        "page_stats":  "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/player-stats",
        "page_wl":     "https://www.atptour.com/en/players/carlos-alcaraz/a0e2/atp-win-loss",
        "wiki_stats":  "https://en.wikipedia.org/wiki/Carlos_Alcaraz_career_statistics",
        "tennisstats": "https://tennisstats.com/players/carlos-alcaraz",
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

RATINGS (numbers): serve_rating, return_rating, under_pressure_rating
PERCENTAGES (numbers, no % sign):
  tiebreaks_won_pct, deciding_sets_won_pct, bp_saved_pct, bp_converted_pct
  after_winning_first_set_pct, after_losing_first_set_pct
WIN-LOSS RECORDS (format "W-L"):
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
    paths = await screenshots(page, n=4, step=650, prefix=f"/tmp/{key}_wl")
    await page.close()
    data = vision(img_blocks(paths), WL_PROMPT.format(name=name))
    print(f"  → {len(data)} fields")
    return data


# ─── Source 4: Vision — Wikipedia ─────────────────────────────────────────────

WIKI_PROMPT = """Wikipedia career statistics page for {name}. Extract as JSON:
  ao_wins, rg_wins, wimbledon_wins, uso_wins  (integers — titles won at each slam)
  weeks_at_no1  (integer)
  days_at_no1   (integer, if shown)
  masters_titles (integer)
  longest_win_streak (integer)
  current_win_streak (integer, if shown)
  year_end_rankings  (object e.g. {"2022": 10, "2023": 4, "2024": 1})
Return ONLY valid JSON. Omit fields not visible."""

async def scrape_wiki_vision(ctx, key):
    name = PLAYERS[key]["name"]
    url  = PLAYERS[key]["wiki_stats"]
    print(f"  Loading {url}")
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception:
        await page.wait_for_timeout(6000)
    paths = await screenshots(page, n=4, step=800, prefix=f"/tmp/{key}_wiki")
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
    data = vision(img_blocks(paths), TS_PROMPT.format(name=name))
    print(f"  → {len(data)} fields")
    return data


# ─── Source 6: Computed ───────────────────────────────────────────────────────

def compute(key, atp, csv_d, wiki, ts):
    dob   = PLAYERS[key]["dob"]
    today = date.today()
    age   = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    career  = atp.get("career", {})
    aces    = career.get("aces") or 0
    dfs     = career.get("double_faults") or 0
    matches = (atp.get("career_wins", 0) or 0) + (atp.get("career_losses", 0) or 0)

    ao  = wiki.get("ao_wins") or 0
    rg  = wiki.get("rg_wins") or 0
    wim = wiki.get("wimbledon_wins") or 0
    uso = wiki.get("uso_wins") or 0
    gs  = ao + rg + wim + uso
    m1k = wiki.get("masters_titles") or 0
    big = gs + m1k

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
        "weeks_at_no1":           wiki.get("weeks_at_no1") or ts.get("weeks_at_no1"),
        "days_at_no1":            wiki.get("days_at_no1") or ts.get("days_at_no1"),
        "longest_win_streak":     ts.get("longest_win_streak") or wiki.get("longest_win_streak"),
        "current_win_streak":     wiki.get("current_win_streak"),
        "year_end_rankings":      wiki.get("year_end_rankings"),
        "fastest_serve_kmh":      ts.get("fastest_serve_kmh") or wiki.get("fastest_serve_kmh"),
        "fastest_serve_mph":      ts.get("fastest_serve_mph") or wiki.get("fastest_serve_mph"),
        "wins_straight_sets_pct": ts.get("wins_straight_sets_pct") or csv_d.get("csv_straight_set_wins_pct"),
        "wins_from_behind_pct":   ts.get("wins_from_behind_pct"),
        "breaks_per_set":         ts.get("breaks_per_set"),
        "tiebreaks_per_match":    ts.get("tiebreaks_per_match"),
        "avg_match_duration_str": ts.get("avg_match_duration_str"),
        "avg_match_duration_mins":ts.get("avg_match_duration_mins"),
        "current_form_str":       ts.get("current_form_str"),
    }


# ─── HTML update ──────────────────────────────────────────────────────────────

def fmt_short(prize_str):
    if not prize_str:
        return None
    digits = re.sub(r"[^\d]", "", str(prize_str))
    return f"${int(digits) / 1_000_000:.1f}M" if digits else None


def update_html(scraped):
    if not os.path.exists("index.html"):
        print("  index.html not found")
        return

    with open("index.html", "r") as f:
        html = f.read()
    orig    = html
    updated = []

    def rn(h, pat, val, n=1):
        """replace nth regex match: keep group(1), replace group(2), keep group(3)"""
        ms = list(re.finditer(pat, h))
        if len(ms) >= n:
            m = ms[n - 1]
            return h[:m.start()] + m.group(1) + str(val) + m.group(2) + h[m.end():]
        return h

    S  = scraped.get("sinner", {})
    A  = scraped.get("alcaraz", {})
    SC = S.get("csv", {})
    AC = A.get("csv", {})
    SV = S.get("vision_wl", {})
    AV = A.get("vision_wl", {})
    SX = S.get("computed", {})
    AX = A.get("computed", {})
    SC_ = S.get("career", {})
    AC_ = A.get("career", {})

    def patch(pat, sv, av, label):
        nonlocal html
        prev = html
        if sv is not None: html = rn(html, pat, sv, 1)
        if av is not None: html = rn(html, pat, av, 2)
        if html != prev: updated.append(f"{label}: {sv} / {av}")

    def sub1(pat, val, label):
        nonlocal html
        prev = html
        if val is not None:
            html = re.sub(pat, lambda m: m.group(1) + str(val) + m.group(2), html, count=1)
        if html != prev: updated.append(f"{label}: {val}")

    def trow(label_text, sv, av, note_label):
        nonlocal html
        prev = html
        le = re.escape(label_text)
        if sv is not None:
            html = re.sub(rf'({le}</td><td class="sv">)[^<]+(</td>)',
                          rf'\g<1>{sv}\2', html, count=1)
        if av is not None:
            html = re.sub(rf'({le}</td><td class="sv">[^<]+</td><td class="av">)[^<]+(</td>)',
                          rf'\g<1>{av}\2', html, count=1)
        if html != prev: updated.append(f"Table {note_label}: {sv} / {av}")

    # ── Profile spans ────────────────────────────────────────────────────
    patch(r'(Career W/L</span><span class="ps-val">)[\d\u2013\-]+(</span>)',
          S.get("career_wl"), A.get("career_wl"), "Profile W/L")
    patch(r'(Win Ratio</span><span class="ps-val">)[\d.]+%(</span>)',
          f"{S['career_win_pct']}%" if S.get("career_win_pct") else None,
          f"{A['career_win_pct']}%" if A.get("career_win_pct") else None, "Profile Win%")
    patch(r'(Titles</span><span class="ps-val">)\d+(</span>)',
          S.get("career_titles"), A.get("career_titles"), "Profile Titles")
    patch(r'(Grand Slams</span><span class="ps-val">)\d+(</span>)',
          SX.get("gs_total"), AX.get("gs_total"), "Profile GS")
    patch(r'(Prize Money</span><span class="ps-val">)[^<]+(</span>)',
          S.get("prize_career"), A.get("prize_career"), "Profile Prize")
    patch(r'(ATP Points</span><span class="ps-val">)[^<]+(</span>)',
          f"{S['atp_points']:,}" if S.get("atp_points") else None,
          f"{A['atp_points']:,}" if A.get("atp_points") else None, "Profile Points")
    patch(r'(Age</span><span class="ps-val">)\d+(</span>)',
          SX.get("age"), AX.get("age"), "Profile Age")
    patch(r'(Coach</span><span class="ps-val">)[^<]+(</span>)',
          S.get("coach"), A.get("coach"), "Profile Coach")
    patch(r'(YTD W/L</span><span class="ps-val">)[\d\u2013\-]+(</span>)',
          S.get("ytd_wl"), A.get("ytd_wl"), "Profile YTD W/L")
    patch(r'(YTD Titles</span><span class="ps-val">)\d+(</span>)',
          S.get("ytd_titles"), A.get("ytd_titles"), "Profile YTD Titles")
    patch(r'(Aces</span><span class="ps-val">)\d+(</span>)',
          SC_.get("aces"), AC_.get("aces"), "Profile Aces")
    patch(r'(Double Faults</span><span class="ps-val">)\d+(</span>)',
          SC_.get("double_faults"), AC_.get("double_faults"), "Profile DF")
    patch(r'(1st Serve %</span><span class="ps-val">)[\d.]+%(</span>)',
          f"{SC_['first_serve_pct']}%" if SC_.get("first_serve_pct") else None,
          f"{AC_['first_serve_pct']}%" if AC_.get("first_serve_pct") else None, "Profile 1stSrv%")
    patch(r'(Avg\. Aces/Match</span><span class="ps-val">)[\d.]+(</span>)',
          SX.get("avg_aces_match"), AX.get("avg_aces_match"), "Profile Avg Aces/Match")
    patch(r'(Avg\. DF/Match</span><span class="ps-val">)[\d.]+(</span>)',
          SX.get("avg_df_match"), AX.get("avg_df_match"), "Profile Avg DF/Match")
    patch(r'(Days at #1</span><span class="ps-val">)[\d+]+(</span>)',
          SX.get("days_at_no1"), AX.get("days_at_no1"), "Profile Days#1")
    patch(r'(Weeks at #1</span><span class="ps-val">)[\d+]+(</span>)',
          SX.get("weeks_at_no1"), AX.get("weeks_at_no1"), "Profile Weeks#1")
    patch(r'(Fastest Serve</span><span class="ps-val">)[^<]+(</span>)',
          f"{SX['fastest_serve_kmh']} km/h" if SX.get("fastest_serve_kmh") else None,
          f"{AX['fastest_serve_kmh']} km/h" if AX.get("fastest_serve_kmh") else None,
          "Profile Fastest Serve")

    # ── Summary cards ────────────────────────────────────────────────────
    s_sh = fmt_short(S.get("prize_career"))
    a_sh = fmt_short(A.get("prize_career"))
    prev = html
    if s_sh:
        html = re.sub(r'(class="qs-val s" style="font-size:26px">\$)[\d.]+M(</div>)',
                      lambda m: f'{m.group(1)}{s_sh.lstrip("$")}{m.group(2)}', html, count=1)
    if a_sh:
        html = re.sub(r'(class="qs-val a" style="font-size:26px">\$)[\d.]+M(</div>)',
                      lambda m: f'{m.group(1)}{a_sh.lstrip("$")}{m.group(2)}', html, count=1)
    if html != prev: updated.append(f"Card earnings: {s_sh}/{a_sh}")

    s_ytd = SC.get("csv_ytd_win_pct") or S.get("ytd_win_pct")
    a_ytd = AC.get("csv_ytd_win_pct") or A.get("ytd_win_pct")
    prev = html
    if s_ytd:
        html = re.sub(r'(class="qs-val s" style="font-size:28px">)[\d.]+%(</div>)',
                      rf'\g<1>{s_ytd}%\2', html, count=1)
    if a_ytd:
        html = re.sub(r'(class="qs-val a" style="font-size:28px">)[\d.]+%(</div>)',
                      rf'\g<1>{a_ytd}%\2', html, count=1)
    if html != prev: updated.append(f"Card YTD Win%: {s_ytd}%/{a_ytd}%")

    sh2h = SC.get("csv_h2h_wins")
    ah2h = AC.get("csv_h2h_wins")
    if sh2h is not None and ah2h is not None:
        prev = html
        pat  = r'(class="qs-val s"[^>]*>)\d+(</div>.*?class="qs-val a"[^>]*>)\d+(</div>.*?matches played)'
        html = re.sub(pat, lambda m: f'{m.group(1)}{sh2h}{m.group(2)}{ah2h}{m.group(3)}',
                      html, count=1, flags=re.DOTALL)
        if html != prev: updated.append(f"H2H: {sh2h}–{ah2h}")

    # ── Comparison table ─────────────────────────────────────────────────
    trow("Career Win/Loss",       S.get("career_wl"), A.get("career_wl"), "W/L")
    trow("Career Win %",
         f"{S['career_win_pct']}%" if S.get("career_win_pct") else None,
         f"{A['career_win_pct']}%" if A.get("career_win_pct") else None, "Win%")
    trow("Titles (ATP)",          S.get("career_titles"), A.get("career_titles"), "Titles")
    trow("Grand Slams",           SX.get("gs_total"), AX.get("gs_total"), "GS")
    trow("Prize Money",           s_sh, a_sh, "Prize")
    trow("YTD W/L",               S.get("ytd_wl"), A.get("ytd_wl"), "YTD W/L")
    trow("YTD Titles",            S.get("ytd_titles"), A.get("ytd_titles"), "YTD Titles")
    trow("Days at World #1",      SX.get("days_at_no1"), AX.get("days_at_no1"), "Days#1")
    trow("Weeks at World #1",     SX.get("weeks_at_no1"), AX.get("weeks_at_no1"), "Weeks#1")
    trow("Aces",                  SC_.get("aces"), AC_.get("aces"), "Aces")
    trow("Double Faults",         SC_.get("double_faults"), AC_.get("double_faults"), "DF")
    trow("1st Serve %",
         f"{SC_['first_serve_pct']}%" if SC_.get("first_serve_pct") else None,
         f"{AC_['first_serve_pct']}%" if AC_.get("first_serve_pct") else None, "1stSrv%")
    trow("1st Serve Won %",
         f"{SC_['first_serve_won_pct']}%" if SC_.get("first_serve_won_pct") else None,
         f"{AC_['first_serve_won_pct']}%" if AC_.get("first_serve_won_pct") else None, "1stSrvWon%")
    trow("2nd Serve Won %",
         f"{SC_['second_serve_won_pct']}%" if SC_.get("second_serve_won_pct") else None,
         f"{AC_['second_serve_won_pct']}%" if AC_.get("second_serve_won_pct") else None, "2ndSrvWon%")
    trow("BP Saved %",
         f"{SC_['bp_saved_pct']}%" if SC_.get("bp_saved_pct") else None,
         f"{AC_['bp_saved_pct']}%" if AC_.get("bp_saved_pct") else None, "BP Saved%")
    trow("BP Converted %",
         f"{SC_['bp_converted_pct']}%" if SC_.get("bp_converted_pct") else None,
         f"{AC_['bp_converted_pct']}%" if AC_.get("bp_converted_pct") else None, "BP Conv%")
    trow("1st Serve Return Won %",
         f"{SC_['first_return_won_pct']}%" if SC_.get("first_return_won_pct") else None,
         f"{AC_['first_return_won_pct']}%" if AC_.get("first_return_won_pct") else None, "1stRetWon%")
    trow("2nd Serve Return Won %",
         f"{SC_['second_return_won_pct']}%" if SC_.get("second_return_won_pct") else None,
         f"{AC_['second_return_won_pct']}%" if AC_.get("second_return_won_pct") else None, "2ndRetWon%")
    trow("Return Games Won %",
         f"{SC_['return_games_won_pct']}%" if SC_.get("return_games_won_pct") else None,
         f"{AC_['return_games_won_pct']}%" if AC_.get("return_games_won_pct") else None, "RetGamesWon%")
    trow("Total Points Won %",
         f"{SC_['total_points_won_pct']}%" if SC_.get("total_points_won_pct") else None,
         f"{AC_['total_points_won_pct']}%" if AC_.get("total_points_won_pct") else None, "TotalPtsWon%")
    trow("Avg. Aces / Match",     SX.get("avg_aces_match"), AX.get("avg_aces_match"), "Avg Aces/M")
    trow("Avg. DF / Match",       SX.get("avg_df_match"), AX.get("avg_df_match"), "Avg DF/M")
    trow("Fastest Serve",
         f"{SX['fastest_serve_kmh']} km/h" if SX.get("fastest_serve_kmh") else None,
         f"{AX['fastest_serve_kmh']} km/h" if AX.get("fastest_serve_kmh") else None, "Fastest Serve")
    trow("Sets Won/Lost",
         f"{SC['csv_sets_won']}\u2013{SC['csv_sets_lost']}" if SC.get("csv_sets_won") else None,
         f"{AC['csv_sets_won']}\u2013{AC['csv_sets_lost']}" if AC.get("csv_sets_won") else None, "Sets W/L")
    trow("Sets Won %",
         f"{SC['csv_sets_ratio']}%" if SC.get("csv_sets_ratio") else None,
         f"{AC['csv_sets_ratio']}%" if AC.get("csv_sets_ratio") else None, "Sets%")
    trow("Wins in Straight Sets %",
         f"{SX['wins_straight_sets_pct']}%" if SX.get("wins_straight_sets_pct") else None,
         f"{AX['wins_straight_sets_pct']}%" if AX.get("wins_straight_sets_pct") else None, "SS Wins%")
    trow("Wins from Behind %",
         f"{SX['wins_from_behind_pct']}%" if SX.get("wins_from_behind_pct") else None,
         f"{AX['wins_from_behind_pct']}%" if AX.get("wins_from_behind_pct") else None, "From Behind%")
    trow("Avg Match Duration",    SX.get("avg_match_duration_str"), AX.get("avg_match_duration_str"), "Avg Duration")
    trow("Longest Win Streak",    SX.get("longest_win_streak"), AX.get("longest_win_streak"), "Streak")
    # Vision W/L situational
    trow("Serve Rating",          SV.get("serve_rating"), AV.get("serve_rating"), "Serve Rating")
    trow("Return Rating",         SV.get("return_rating"), AV.get("return_rating"), "Return Rating")
    trow("Under Pressure Rating", SV.get("under_pressure_rating"), AV.get("under_pressure_rating"), "Pressure Rating")
    trow("vs Top 5",              SV.get("vs_top5_wl"), AV.get("vs_top5_wl"), "vs Top5")
    trow("vs Top 10",             SV.get("vs_top10_wl"), AV.get("vs_top10_wl"), "vs Top10")
    trow("vs Top 20",             SV.get("vs_top20_wl"), AV.get("vs_top20_wl"), "vs Top20")
    trow("Finals W/L",            SV.get("finals_wl"), AV.get("finals_wl"), "Finals W/L")
    trow("Grand Slams W/L",       SV.get("grand_slams_wl"), AV.get("grand_slams_wl"), "GS W/L record")
    trow("Masters 1000 W/L",      SV.get("masters_wl"), AV.get("masters_wl"), "Masters W/L")
    trow("Indoor W/L",            SV.get("indoor_wl"), AV.get("indoor_wl"), "Indoor")
    trow("Outdoor W/L",           SV.get("outdoor_wl"), AV.get("outdoor_wl"), "Outdoor")
    trow("Tiebreaks W/L",         SV.get("tiebreak_wl"), AV.get("tiebreak_wl"), "TB W/L")
    trow("Deciding Set W/L",      SV.get("deciding_set_wl"), AV.get("deciding_set_wl"), "Dec Set W/L")
    trow("5th Set W/L",           SV.get("fifth_set_wl"), AV.get("fifth_set_wl"), "5th Set")
    trow("vs Left-Handed",        SV.get("vs_lefthanded_wl"), AV.get("vs_lefthanded_wl"), "vs Left")
    trow("vs Right-Handed",       SV.get("vs_righthanded_wl"), AV.get("vs_righthanded_wl"), "vs Right")
    trow("After Winning 1st Set",
         f"{SV['after_winning_first_set_pct']}%" if SV.get("after_winning_first_set_pct") else None,
         f"{AV['after_winning_first_set_pct']}%" if AV.get("after_winning_first_set_pct") else None,
         "After Win 1stSet")
    trow("After Losing 1st Set",
         f"{SV['after_losing_first_set_pct']}%" if SV.get("after_losing_first_set_pct") else None,
         f"{AV['after_losing_first_set_pct']}%" if AV.get("after_losing_first_set_pct") else None,
         "After Lose 1stSet")

    # ── Surface table ────────────────────────────────────────────────────
    for surf in ["hard", "clay", "grass"]:
        cap   = surf.capitalize()
        sw    = SC.get(f"csv_{surf}_wl")
        sp    = SC.get(f"csv_{surf}_win_pct")
        aw    = AC.get(f"csv_{surf}_wl")
        ap    = AC.get(f"csv_{surf}_win_pct")
        if sw and aw:
            prev = html
            pat  = rf'(<td>{cap}</td><td class="sv">)[\d\u2013\-]+(</td><td class="av">)[\d\u2013\-]+(</td><td class="sv">)[\d.]+%(</td><td class="av">)[\d.]+%'
            html = re.sub(pat,
                          lambda m, sv=sw, spc=sp, av=aw, apc=ap:
                              f'{m.group(1)}{sv}{m.group(2)}{av}{m.group(3)}{spc}%{m.group(4)}{apc}%',
                          html, count=1)
            if html != prev: updated.append(f"{cap}: S {sw}({sp}%) A {aw}({ap}%)")

    # ── Per-slam wins ────────────────────────────────────────────────────
    for slam_name, sx_key in [
        ("Australian Open", "gs_ao"),
        ("Roland Garros",   "gs_rg"),
        ("Wimbledon",       "gs_wimbledon"),
        ("US Open",         "gs_uso"),
    ]:
        sv = SX.get(sx_key)
        av = AX.get(sx_key)
        if sv is not None or av is not None:
            prev = html
            esc  = re.escape(slam_name)
            html = re.sub(
                rf'({esc}</td><td class="sv">)\d+(</td><td class="av">)\d+(</td>)',
                lambda m, s=sv or 0, a=av or 0:
                    f'{m.group(1)}{s}{m.group(2)}{a}{m.group(3)}',
                html, count=1
            )
            if html != prev: updated.append(f"{slam_name}: S={sv} A={av}")

    # ── Clutch Score rows (tiebreaks / deciding sets / BP) ────────────────
    def clutch_pair(label, pat, sv, av):
        nonlocal html
        prev = html
        if sv is not None:
            ms = list(re.finditer(pat, html))
            if ms:
                m = ms[0]
                html = html[:m.start()] + m.group(1) + str(sv) + m.group(2) + html[m.end():]
        if av is not None:
            ms = list(re.finditer(pat, html))
            if len(ms) >= 2:
                m = ms[1]
                html = html[:m.start()] + m.group(1) + str(av) + m.group(2) + html[m.end():]
        if html != prev: updated.append(f"Clutch {label}: {sv}/{av}")

    clutch_pair("Tiebreaks%",
        r'(Tiebreaks Won %</span><span class="clutch-row-val [sa]">)[\d.]+(%)',
        SV.get("tiebreaks_won_pct"), AV.get("tiebreaks_won_pct"))
    clutch_pair("Deciding Sets%",
        r'(Deciding Sets Won %</span><span class="clutch-row-val [sa]">)[\d.]+(%)',
        SV.get("deciding_sets_won_pct"), AV.get("deciding_sets_won_pct"))
    clutch_pair("BP Saved%",
        r'(BP Saved %</span><span class="clutch-row-val [sa]">)[\d.]+(%)',
        SV.get("bp_saved_pct"), AV.get("bp_saved_pct"))
    clutch_pair("BP Converted%",
        r'(BP Converted %</span><span class="clutch-row-val [sa]">)[\d.]+(%)',
        SV.get("bp_converted_pct"), AV.get("bp_converted_pct"))

    # ── vs Legends table ─────────────────────────────────────────────────
    prev = html
    if s_sh:
        html = re.sub(r'(highlight-s">\$)[\d.]+M(</td>)',
                      rf'\g<1>{s_sh.lstrip("$")}\2', html, count=1)
    if a_sh:
        html = re.sub(r'(highlight-a">\$)[\d.]+M(</td>)',
                      rf'\g<1>{a_sh.lstrip("$")}\2', html, count=1)
    if html != prev: updated.append(f"Legends: {s_sh}/{a_sh}")

    # ── Timestamp ────────────────────────────────────────────────────────
    today = datetime.now(timezone.utc).strftime("%-d %B %Y")
    html  = re.sub(r"Last updated: [^<\"]+", f"Last updated: {today}", html)

    for msg in updated:
        print(f"  ✓ {msg}")

    if html != orig:
        with open("index.html", "w") as f:
            f.write(html)
        print(f"\n  ✅ index.html saved ({today}) — {len(updated)} fields updated")
    else:
        print("\n  index.html unchanged")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print(f"=== sincaraz.app scraper v10 — {datetime.now(timezone.utc).isoformat()} ===\n")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        print("⚠  ANTHROPIC_API_KEY not set — vision sources skipped\n")

    result = {"scraped_at": datetime.now(timezone.utc).isoformat(),
              "sinner": {}, "alcaraz": {}}

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
