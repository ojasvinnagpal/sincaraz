# Sincaraz.app — Complete Handoff Document v3
**Last updated: 2 April 2026**

---

## What This Project Is

**sincaraz.app** is a single-page tennis statistics website comparing Jannik Sinner and Carlos Alcaraz. It has tabs for: Home, H2H, Serve Stats, Return Stats, Pressure/Clutch, Grand Slams, Records, Legends Comparison, Expert Analysis, and Insights. Stats update automatically daily via a GitHub Actions scraper.

---

## 🚨 MOST URGENT ISSUE — TABS NOT WORKING

**The navigation tabs (H2H, Serve, Return, Pressure, Slams, Records, etc.) are NOT opening when clicked.** Only the Home tab displays correctly. Every other tab click does nothing.

### Root Cause
The `showPage()` function used `event.target` as an implicit global to highlight the active tab. This is unreliable and throws a silent error that prevents the page switch entirely.

### Fix Applied (but NOT yet pushed as of this handoff)
In `index.html`, `showPage` was changed from:
```javascript
// BROKEN
function showPage(id){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  event.target.classList.add('active');   // ← implicit event, unreliable
  window.scrollTo(0,0);
}
// Called as: onclick="showPage('h2h')"
```

To:
```javascript
// FIXED
function showPage(id, el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  const page = document.getElementById('page-'+id);
  if(page) page.classList.add('active');
  if(el) el.classList.add('active');
  window.scrollTo(0,0);
}
// Called as: onclick="showPage('h2h',this)"   ← pass 'this' explicitly
```

All 10 nav tab `onclick` attributes were updated to pass `this`. The latest `index.html` in the Claude output has this fix. **Download it and push it — that's the first thing to do.**

### Additional JS Bugs Fixed in Same Session
1. `initApp()` used `await` but wasn't declared `async` — crashed entire JS engine on load
2. `async async function initVotes()` — duplicate `async` keyword, also a crash

All three bugs were fixed in the current `index.html` output file.

---

## Infrastructure

| Service | Details |
|---|---|
| **Website** | https://sincaraz.app |
| **GitHub** | https://github.com/ojasvinnagpal/sincaraz |
| **Netlify** | app.netlify.com, team: Ojasvin, $9/month Personal plan |
| **DNS** | Hostinger: A → 75.2.60.5, CNAME www → sincaraz.netlify.app |
| **Supabase** | https://nxwntslftzwosmcwqjxk.supabase.co (voting only — **pauses after 7 days inactivity on free tier**) |
| **Google Analytics** | G-NSCL5WC0B7 |
| **Google Search Console** | domain: sincaraz.app |
| **Anthropic API** | Claude Vision used in scraper. Key in GitHub secret `ANTHROPIC_API_KEY` |

---

## Repository Files

```
sincaraz/
├── index.html              ← Full website (single HTML file, ~1950 lines)
├── scrape_atp.py           ← Daily scraper (~544 lines Python)
├── scraped_stats.json      ← Scraper output, fetched by browser at runtime
└── .github/workflows/
    └── daily-scraper.yml   ← GitHub Actions (6AM UTC daily + manual trigger)
```

---

## How Everything Works

### Pipeline
```
GitHub Actions (6AM UTC)
  → python scrape_atp.py
      → Source 1: ATP XHR intercept → career stats, rankings, serve/return
      → Source 2: ATP W/L page vision → situational records, ratings
      → Source 3: Wikipedia vision → GS counts, year-end rankings
      → compute() → age, days at #1, tiebreak%, etc.
  → writes scraped_stats.json
  → updates "Last updated" timestamp in index.html
  → git commit + push → Netlify redeploys
  → browser loads sincaraz.app
      → loadScrapedStats() fetches scraped_stats.json from GitHub raw URL
      → applyStats() populates all 115 stat elements via getElementById()
```

### Critical Architecture Point
The scraper does NOT regex-patch stats into `index.html`. It only writes `scraped_stats.json` and updates a timestamp. All stats display dynamically via JavaScript at page load.

---

## Scraper — Data Sources

### Source 1: ATP XHR Intercept ✅ WORKING
- Playwright intercepts XHR from `https://www.atptour.com/en/players/{name}/{id}/player-stats`
- Captures `/players/hero/{id}` → career W/L, ranking, prize money, titles, YTD, coach
- Captures `/stats/{id}/` → all serve and return percentages
- **Player IDs:** Sinner = `s0ag`, Alcaraz = `a0e2`
- **Known issue:** `atp_points` field returns null — XHR stopped including it

### Source 2: ATP Win/Loss Vision ✅ WORKING
- URL: `https://www.atptour.com/en/players/{name}/{id}/atp-win-loss`
- 5 screenshots, clicks "Career" tab
- Extracts: serve/return/pressure ratings, tiebreak W/L, deciding set W/L, finals W/L, GS W/L, Masters W/L, surface W/L, indoor/outdoor, vs top10, vs left/righthanded, after 1st set %
- **Intermittent:** return_rating and under_pressure_rating sometimes missing for Alcaraz

### Source 3: Wikipedia Vision ⚠️ PARTIALLY WORKING
- URL: `https://en.wikipedia.org/wiki/{Player}_career_statistics`
- 5 screenshots + 2s extra wait
- Extracts: GS wins per slam, masters_titles, year_end_rankings
- **Known issues:**
  - Sinner wimbledon_wins sometimes returns 0 → GS_FLOOR corrects to 1
  - Alcaraz masters_titles sometimes returns 15 (total titles, not Masters) → capped at 10, floor (8) used
  - weeks_at_no1 never successfully extracted → floor used
- **Prompt uses `.replace("{name}", name)` — see Critical Bug below**

### Source 4: Flashscore/TennisStats Vision ❌ REMOVED
- Permanently blocks headless browsers, returns `{}` every run
- Removed from scraper entirely

### Source 5: JeffSackmann CSV ❌ REMOVED
- 2026 data not published, returns wrong/empty values
- Removed from scraper entirely

### Source 6: Computed ✅ WORKING
- `age` — live from DOB
- `avg_aces_match`, `avg_df_match` — from XHR career stats
- `gs_total`, `big_titles` — summed
- `tiebreaks_won_pct` — from tiebreak_wl string e.g. "111-60" → 64.9%
- `deciding_sets_won_pct` — same from deciding_set_wl
- `days_at_no1` — weeks_at_no1 × 7
- `after_winning/losing_first_set_pct` — direct from vision_wl

---

## ☠️ CRITICAL BUG — Check Every Single Time

`WIKI_PROMPT` contains example JSON with `{"2022": 10}` in the text. If `.format(name=name)` is used, Python throws `KeyError: "2022"` and the **entire scraper crashes**.

**Line ~397 in scrape_atp.py MUST say:**
```python
data = vision(img_blocks(paths), WIKI_PROMPT.replace("{name}", name))
```
**NOT:**
```python
data = vision(img_blocks(paths), WIKI_PROMPT.format(name=name))  # CRASHES
```

Run this every time after modifying scrape_atp.py:
```bash
sed -i '' 's/WIKI_PROMPT.format(name=name)/WIKI_PROMPT.replace("{name}", name)/' scrape_atp.py
sed -i '' 's/WL_PROMPT.format(name=name)/WL_PROMPT.replace("{name}", name)/' scrape_atp.py
```

---

## Hardcoded Values — Must Update Manually

### 1. H2H Record (update after every Sinner-Alcaraz match)
In `scrape_atp.py`, `PLAYERS` config at top of file:
```python
"sinner":  { "h2h_wins": 6,  "h2h_losses": 12 }   # Alcaraz leads 12–6 as of Apr 2026
"alcaraz": { "h2h_wins": 12, "h2h_losses": 6  }
```

### 2. GS_FLOOR (update after every Grand Slam win or milestone)
In `scrape_atp.py`, inside `compute()` function:
```python
GS_FLOOR = {
    "sinner":  {"ao": 2, "rg": 0, "wim": 1, "uso": 1, "m1k": 7, "weeks_no1": 66},
    "alcaraz": {"ao": 1, "rg": 2, "wim": 2, "uso": 2, "m1k": 8, "weeks_no1": 65},
}
```
These are fallback values used when Wikipedia returns wrong/null data.

### 3. Match History in index.html (update after every meeting)
`const matches = [...]` — full H2H match list (currently 25 matches through Miami 2026)

### 4. Momentum Matches in index.html (update after every meeting)
`const momentumMatches = [...]` — last 8 matches

---

## scraped_stats.json — All Fields

### Top Level (both players)
| Field | Source | Status |
|---|---|---|
| `h2h_wins` / `h2h_losses` | PLAYERS config | ⚠️ Hardcoded |
| `career_wl`, `career_wins`, `career_losses`, `career_win_pct` | ATP XHR | ✅ Dynamic |
| `career_titles` | ATP XHR | ✅ Dynamic |
| `ranking` | ATP XHR | ✅ Dynamic |
| `atp_points` | ATP XHR | ❌ Null (field stopped returning) |
| `ytd_wl`, `ytd_wins`, `ytd_losses`, `ytd_win_pct`, `ytd_titles` | ATP XHR | ✅ Dynamic |
| `prize_career` | ATP XHR | ✅ Dynamic |
| `coach` | ATP XHR | ✅ Dynamic (may lag — Alcaraz shows "Samuel Lopez", Ferrero left Dec 2025) |

### career{} — All Serve/Return Stats
| Field | Source | Status |
|---|---|---|
| `aces`, `double_faults` | ATP XHR | ✅ Dynamic |
| `first_serve_pct`, `first_serve_won_pct`, `second_serve_won_pct` | ATP XHR | ✅ Dynamic |
| `bp_saved_pct`, `bp_faced`, `service_games_played`, `service_games_won_pct`, `service_points_won_pct` | ATP XHR | ✅ Dynamic |
| `first_return_won_pct`, `second_return_won_pct`, `bp_converted_pct`, `bp_opportunities` | ATP XHR | ✅ Dynamic |
| `return_games_played`, `return_games_won_pct`, `return_points_won_pct`, `total_points_won_pct` | ATP XHR | ✅ Dynamic |

### vision_wl{} — Situational Records
| Field | Source | Status |
|---|---|---|
| `overall_wl`, `grand_slams_wl`, `masters_wl`, `finals_wl` | ATP W/L vision | ✅ Dynamic |
| `deciding_set_wl`, `fifth_set_wl`, `tiebreak_wl` | ATP W/L vision | ✅ Dynamic |
| `vs_top10_wl`, `on_hard_wl`, `on_clay_wl`, `on_grass_wl` | ATP W/L vision | ✅ Dynamic |
| `carpet_wl`, `indoor_wl`, `outdoor_wl` | ATP W/L vision | ✅ Dynamic |
| `after_winning_first_set_pct`, `after_losing_first_set_pct` | ATP W/L vision | ✅ Dynamic |
| `vs_righthanded_wl`, `vs_lefthanded_wl` | ATP W/L vision | ✅ Dynamic |
| `serve_rating` | ATP W/L vision | ✅ Dynamic |
| `return_rating`, `under_pressure_rating` | ATP W/L vision | ⚠️ Intermittent |

### vision_wiki{} — Wikipedia Data
| Field | Source | Status |
|---|---|---|
| `ao_wins`, `rg_wins`, `wimbledon_wins`, `uso_wins` | Wikipedia vision + GS_FLOOR | ⚠️ Dynamic with fallback |
| `masters_titles` | Wikipedia vision, capped at 10 | ⚠️ Dynamic with fallback |
| `year_end_rankings` | Wikipedia vision | ✅ Dynamic |
| `weeks_at_no1` | Wikipedia vision | ❌ Never extracted — floor used |
| `days_at_no1` | Wikipedia vision | ❌ Never extracted |

### computed{} — Derived Fields
| Field | Source | Status |
|---|---|---|
| `age` | DOB computed | ✅ Dynamic |
| `avg_aces_match`, `avg_df_match` | XHR computed | ✅ Dynamic |
| `gs_ao`, `gs_rg`, `gs_wimbledon`, `gs_uso`, `gs_total` | Wiki + floor | ⚠️ Dynamic with fallback |
| `masters_titles`, `big_titles` | Wiki + floor | ⚠️ Dynamic with fallback |
| `weeks_at_no1` | GS_FLOOR fallback | ⚠️ Floor only (66/65) |
| `days_at_no1` | weeks × 7 | ✅ Dynamic (462/455) |
| `tiebreaks_won_pct` | Computed from tiebreak_wl | ✅ Dynamic (64.9% / 62.0%) |
| `deciding_sets_won_pct` | Computed from deciding_set_wl | ✅ Dynamic (66.7% / 71.0%) |
| `after_winning_first_set_pct` | vision_wl direct | ✅ Dynamic (90.5% / 93.8%) |
| `after_losing_first_set_pct` | vision_wl direct | ✅ Dynamic (43% / 45.1%) |

### Fields Permanently Removed (no source exists)
- `fastest_serve_kmh/mph` — was hardcoded floor, not real data
- `longest_win_streak`, `current_win_streak` — no scrapeable source
- `wins_straight_sets_pct` — source (Sackmann CSV) removed
- `breaks_per_set`, `tiebreaks_per_match`, `avg_match_duration` — TennisStats blocked
- `current_form_str` — TennisStats blocked

---

## index.html — Architecture

### Dynamic Stats Loading (at page load)
```javascript
async function loadScrapedStats() {
  const STATS_URL = 'https://raw.githubusercontent.com/ojasvinnagpal/sincaraz/main/scraped_stats.json';
  const res = await fetch(STATS_URL + '?t=' + Date.now());
  return await res.json();
}

async function initApp() {
  renderTicker();
  renderMatches();
  renderRecords();
  renderExpert();
  const stats = await loadScrapedStats();
  applyStats(stats);
}
initApp();
```

### Element ID Convention (115 total)
- `s-{stat}` / `a-{stat}` — profile spans
- `t-s-{stat}` / `t-a-{stat}` — comparison table
- `sv-s-{stat}` / `sv-a-{stat}` — serve page
- `rt-s-{stat}` / `rt-a-{stat}` — return page
- `pr-s-{stat}` / `pr-a-{stat}` — pressure page
- `c-s-{stat}` / `c-a-{stat}` — clutch score
- `h2h-score-s` / `h2h-score-a` — H2H hero numbers

### Pages (10 tabs)
| Tab | Page ID | Status |
|---|---|---|
| Home | `page-home` | ✅ Works, has `class="page active"` by default |
| H2H | `page-h2h` | ❌ Not opening (tab bug — fix in latest index.html) |
| Serve Stats | `page-serve` | ❌ Not opening |
| Return Stats | `page-return` | ❌ Not opening |
| Pressure | `page-pressure` | ❌ Not opening |
| Grand Slams | `page-slams` | ❌ Not opening |
| Records | `page-records` | ❌ Not opening |
| Legends | `page-legends` | ❌ Not opening |
| Expert | `page-expert` | ❌ Not opening |
| Insights | `page-insights` | ❌ Not opening |

**All 9 non-home tabs broken.** The fix is in the current `index.html` output. Push it.

### Hardcoded Editorial Content (NOT scraped — these are written content)
- `const matches = [...]` — H2H match history (25 matches through Miami 2026)
- `const momentumMatches = [...]` — last 8 matches
- `const records = [...]` — records and achievements cards
- `const trivia = [...]` — fun facts
- `const expertVerdicts = [...]` — who's better analysis
- `renderTicker()` items — scrolling headline ticker

---

## GitHub Actions Workflow

```yaml
name: Daily ATP Stats Scraper
on:
  schedule:
    - cron: '0 6 * * *'   # 6AM UTC daily
  workflow_dispatch:        # manual trigger from Actions tab
jobs:
  scrape-and-deploy:
    runs-on: ubuntu-latest
    permissions: {contents: write}
    steps:
      - checkout
      - python 3.11
      - pip install playwright anthropic
      - playwright install chromium
      - python scrape_atp.py  (env: ANTHROPIC_API_KEY)
      - show scraped_stats.json (debugging step)
      - git commit scraped_stats.json + index.html
      - git push
      - curl Netlify deploy hook
```

**GitHub Secrets required:**
- `ANTHROPIC_API_KEY` — Anthropic console → API Keys
- `NETLIFY_DEPLOY_HOOK` — Netlify → Site → Build hooks
- `GITHUB_TOKEN` — auto-provided

---

## Local Development

```bash
cd ~/Downloads/sincaraz
source venv/bin/activate
ANTHROPIC_API_KEY=your_key python scrape_atp.py
```

Outputs `scraped_stats.json`. Push it before opening `index.html` in browser (the HTML fetches JSON from GitHub raw URL, not locally).

---

## Last Known Good Data (from 2 April 2026 run)

| Stat | Sinner | Alcaraz |
|---|---|---|
| Ranking | #2 | #1 |
| Career W/L | 340–88 (79.4%) | 297–67 (81.6%) |
| Career Titles | 26 | 26 |
| Grand Slams | 4 (AO×2, W×1, US×1) | 7 (AO×1, RG×2, W×2, US×2) |
| Masters 1000 | 7 | 8 |
| H2H | 6 wins | 12 wins |
| Weeks at #1 | 66 | 65 |
| Days at #1 | 462 | 455 |
| Prize Money | $61,191,211 | $64,336,028 |
| YTD W/L | 19–2 | 17–2 |
| Serve Rating | 300 | — |
| Tiebreaks Won | 64.9% | 62.0% |
| Deciding Sets Won | 66.7% | 71.0% |
| After Winning 1st Set | 90.5% | 93.8% |
| After Losing 1st Set | 43.0% | 45.1% |
| Coach | Vagnozzi / Cahill | Samuel Lopez* |

*Alcaraz parted with Juan Carlos Ferrero in Dec 2025. ATP XHR shows "Samuel Lopez" which may be a temporary/incorrect value.

---

## Immediate Action Items (in order)

1. **Push the current `index.html`** — fixes all 9 broken tabs
   ```bash
   cd ~/Downloads/sincaraz
   git add index.html
   git commit -m "fix: showPage pass element explicitly, fix all broken tabs"
   git pull --rebase && git push
   ```

2. **Verify tabs work** — visit sincaraz.app and click every tab

3. **Trigger GitHub Action manually** — Actions tab → Daily ATP Stats Scraper → Run workflow

4. **Fix masters_titles cap** — Alcaraz Wikipedia sometimes returns 15 instead of 8. In `scrape_atp.py` find `m1k = raw_m1k if (0 < raw_m1k <= 15)` and change 15 to 10.

---

## Known Issues Not Yet Fixed

| Issue | Details | Difficulty |
|---|---|---|
| `atp_points` null | XHR field stopped returning. Try intercepting ATP Rankings page XHR instead | Medium |
| Alcaraz coach stale | Shows "Samuel Lopez" — ATP XHR lags on coach updates | Easy — hardcode fallback |
| `return_rating` intermittent | ATP W/L vision misses it ~30% of runs for Alcaraz | Medium |
| `weeks_at_no1` from wiki | Never extracted — floor fallback used forever | Hard |
| All tabs broken | Fixed in latest index.html — just needs pushing | **Done — push now** |

---

## SEO State

- Google Search Console: 1 page indexed, "sincaraz" query up 367%
- Competitor: alcarazvssinner.app (page 3, stale data)
- Schema: FAQPage + WebSite markup implemented
- Meta title: "Sinner vs Alcaraz: Live H2H Stats, Career Comparison & Rivalry Tracker | Sincaraz"
