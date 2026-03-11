# sincaraz.app Scraper — How It Works

## The core problem with ATP Tour

ATP's website is an Angular SPA. The raw HTML has zero data — just `{{stats || 0}}` placeholders.
Data is loaded via internal JSON API calls made by JavaScript. This is why our previous
Playwright scraper always returned `{}`.

## Two approaches (one primary, one fallback)

---

### Approach A: API Intercept (scrape_atp.py) ← DEPLOY THIS

Playwright loads the ATP stats page and listens to all outgoing network requests.
When the Angular app fires its internal API calls to fetch stats, Playwright captures
those JSON responses directly — clean, structured data, no regex needed.

**How to test locally (run this in your terminal):**
```bash
pip install playwright
python -m playwright install chromium
python scrape_atp.py
```

**What to check after running:**
- `/home/claude/sinner_captured_api.json` — all XHR calls + data intercepted
- `/home/claude/sinner_stats.png` — what Playwright actually rendered
- `/home/claude/sinner_rendered.html` — full Angular-rendered HTML

**If XHR capture works:** you'll see JSON with fields like
`ServiceGamesWon`, `Aces`, `FirstServePointsWon`, etc. in the captured file.

**If it doesn't work:** ATP may be blocking headless browsers. Use Approach B.

---

### Approach B: Vision AI (scrape_vision.py) ← FALLBACK

Playwright takes screenshots of the rendered page, sends them to Claude Vision,
which reads the numbers off the page exactly like a human would and returns JSON.

**Pros:** Works on ANY website, impossible to block, gets ALL visible stats
**Cons:** Requires `ANTHROPIC_API_KEY` env var in GitHub Actions secret, costs ~$0.01/run

**How to enable:**
1. Add `ANTHROPIC_API_KEY` as a GitHub Actions secret
2. Switch the workflow to run `scrape_vision.py` instead of `scrape_atp.py`

**What stats it can extract:** Everything visible on the page — serve %, return %,
break points, aces, rankings, prize money, surface splits, YTD record, etc.

---

## Stats coverage comparison

| Source | W/L | Serve % | Return % | Break pts | Surface splits | Aces | Rankings |
|--------|-----|---------|----------|-----------|----------------|------|----------|
| Wikipedia | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| ATP API Intercept | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Vision AI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Recommended workflow

1. **Primary:** API intercept (free, fast, no API key needed)
2. **Fallback:** Vision AI (requires ANTHROPIC_API_KEY, ~$0.01/run)
3. **Last resort:** Wikipedia (free, only basic stats)

The scraper tries them in order and uses whichever works.
