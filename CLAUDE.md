# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**sincaraz.app** — A real-time tennis statistics comparison site tracking the Sinner vs. Alcaraz H2H rivalry. Stats auto-update daily via GitHub Actions + Claude Vision AI.

## Running the Scraper Locally

```bash
source venv/bin/activate
ANTHROPIC_API_KEY=your_key python scrape_atp.py
```

To regenerate SEO pages (match pages, surface hubs, sitemap):
```bash
source venv/bin/activate
python generate_pages.py
```

## Architecture

**No build step.** The site is a single HTML file (`index.html`) served directly by Netlify.

### Data Pipeline (runs daily at 6AM UTC via GitHub Actions)
1. `scrape_atp.py` — Collects stats from 3 sources, writes `scraped_stats.json`
2. `generate_pages.py` — Generates `/matches/*/`, `/surface/*/`, and `sitemap.xml`
3. Git commit + push → Netlify webhook rebuild

### Data Sources in `scrape_atp.py`
| Source | Method | What it gets |
|--------|--------|--------------|
| ATP XHR intercept | Playwright | Career W/L, rankings, serve/return %, YTD |
| ATP W/L page Vision | Claude Vision screenshot | Situational records, pressure ratings, surface splits |
| Wikipedia Vision | Claude Vision screenshot | Grand Slam counts, year-end rankings |

### Frontend (`index.html`)
- ~2400-line single-page app. 10 tabs toggled by `showPage('id')`.
- On load, `loadScrapedStats()` fetches `scraped_stats.json` from GitHub raw URL.
- `applyStats()` populates ~115 elements via `getElementById()`.

### Generated Directories
- `matches/` — 17 individual H2H match SEO pages (auto-generated, don't edit manually)
- `surface/` — clay/grass/hard hub pages (auto-generated)

## Critical Hardcoded Values (Must Update After Each H2H Match)

In `scrape_atp.py`:
- `PLAYERS["sinner"]["h2h_wins"]` / `h2h_losses` — H2H record
- `GS_FLOOR` dict in `compute()` — Grand Slam floor counts (Wikipedia vision is unreliable)

In `index.html`:
- `const matches = [...]` — Match history array
- `const momentumMatches = [...]` — Momentum section matches

In `generate_pages.py`:
- `MATCHES[]` — Editorial metadata for each match (slug, scores, significance)

## Known Gotchas

- **WIKI_PROMPT contains `{2022}` literal braces** — always use `.replace()` not `.format()` on this string or it will crash.
- `atp_points` is currently null from the ATP API (field was removed upstream).
- `weeks_at_no1` is never reliably extracted from Wikipedia vision; `GS_FLOOR` fallback is always used.
- `return_rating` for Alcaraz intermittently fails vision extraction (~30% of runs).
- Supabase (voting feature) pauses after 7 days of inactivity on free tier.

## Deployment

- **Hosting:** Netlify (custom domain `sincaraz.app`, DNS at Hostinger)
- **Cache headers** in `netlify.toml`: 5min for `/` and `/scraped_stats.json`, 24h for `/matches/*` and `/surface/*`
- **GitHub secrets required:** `ANTHROPIC_API_KEY`, `NETLIFY_DEPLOY_HOOK`

## Key Files

| File | Purpose |
|------|---------|
| `index.html` | Entire frontend SPA |
| `scrape_atp.py` | Daily data pipeline |
| `generate_pages.py` | Programmatic SEO page generator |
| `scraped_stats.json` | Daily scraper output (committed to git) |
| `netlify.toml` | Deployment + cache config |
| `.github/workflows/daily-scraper.yml` | CI/CD schedule |
| `sincaraz_handoff_v3.md` | Full project documentation with all stat element IDs |
| `scrape_readme.md` | Data source architecture notes |
