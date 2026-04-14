"""
generate_pages.py — Programmatic SEO page generator for sincaraz.app

Generates:
  matches/<slug>/index.html  — one page per H2H match (16+)
  surface/clay/index.html    — Clay H2H hub
  surface/hard/index.html    — Hard court H2H hub
  surface/grass/index.html   — Grass H2H hub
  stats/<topic>/index.html   — Long-tail keyword comparison pages
  sitemap.xml                — Full sitemap

Run after scrape_atp.py so h2h_matches from JSON takes priority.
"""

import json
import os
import re
from datetime import datetime, timezone
try:
    import anthropic as _anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

BASE_URL = "https://sincaraz.app"

# ─── Match data ───────────────────────────────────────────────────────────────
# Editorial fields (notes, duration) live here; scraped JSON overrides date/score/winner.
# Update this list after each new Sinner-Alcaraz meeting.

MATCHES = [
    {
        "slug":    "2026-monte-carlo-final",
        "date":    "April 2026",
        "year":    "2026",
        "event":   "Monte-Carlo Masters",
        "location":"Monte-Carlo, Monaco",
        "round":   "Final",
        "surface": "clay",
        "winner":  "sinner",
        "score":   "7–6(5) 6–3",
        "duration":"1h 52m",
        "note":    "Sinner claims his first Monte-Carlo title, closing to 7–10 in the H2H. He dominates the second set after edging a tight opener, snapping Alcaraz's clay winning run.",
        "sinner_rank": 2, "alcaraz_rank": 1,
    },
    {
        "slug":    "2025-atp-finals-final",
        "date":    "November 2025",
        "year":    "2025",
        "event":   "ATP Finals",
        "location":"Turin, Italy",
        "round":   "Final",
        "surface": "hard",
        "winner":  "sinner",
        "score":   "7–6(4) 7–5",
        "duration":"2h 15m",
        "note":    "Sinner defends his Turin title and closes 2025 with the H2H points total perfectly tied at 1,651 each — the most statistically even rivalry in modern tennis.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2025-us-open-final",
        "date":    "September 2025",
        "year":    "2025",
        "event":   "US Open",
        "location":"New York, USA",
        "round":   "Final",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "6–2 3–6 6–1 6–4",
        "duration":"2h 42m",
        "note":    "Alcaraz reclaims World No. 1 and ends Sinner's run of three consecutive hardcourt Grand Slam titles. A dominant performance after a slow second set.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2025-cincinnati-open-final",
        "date":    "August 2025",
        "year":    "2025",
        "event":   "Cincinnati Open",
        "location":"Cincinnati, USA",
        "round":   "Final",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "5–0 ret.",
        "duration":"0h 23m",
        "note":    "Sinner retires due to illness with Alcaraz leading 5–0 in the first set. Alcaraz wins the title but both players downplay the result given the circumstances.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2025-wimbledon-final",
        "date":    "July 2025",
        "year":    "2025",
        "event":   "Wimbledon",
        "location":"London, UK",
        "round":   "Final",
        "surface": "grass",
        "winner":  "sinner",
        "score":   "4–6 6–4 6–4 6–4",
        "duration":"3h 04m",
        "note":    "Sinner wins his first Wimbledon title and ends Alcaraz's 24-match grass winning streak. After dropping the first set, Sinner wins 18 of the next 20 games.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2025-roland-garros-final",
        "date":    "June 2025",
        "year":    "2025",
        "event":   "Roland Garros",
        "location":"Paris, France",
        "round":   "Final",
        "surface": "clay",
        "winner":  "alcaraz",
        "score":   "4–6 6–7(4) 6–4 7–6(3) 7–6(2)",
        "duration":"5h 29m",
        "note":    "The longest Grand Slam final in history. Sinner holds 3 match points in the fourth set. Alcaraz saves them all and wins the fifth-set tiebreak. One of the greatest matches ever played.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2025-italian-open-final",
        "date":    "May 2025",
        "year":    "2025",
        "event":   "Italian Open",
        "location":"Rome, Italy",
        "round":   "Final",
        "surface": "clay",
        "winner":  "alcaraz",
        "score":   "7–6(5) 6–1",
        "duration":"1h 43m",
        "note":    "Their first Masters 1000 final together. Alcaraz snaps Sinner's 26-match winning streak with a dominant second set in front of a partisan Italian crowd.",
        "sinner_rank": 1, "alcaraz_rank": 2,
    },
    {
        "slug":    "2024-china-open-final",
        "date":    "October 2024",
        "year":    "2024",
        "event":   "China Open",
        "location":"Beijing, China",
        "round":   "Final",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "6–7(6) 6–4 7–6(3)",
        "duration":"3h 21m",
        "note":    "The longest final in China Open history. Alcaraz comes from a set down to snap Sinner's 15-match winning streak, winning the decisive tiebreak 7–3.",
        "sinner_rank": 1, "alcaraz_rank": 3,
    },
    {
        "slug":    "2024-roland-garros-sf",
        "date":    "June 2024",
        "year":    "2024",
        "event":   "Roland Garros",
        "location":"Paris, France",
        "round":   "Semifinal",
        "surface": "clay",
        "winner":  "alcaraz",
        "score":   "2–6 6–3 3–6 6–4 6–3",
        "duration":"4h 09m",
        "note":    "Both players dealing with injuries throughout. A gruelling five-setter that Alcaraz wins from 2 sets to 1 down. He goes on to win the title.",
        "sinner_rank": 2, "alcaraz_rank": 3,
    },
    {
        "slug":    "2024-indian-wells-sf",
        "date":    "March 2024",
        "year":    "2024",
        "event":   "Indian Wells",
        "location":"Indian Wells, USA",
        "round":   "Semifinal",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "1–6 6–3 6–2",
        "duration":"2h 05m",
        "note":    "Alcaraz recovers from a bagel first set to win 12 of the last 13 games and snap Sinner's 19-match winning streak in dominant fashion.",
        "sinner_rank": 3, "alcaraz_rank": 2,
    },
    {
        "slug":    "2023-china-open-sf",
        "date":    "October 2023",
        "year":    "2023",
        "event":   "China Open",
        "location":"Beijing, China",
        "round":   "Semifinal",
        "surface": "hard",
        "winner":  "sinner",
        "score":   "7–6(4) 6–1",
        "duration":"1h 55m",
        "note":    "Sinner's first straight-sets win over Alcaraz, and a dominant one. He wins 7 of the last 8 games after taking a tight first set tiebreak.",
        "sinner_rank": 4, "alcaraz_rank": 1,
    },
    {
        "slug":    "2023-miami-open-sf",
        "date":    "March 2023",
        "year":    "2023",
        "event":   "Miami Open",
        "location":"Miami, USA",
        "round":   "Semifinal",
        "surface": "hard",
        "winner":  "sinner",
        "score":   "6–7(4) 6–4 6–2",
        "duration":"3h 02m",
        "note":    "Sinner dashes Alcaraz's Sunshine Double hopes by winning from a set down. He dominates the third set 6–2 to advance. Alcaraz had won Indian Wells that year.",
        "sinner_rank": 9, "alcaraz_rank": 1,
    },
    {
        "slug":    "2023-indian-wells-sf",
        "date":    "March 2023",
        "year":    "2023",
        "event":   "Indian Wells",
        "location":"Indian Wells, USA",
        "round":   "Semifinal",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "7–6(4) 6–3",
        "duration":"1h 52m",
        "note":    "Alcaraz wins in straight sets in a tighter match than the scoreline suggests. He goes on to win the tournament.",
        "sinner_rank": 13, "alcaraz_rank": 2,
    },
    {
        "slug":    "2022-us-open-qf",
        "date":    "September 2022",
        "year":    "2022",
        "event":   "US Open",
        "location":"New York, USA",
        "round":   "Quarterfinal",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "6–3 6–7(7) 6–7(0) 7–5 6–3",
        "duration":"5h 15m",
        "note":    "Finished at 2:50 AM — the latest finish in US Open history. Alcaraz saves a match point in the fourth set. One of the most dramatic night sessions in Slam history. Alcaraz wins the title.",
        "sinner_rank": 13, "alcaraz_rank": 3,
    },
    {
        "slug":    "2022-croatia-open-final",
        "date":    "July 2022",
        "year":    "2022",
        "event":   "Croatia Open",
        "location":"Umag, Croatia",
        "round":   "Final",
        "surface": "clay",
        "winner":  "sinner",
        "score":   "6–7(5) 6–1 6–1",
        "duration":"2h 26m",
        "note":    "Sinner wins his first clay title by breadsticking Alcaraz twice in a dominant turnaround after losing a close first set.",
        "sinner_rank": 13, "alcaraz_rank": 4,
    },
    {
        "slug":    "2022-wimbledon-r16",
        "date":    "July 2022",
        "year":    "2022",
        "event":   "Wimbledon",
        "location":"London, UK",
        "round":   "Round of 16",
        "surface": "grass",
        "winner":  "sinner",
        "score":   "6–1 6–4 6–7(8) 6–3",
        "duration":"3h 35m",
        "note":    "Sinner upsets Alcaraz in only their second Wimbledon — and first grass — meeting. Alcaraz pushes a tense third-set tiebreak to 10–8 but Sinner closes out the fourth comfortably.",
        "sinner_rank": 13, "alcaraz_rank": 6,
    },
    {
        "slug":    "2021-paris-masters-r32",
        "date":    "November 2021",
        "year":    "2021",
        "event":   "Paris Masters",
        "location":"Paris, France",
        "round":   "Round of 32",
        "surface": "hard",
        "winner":  "alcaraz",
        "score":   "7–6(1) 7–5",
        "duration":"2h 08m",
        "note":    "The first ever ATP meeting between the two future world No. 1s. An 18-year-old Alcaraz upsets a top-20 Sinner in a sign of things to come.",
        "sinner_rank": 10, "alcaraz_rank": 32,
    },
]

SURFACE_INFO = {
    "hard":  {"label": "Hard Court", "color": "#4a9eff", "emoji": "🏟️"},
    "clay":  {"label": "Clay",       "color": "#e8600a", "emoji": "🔶"},
    "grass": {"label": "Grass",      "color": "#2e8b57", "emoji": "🌿"},
}

SLAM_EVENTS = {"US Open", "Australian Open", "Roland Garros", "Wimbledon"}


# ─── Shared CSS ───────────────────────────────────────────────────────────────

PAGE_CSS = """
  :root{--bg:#0a0a0f;--bg2:#111118;--bg3:#1a1a24;--border:#2a2a3a;
        --sinner:#4a9eff;--alcaraz:#ff6b35;--gold:#f5c842;--text:#e8e8f0;--text-dim:#888}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh}
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
  .bebas{font-family:'Bebas Neue',Impact,sans-serif;letter-spacing:.04em}
  a{color:var(--sinner);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:860px;margin:0 auto;padding:0 20px}
  header{border-bottom:1px solid var(--border);padding:16px 0;margin-bottom:40px}
  header .logo{font-size:22px;font-weight:700;color:var(--text)}
  header .logo span.s{color:var(--sinner)}
  header .logo span.a{color:var(--alcaraz)}
  header nav{display:flex;gap:20px;margin-top:8px;font-size:13px;color:var(--text-dim)}
  .breadcrumb{font-size:13px;color:var(--text-dim);margin-bottom:24px}
  .breadcrumb a{color:var(--text-dim)}
  h1{font-size:clamp(26px,5vw,42px);line-height:1.2;margin-bottom:16px;font-weight:800}
  h2{font-size:20px;font-weight:700;margin:32px 0 16px;color:var(--text)}
  .badge{display:inline-block;padding:4px 12px;border-radius:20px;
         font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
  .badge.s{background:rgba(74,158,255,.15);color:var(--sinner)}
  .badge.a{background:rgba(255,107,53,.15);color:var(--alcaraz)}
  .badge.surf{background:var(--bg3);color:var(--text-dim)}
  .result-card{background:var(--bg2);border:1px solid var(--border);
               border-radius:16px;padding:32px;margin:24px 0;text-align:center}
  .score-display{font-family:'Bebas Neue',Impact,sans-serif;
                 font-size:clamp(36px,8vw,64px);letter-spacing:.04em;margin:12px 0}
  .score-display .s{color:var(--sinner)} .score-display .a{color:var(--alcaraz)}
  .match-meta-row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;
                  margin:16px 0;font-size:13px;color:var(--text-dim)}
  .note-box{background:var(--bg3);border-left:3px solid var(--gold);
            border-radius:0 8px 8px 0;padding:16px 20px;margin:24px 0;
            font-size:14px;line-height:1.7;color:var(--text-dim)}
  .match-table{width:100%;border-collapse:collapse;font-size:14px;margin:16px 0}
  .match-table th{text-align:left;padding:10px 12px;font-size:11px;
                  text-transform:uppercase;letter-spacing:.08em;
                  color:var(--text-dim);border-bottom:1px solid var(--border)}
  .match-table td{padding:12px;border-bottom:1px solid var(--border)}
  .match-table tr:last-child td{border-bottom:none}
  .match-table tr:hover td{background:var(--bg3)}
  .win-s td:first-child{border-left:3px solid var(--sinner)}
  .win-a td:first-child{border-left:3px solid var(--alcaraz)}
  .cta{display:block;background:linear-gradient(135deg,var(--sinner),var(--alcaraz));
       color:#fff;text-align:center;padding:18px 32px;border-radius:12px;
       font-weight:700;font-size:16px;margin:32px 0;text-decoration:none}
  .cta:hover{opacity:.9;text-decoration:none}
  .stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
  .stat-box{background:var(--bg2);border:1px solid var(--border);
            border-radius:12px;padding:20px;text-align:center}
  .stat-box .val{font-size:32px;font-family:'Bebas Neue',Impact,sans-serif;
                 letter-spacing:.04em;margin:4px 0}
  .stat-box .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
                 color:var(--text-dim)}
  footer{border-top:1px solid var(--border);padding:32px 0;margin-top:60px;
         font-size:13px;color:var(--text-dim);text-align:center}
  @media(max-width:600px){.stat-grid{grid-template-columns:1fr 1fr}.score-display{font-size:40px}}
"""


# ─── Template helpers ─────────────────────────────────────────────────────────

def page_header():
    return """<header>
  <div class="wrap">
    <div class="logo"><a href="/" style="color:inherit;text-decoration:none">
      <span class="s">SIN</span><span class="a">CAR</span>AZ
    </a></div>
    <nav>
      <a href="/">Home</a>
      <a href="/matches/">All Matches</a>
      <a href="/surface/clay/">Clay H2H</a>
      <a href="/surface/hard/">Hard H2H</a>
      <a href="/surface/grass/">Grass H2H</a>
      <a href="/sinner-vs-alcaraz-head-to-head/">H2H Stats</a>
    </nav>
  </div>
</header>"""


def page_footer():
    year = datetime.now(timezone.utc).year
    return f"""<footer>
  <div class="wrap">
    <p>© {year} <a href="/">sincaraz.app</a> — Sinner vs Alcaraz rivalry stats tracker</p>
    <p style="margin-top:8px">Data sourced from official ATP Tour records. Updated daily.</p>
  </div>
</footer>"""


def html_page(title, description, canonical, body, schema=None):
    schema_block = f'<script type="application/ld+json">{json.dumps(schema, indent=2)}</script>' if schema else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Sincaraz">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
{schema_block}
<style>{PAGE_CSS}</style>
</head>
<body>
{page_header()}
<main class="wrap">
{body}
</main>
{page_footer()}
</body>
</html>"""


def write(path, content):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {path}")


def winner_badge(winner):
    cls = "s" if winner == "sinner" else "a"
    name = "Sinner" if winner == "sinner" else "Alcaraz"
    return f'<span class="badge {cls}">{name} wins</span>'


def surface_badge(surface):
    info = SURFACE_INFO.get(surface, {})
    label = info.get("label", surface.title())
    return f'<span class="badge surf">{info.get("emoji","")}&nbsp;{label}</span>'


# ─── Match pages ──────────────────────────────────────────────────────────────

def match_schema(m):
    winner_name = "Jannik Sinner" if m["winner"] == "sinner" else "Carlos Alcaraz"
    loser_name  = "Carlos Alcaraz" if m["winner"] == "sinner" else "Jannik Sinner"
    return {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": f"Sinner vs Alcaraz — {m['event']} {m['year']} {m['round']}",
        "startDate": m["date"],
        "location": {"@type": "Place", "name": m.get("location", m["event"])},
        "sport": "Tennis",
        "competitor": [
            {"@type": "Person", "name": "Jannik Sinner"},
            {"@type": "Person", "name": "Carlos Alcaraz"},
        ],
        "winner": {"@type": "Person", "name": winner_name},
        "description": m["note"],
        "url": f"{BASE_URL}/matches/{m['slug']}/",
    }


def related_matches(current_slug, all_matches, n=4):
    others = [m for m in all_matches if m["slug"] != current_slug][:n]
    if not others:
        return ""
    rows = ""
    for m in others:
        w_cls = "s" if m["winner"] == "sinner" else "a"
        rows += f"""<tr class="win-{m['winner'][0]}">
  <td><a href="/matches/{m['slug']}/">{m['event']} {m['year']}</a></td>
  <td>{m['round']}</td>
  <td>{surface_badge(m['surface'])}</td>
  <td><span class="badge {w_cls}">{('Sinner' if m['winner']=='sinner' else 'Alcaraz')} wins</span></td>
  <td style="font-family:monospace">{m['score']}</td>
</tr>"""
    return f"""<h2>Other H2H Matches</h2>
<table class="match-table">
<thead><tr><th>Match</th><th>Round</th><th>Surface</th><th>Result</th><th>Score</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""


def parse_set_scores(score_str, winner):
    """Return list of (winner_games, loser_games, tb_str) per set. Skip ret/w/o."""
    if not score_str or re.search(r'ret|w/o', score_str, re.I):
        return []
    sets = []
    for s in score_str.strip().split():
        m = re.match(r'(\d+)[–\-](\d+)(?:\((\d+)\))?', s)
        if not m:
            continue
        g1, g2, tb = int(m.group(1)), int(m.group(2)), m.group(3)
        tb_str = f"({tb})" if tb else ""
        sets.append((g1, g2, tb_str))
    return sets


def set_score_table(m):
    """HTML set-by-set score table. Winner's games listed first per ATP convention."""
    sets = parse_set_scores(m.get("score", ""), m["winner"])
    if not sets:
        return ""
    winner_name = "Sinner" if m["winner"] == "sinner" else "Alcaraz"
    loser_name  = "Alcaraz" if m["winner"] == "sinner" else "Sinner"
    w_cls = "s" if m["winner"] == "sinner" else "a"
    l_cls = "a" if m["winner"] == "sinner" else "s"
    rows = ""
    for i, (g1, g2, tb) in enumerate(sets, 1):
        set_winner = winner_name if g1 > g2 else loser_name
        set_cls    = w_cls if g1 > g2 else l_cls
        rows += f"""<tr>
  <td style="color:var(--text-dim);text-align:center">Set {i}</td>
  <td style="color:var(--{w_cls});font-weight:700;text-align:center">{g1}{tb if g1<g2 else ''}</td>
  <td style="color:var(--{l_cls});text-align:center">{g2}{tb if g1>g2 else ''}</td>
  <td><span class="badge {set_cls}" style="font-size:11px">{set_winner}</span></td>
</tr>"""
    return f"""<h2>Set-by-Set Breakdown</h2>
<table class="match-table" style="max-width:400px">
<thead><tr><th></th><th style="text-align:center;color:var(--{w_cls})">{winner_name}</th><th style="text-align:center;color:var(--{l_cls})">{loser_name}</th><th>Set winner</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""


def auto_generate_note(m):
    """Call Claude Haiku to write a match note for a new scraped match."""
    if not _HAS_ANTHROPIC or not os.environ.get("ANTHROPIC_API_KEY"):
        return ""
    try:
        client = _anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f"Write a 1-sentence match summary for: Sinner vs Alcaraz, {m.get('event','')} {m.get('year','')} {m.get('round','')}, "
                f"winner: {m.get('winner','').title()}, score: {m.get('score','')}. "
                f"Be specific and factual. Under 25 words. No 'impressive'."
            }]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  Note gen failed: {e}")
        return ""


def generate_match_page(m, all_matches):
    winner_name = "Sinner" if m["winner"] == "sinner" else "Alcaraz"
    loser_name  = "Alcaraz" if m["winner"] == "sinner" else "Sinner"
    is_slam     = m["event"] in SLAM_EVENTS
    is_masters  = "masters" in m["event"].lower() or "open" in m["event"].lower()
    event_label = "Grand Slam" if is_slam else ("Masters 1000" if is_masters else "ATP Tour")
    duration_str = f" · {m['duration']}" if m.get("duration") else ""

    note = m.get("note") or ""

    # Build a keyword-rich, specific title
    score_display = m['score'].replace('–','-')
    title = f"Sinner vs Alcaraz {m['event']} {m['year']} {m['round']}: {winner_name} wins {score_display} | Sincaraz"

    # Description: lead with what makes this match memorable
    if note:
        # Use first sentence of note as hook
        hook = note.split('.')[0].rstrip()
        description = f"{hook}. {winner_name} def. {loser_name} {score_display}{duration_str}. Full score, set breakdown & H2H stats."
    else:
        description = (
            f"{winner_name} defeats {loser_name} {score_display} in the {m['round']} of the "
            f"{m['year']} {m['event']}{duration_str}. Score, set breakdown and H2H stats on sincaraz.app."
        )
    # Cap description at 155 chars for SERP
    if len(description) > 155:
        description = description[:152] + "..."

    canonical = f"{BASE_URL}/matches/{m['slug']}/"

    # H2H record up to and including this match (count by position in list)
    idx = next((i for i, x in enumerate(all_matches) if x["slug"] == m["slug"]), None)
    if idx is not None:
        subset = all_matches[idx:]  # matches from this point backwards in time
        sw_then = sum(1 for x in subset if x["winner"] == "sinner")
        aw_then = sum(1 for x in subset if x["winner"] == "alcaraz")
    else:
        sw_then = aw_then = "?"

    body = f"""<div class="breadcrumb">
  <a href="/">Home</a> › <a href="/matches/">All H2H Matches</a> › {m['event']} {m['year']}
</div>

<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px">
  {winner_badge(m['winner'])}
  {surface_badge(m['surface'])}
  <span class="badge surf">{event_label}</span>
  {'<span class="badge" style="background:rgba(245,200,66,.15);color:var(--gold)">⭐ Grand Slam Final</span>' if is_slam and m["round"]=="Final" else ''}
</div>

<h1>Sinner vs Alcaraz — {m['event']} {m['year']}<br>
  <span style="font-size:0.55em;font-weight:400;color:var(--text-dim)">{m['round']} · {m.get('location', m['event'])} · {SURFACE_INFO.get(m['surface'],{}).get('label', m['surface'].title())}</span>
</h1>

<div class="result-card">
  <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">{m['date']}</div>
  <div class="score-display">
    <span class="{'s' if m['winner']=='sinner' else 'a'}">{winner_name}</span>
    <span style="color:var(--text-dim);font-size:0.55em;margin:0 8px">def.</span>
    <span class="{'a' if m['winner']=='sinner' else 's'}">{loser_name}</span>
  </div>
  <div style="font-size:clamp(20px,4vw,32px);font-family:'Bebas Neue',Impact,sans-serif;letter-spacing:.04em;color:var(--text);margin:8px 0">{m['score']}</div>
  <div class="match-meta-row">
    <span>🏆 {m['event']}</span>
    {f'<span>⏱ {m["duration"]}</span>' if m.get("duration") else ''}
    <span>📊 H2H at time: Sinner {sw_then}–Alcaraz {aw_then}</span>
  </div>
</div>

{('<div class="note-box">💬 ' + note + '</div>') if note else ''}

{set_score_table(m)}

<div class="stat-grid" style="max-width:480px;margin-top:24px">
  <div class="stat-box">
    <div class="lbl">Sinner Ranking</div>
    <div class="val" style="color:var(--sinner)">#{m.get('sinner_rank','—')}</div>
    <div class="lbl">at time of match</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz Ranking</div>
    <div class="val" style="color:var(--alcaraz)">#{m.get('alcaraz_rank','—')}</div>
    <div class="lbl">at time of match</div>
  </div>
</div>

<a class="cta" href="/">📊 Full H2H Stats, Live Rankings & Career Data → sincaraz.app</a>

{related_matches(m['slug'], all_matches)}

<h2>About the Sinner–Alcaraz Rivalry</h2>
<p style="color:var(--text-dim);font-size:14px;line-height:1.8;margin-bottom:16px">
  Jannik Sinner and Carlos Alcaraz are the defining tennis rivalry of the 2020s —
  two world No. 1s born just 21 months apart, with {len(all_matches)} meetings across
  hard courts, clay and grass. This {m['event']} {m['year']} {m['round']} is one chapter in that story.
</p>
<p style="color:var(--text-dim);font-size:14px;line-height:1.8">
  For the complete head-to-head record, live career stats, serve & return ratings, surface splits,
  Grand Slam breakdown and the Clutch Score™ comparison, visit
  <a href="/">sincaraz.app</a> — updated daily from official ATP data.
</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:20px">
  <a href="/surface/{m['surface']}/" style="padding:10px 18px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px">{SURFACE_INFO.get(m['surface'],{}).get('emoji','')} All {SURFACE_INFO.get(m['surface'],{}).get('label','') } H2H matches</a>
  <a href="/matches/" style="padding:10px 18px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px">📋 Full H2H match list</a>
</div>
"""
    return html_page(title, description, canonical, body, match_schema(m))


# ─── Matches index page ───────────────────────────────────────────────────────

def generate_matches_index(all_matches):
    rows = ""
    for m in all_matches:
        w_cls = "s" if m["winner"] == "sinner" else "a"
        rows += f"""<tr class="win-{m['winner'][0]}">
  <td><a href="/matches/{m['slug']}/">{m['event']} {m['year']} {m['round']}</a></td>
  <td>{m['date']}</td>
  <td>{surface_badge(m['surface'])}</td>
  <td><span class="badge {w_cls}">{'Sinner' if m['winner']=='sinner' else 'Alcaraz'} wins</span></td>
  <td style="font-family:monospace">{m['score']}</td>
  <td style="color:var(--text-dim)">{m.get('duration','')}</td>
</tr>"""

    sw = sum(1 for m in all_matches if m["winner"] == "sinner")
    aw = sum(1 for m in all_matches if m["winner"] == "alcaraz")
    leader = "Alcaraz" if aw > sw else "Sinner"
    leader_score = f"{max(aw,sw)}–{min(aw,sw)}"

    title = f"Sinner vs Alcaraz: All {len(all_matches)} H2H Matches, Scores & Results | Sincaraz"
    desc  = (f"{leader} leads the H2H {leader_score} across {len(all_matches)} ATP Tour meetings. "
             f"Full match-by-match results, scores, surfaces and match reports.")
    canonical = f"{BASE_URL}/matches/"

    body = f"""<h1>Sinner vs Alcaraz: All H2H Matches</h1>
<p style="color:var(--text-dim);margin-bottom:32px">
  {leader} leads <strong style="color:var(--{'alcaraz' if leader=='Alcaraz' else 'sinner'})">{leader_score}</strong>
  across <strong>{len(all_matches)}</strong> ATP Tour meetings.
  Click any match for the full report.
</p>
<table class="match-table">
<thead><tr><th>Match</th><th>Date</th><th>Surface</th><th>Result</th><th>Score</th><th>Duration</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<a class="cta" href="/">📊 Live Stats & Full Rivalry Analysis → sincaraz.app</a>"""

    return html_page(title, desc, canonical, body)


# ─── Surface pages ────────────────────────────────────────────────────────────

def generate_surface_page(surface, all_matches):
    info = SURFACE_INFO[surface]
    surf_matches = [m for m in all_matches if m["surface"] == surface]
    sw = sum(1 for m in surf_matches if m["winner"] == "sinner")
    aw = sum(1 for m in surf_matches if m["winner"] == "alcaraz")
    leader = "Alcaraz" if aw > sw else "Sinner"
    leader_cls = "alcaraz" if aw > sw else "sinner"
    leader_score = f"{max(aw,sw)}–{min(aw,sw)}"

    title = (f"Sinner vs Alcaraz on {info['label']}: H2H Record, Matches & Stats | Sincaraz")
    desc  = (f"{leader} leads the {info['label'].lower()} H2H {leader_score} across "
             f"{len(surf_matches)} meetings. All match results, scores and stats.")
    canonical = f"{BASE_URL}/surface/{surface}/"

    rows = ""
    for m in surf_matches:
        w_cls = "s" if m["winner"] == "sinner" else "a"
        rows += f"""<tr class="win-{m['winner'][0]}">
  <td><a href="/matches/{m['slug']}/">{m['event']} {m['year']}</a></td>
  <td>{m['round']}</td>
  <td><span class="badge {w_cls}">{'Sinner' if m['winner']=='sinner' else 'Alcaraz'} wins</span></td>
  <td style="font-family:monospace">{m['score']}</td>
  <td style="color:var(--text-dim)">{m.get('duration','')}</td>
</tr>"""

    body = f"""<div class="breadcrumb">
  <a href="/">Home</a> › Surface H2H › {info['label']}
</div>

<h1>Sinner vs Alcaraz on {info['label']}<br>
  <span style="font-size:0.55em;color:var(--text-dim)">H2H Record, All Matches & Stats</span>
</h1>

<div class="stat-grid" style="max-width:500px">
  <div class="stat-box">
    <div class="lbl">Sinner {info['label']} Wins</div>
    <div class="val" style="color:var(--sinner)">{sw}</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz {info['label']} Wins</div>
    <div class="val" style="color:var(--alcaraz)">{aw}</div>
  </div>
</div>

<p style="color:var(--text-dim);margin:16px 0 32px;font-size:15px">
  <strong style="color:var(--{leader_cls})">{leader}</strong> leads the {info['label'].lower()}
  H2H <strong>{leader_score}</strong> across {len(surf_matches)} matches.
</p>

<h2>All {info['label']} Meetings</h2>
<table class="match-table">
<thead><tr><th>Tournament</th><th>Round</th><th>Result</th><th>Score</th><th>Duration</th></tr></thead>
<tbody>{rows}</tbody>
</table>

<a class="cta" href="/">📊 Full Rivalry Stats → sincaraz.app</a>

<h2>Other Surfaces</h2>
<div style="display:flex;gap:12px;flex-wrap:wrap">
  {''.join(f'<a href="/surface/{s}/" style="padding:10px 20px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px">{SURFACE_INFO[s]["emoji"]} {SURFACE_INFO[s]["label"]} H2H</a>' for s in SURFACE_INFO if s != surface)}
</div>
"""

    return html_page(title, desc, canonical, body)


# ─── Topic / Comparison pages (long-tail SEO) ────────────────────────────

def _load_stats():
    """Load scraped_stats.json and return the dict, or None on failure."""
    try:
        with open("scraped_stats.json") as f:
            return json.load(f)
    except Exception:
        return None


def _pct(w, l):
    """Win percentage from W and L counts."""
    t = w + l
    return round(100 * w / t, 1) if t else 0


def _parse_wl(wl_str):
    """Parse '70-24' → (70, 24)."""
    m = re.match(r'(\d+)\D+(\d+)', str(wl_str))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _faq_schema(pairs):
    """Return FAQPage schema for list of (question, answer) tuples."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }


def _comparison_row(label, sinner_val, alcaraz_val, highlight_higher=True):
    """Single stat comparison row with color emphasis on the leader."""
    s_style = a_style = ""
    try:
        sv = float(str(sinner_val).replace('%','').replace(',',''))
        av = float(str(alcaraz_val).replace('%','').replace(',',''))
        if highlight_higher:
            if sv > av: s_style = "color:var(--sinner);font-weight:700"
            elif av > sv: a_style = "color:var(--alcaraz);font-weight:700"
        else:
            if sv < av: s_style = "color:var(--sinner);font-weight:700"
            elif av < sv: a_style = "color:var(--alcaraz);font-weight:700"
    except (ValueError, TypeError):
        pass
    return f"""<tr>
  <td style="color:var(--text-dim)">{label}</td>
  <td style="text-align:center;{s_style}">{sinner_val}</td>
  <td style="text-align:center;{a_style}">{alcaraz_val}</td>
</tr>"""


def _stat_table(rows_html):
    return f"""<table class="match-table">
<thead><tr><th>Stat</th><th style="text-align:center;color:var(--sinner)">Sinner</th><th style="text-align:center;color:var(--alcaraz)">Alcaraz</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>"""


def _internal_links(exclude_slug=""):
    """Standard internal linking block for topic pages."""
    links = [
        ("/", "Full H2H Stats Dashboard"),
        ("/matches/", "All H2H Match Results"),
        ("/sinner-vs-alcaraz-head-to-head/", "Head to Head Record"),
        ("/who-is-better-sinner-or-alcaraz/", "Who Is Better?"),
        ("/sinner-vs-alcaraz-clay-stats/", "Clay Stats"),
        ("/sinner-vs-alcaraz-hard-court-stats/", "Hard Court Stats"),
        ("/sinner-vs-alcaraz-grass-record/", "Grass Record"),
        ("/sinner-vs-alcaraz-2026-stats/", "2026 Season Stats"),
        ("/sinner-vs-alcaraz-last-5-matches/", "Last 5 Matches"),
        ("/sinner-vs-alcaraz-serve-stats/", "Serve Stats"),
        ("/sinner-vs-alcaraz-return-stats/", "Return Stats"),
        ("/sinner-vs-alcaraz-grand-slams/", "Grand Slam Record"),
        ("/sinner-vs-alcaraz-break-points/", "Break Point Stats"),
        ("/sinner-vs-alcaraz-tiebreak-record/", "Tiebreak Record"),
        ("/sinner-vs-alcaraz-ranking-history/", "Ranking History"),
        ("/sinner-vs-alcaraz-career-titles/", "Career Titles"),
        ("/sinner-vs-alcaraz-five-set-record/", "Five-Set Record"),
        ("/sinner-vs-alcaraz-clutch-stats/", "Clutch & Pressure Stats"),
        ("/sinner-vs-alcaraz-prize-money/", "Prize Money"),
    ]
    items = "".join(
        f'<a href="{url}" style="padding:8px 16px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px;display:inline-block">{label}</a>'
        for url, label in links if exclude_slug not in url
    )
    return f'<h2>Explore More Stats</h2><div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px">{items}</div>'


def _faq_html(pairs):
    """Render FAQ section as visible HTML + schema."""
    items = ""
    for q, a in pairs:
        items += f"""<details style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px">
  <summary style="cursor:pointer;font-weight:700;font-size:15px">{q}</summary>
  <p style="margin-top:12px;color:var(--text-dim);font-size:14px;line-height:1.7">{a}</p>
</details>"""
    return f"<h2>Frequently Asked Questions</h2>{items}"


# --- Individual topic page generators ---

def _page_serve_comparison(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sc, ac = s["career"], a["career"]

    rows = "".join([
        _comparison_row("Aces (career)", f'{sc["aces"]:,}', f'{ac["aces"]:,}'),
        _comparison_row("Avg Aces / Match", s["computed"]["avg_aces_match"], a["computed"]["avg_aces_match"]),
        _comparison_row("Double Faults", f'{sc["double_faults"]:,}', f'{ac["double_faults"]:,}', False),
        _comparison_row("Avg DFs / Match", s["computed"]["avg_df_match"], a["computed"]["avg_df_match"], False),
        _comparison_row("1st Serve %", f'{sc["first_serve_pct"]}%', f'{ac["first_serve_pct"]}%'),
        _comparison_row("1st Serve Won %", f'{sc["first_serve_won_pct"]}%', f'{ac["first_serve_won_pct"]}%'),
        _comparison_row("2nd Serve Won %", f'{sc["second_serve_won_pct"]}%', f'{ac["second_serve_won_pct"]}%'),
        _comparison_row("Service Games Won %", f'{sc["service_games_won_pct"]}%', f'{ac["service_games_won_pct"]}%'),
        _comparison_row("Service Points Won %", f'{sc["service_points_won_pct"]}%', f'{ac["service_points_won_pct"]}%'),
        _comparison_row("Break Points Saved %", f'{sc["bp_saved_pct"]}%', f'{ac["bp_saved_pct"]}%'),
    ])

    s_rating = s["vision_wl"].get("serve_rating", "N/A")

    faqs = [
        ("Who has the better serve, Sinner or Alcaraz?",
         f"Sinner has the stronger serve statistically — he hits {sc['aces']:,} career aces at {s['computed']['avg_aces_match']} per match vs Alcaraz's {ac['aces']:,} ({a['computed']['avg_aces_match']}/match). Sinner also wins {sc['first_serve_won_pct']}% of first serve points compared to {ac['first_serve_won_pct']}% for Alcaraz and holds serve {sc['service_games_won_pct']}% vs {ac['service_games_won_pct']}%."),
        ("How many aces do Sinner and Alcaraz average per match?",
         f"Sinner averages {s['computed']['avg_aces_match']} aces per match while Alcaraz averages {a['computed']['avg_aces_match']}. The gap comes from Sinner's height advantage (6'2\" vs 6'1\") and flatter ball-striking pattern, giving him a more dominant first serve."),
        ("Who saves more break points, Sinner or Alcaraz?",
         f"Sinner saves {sc['bp_saved_pct']}% of break points faced compared to Alcaraz's {ac['bp_saved_pct']}%. Sinner has faced {sc['bp_faced']:,} break points across his career vs {ac['bp_faced']:,} for Alcaraz."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Serve Stats</div>

<h1>Sinner vs Alcaraz Serve Stats (2026 Comparison)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Sinner's serve is the more potent weapon in this rivalry. He leads in aces ({sc['aces']:,} to {ac['aces']:,}),
first-serve points won ({sc['first_serve_won_pct']}% to {ac['first_serve_won_pct']}%), and service games held
({sc['service_games_won_pct']}% to {ac['service_games_won_pct']}%). Alcaraz compensates with a higher first-serve
percentage ({ac['first_serve_pct']}% to {sc['first_serve_pct']}%), finding more first serves but winning fewer
points behind them.
</p>

<h2>Career Serve Statistics</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. The ace gap is real but overstated.</strong> Sinner averages {s['computed']['avg_aces_match']} aces per match
to Alcaraz's {a['computed']['avg_aces_match']}, but the bigger differentiator is the 4% gap in first-serve points won.
Sinner's flatter serve generates weaker returns, setting up shorter rallies that suit his baseline game.
</div>
<div class="note-box">
<strong>2. Alcaraz's approach is accuracy-first.</strong> Hitting {ac['first_serve_pct']}% of first serves in means
fewer second serves exposed to attack. Alcaraz's {a['computed']['avg_df_match']} double faults per match vs Sinner's
{s['computed']['avg_df_match']} shows the tradeoff — Sinner goes bigger but misses more.
</div>
<div class="note-box">
<strong>3. Sinner is the better escape artist.</strong> At {sc['bp_saved_pct']}% break points saved vs {ac['bp_saved_pct']}%,
Sinner is more reliable under pressure on serve — a critical edge in tight matches where every service game matters.
</div>

<a class="cta" href="/">📊 See All Live H2H Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("serve-comparison")}
"""
    return {
        "slug": "sinner-vs-alcaraz-serve-stats",
        "title": "Sinner vs Alcaraz Serve Stats 2026: Aces, Win % & Data",
        "description": f"Sinner leads in aces ({sc['aces']:,} vs {ac['aces']:,}) and 1st serve won ({sc['first_serve_won_pct']}% vs {ac['first_serve_won_pct']}%). Full serve comparison with 2026 data.",
        "body": body,
        "faqs": faqs,
    }


def _page_return_stats(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sc, ac = s["career"], a["career"]

    rows = "".join([
        _comparison_row("1st Return Won %", f'{sc["first_return_won_pct"]}%', f'{ac["first_return_won_pct"]}%'),
        _comparison_row("2nd Return Won %", f'{sc["second_return_won_pct"]}%', f'{ac["second_return_won_pct"]}%'),
        _comparison_row("Return Games Won %", f'{sc["return_games_won_pct"]}%', f'{ac["return_games_won_pct"]}%'),
        _comparison_row("Return Points Won %", f'{sc["return_points_won_pct"]}%', f'{ac["return_points_won_pct"]}%'),
        _comparison_row("Break Points Converted %", f'{sc["bp_converted_pct"]}%', f'{ac["bp_converted_pct"]}%'),
        _comparison_row("Break Point Opportunities", f'{sc["bp_opportunities"]:,}', f'{ac["bp_opportunities"]:,}'),
        _comparison_row("Total Points Won %", f'{sc["total_points_won_pct"]}%', f'{ac["total_points_won_pct"]}%'),
    ])

    faqs = [
        ("Who is the better returner, Sinner or Alcaraz?",
         f"Alcaraz has the statistical edge on return. He wins {ac['first_return_won_pct']}% of first-return points vs {sc['first_return_won_pct']}% for Sinner, and breaks serve {ac['return_games_won_pct']}% of the time compared to {sc['return_games_won_pct']}%. Alcaraz's return prowess is one of his most distinctive weapons."),
        ("How do Sinner and Alcaraz compare at converting break points?",
         f"They are nearly identical: Sinner converts {sc['bp_converted_pct']}% vs Alcaraz's {ac['bp_converted_pct']}%. The real difference is opportunity creation — Sinner generates {sc['bp_opportunities']:,} break point chances career-wide vs {ac['bp_opportunities']:,} for Alcaraz."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Return Stats</div>

<h1>Sinner vs Alcaraz Return Stats (2026 Data)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Alcaraz owns the return game in this rivalry. He leads Sinner in first-return points won ({ac['first_return_won_pct']}%
to {sc['first_return_won_pct']}%), return games broken ({ac['return_games_won_pct']}% to {sc['return_games_won_pct']}%),
and total return points ({ac['return_points_won_pct']}% to {sc['return_points_won_pct']}%). Alcaraz's ability to
neutralize big servers and create break opportunities is what makes him dangerous on any surface.
</p>

<h2>Career Return Statistics</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Alcaraz is the elite return threat.</strong> Breaking serve {ac['return_games_won_pct']}% of the time puts him
among the best returners on Tour. His ability to redirect pace and find angles off the return neutralizes
first-serve advantages that most players can't counter.
</div>
<div class="note-box">
<strong>2. The break point conversion paradox.</strong> Despite Sinner ({sc['bp_converted_pct']}%) and Alcaraz
({ac['bp_converted_pct']}%) converting at nearly identical rates, Alcaraz creates more opportunities — {ac['bp_opportunities']:,}
career break point chances vs {sc['bp_opportunities']:,} for Sinner, per return game played.
</div>
<div class="note-box">
<strong>3. Second-serve return is the equalizer.</strong> Both win {sc['second_return_won_pct']}%/{ac['second_return_won_pct']}% on second-serve returns.
The difference emerges on first-serve returns, where Alcaraz's reflexes and positioning give him a {ac['first_return_won_pct'] - sc['first_return_won_pct']}% advantage.
</div>

<a class="cta" href="/">📊 See All Live H2H Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("return-stats")}
"""
    return {
        "slug": "sinner-vs-alcaraz-return-stats",
        "title": "Sinner vs Alcaraz Return Stats 2026: Break % & Analysis",
        "description": f"Alcaraz breaks serve {ac['return_games_won_pct']}% vs Sinner's {sc['return_games_won_pct']}%. Full return game comparison — 1st/2nd return %, break points, and return winners.",
        "body": body,
        "faqs": faqs,
    }


def _page_grand_slam_record(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]
    sv, av = s["vision_wl"], a["vision_wl"]
    s_gs_wl = _parse_wl(sv.get("grand_slams_wl", "0-0"))
    a_gs_wl = _parse_wl(av.get("grand_slams_wl", "0-0"))

    rows = "".join([
        _comparison_row("Grand Slam Titles", sco["gs_total"], aco["gs_total"]),
        _comparison_row("Australian Open", sco["gs_ao"], aco["gs_ao"]),
        _comparison_row("Roland Garros", sco["gs_rg"], aco["gs_rg"]),
        _comparison_row("Wimbledon", sco["gs_wimbledon"], aco["gs_wimbledon"]),
        _comparison_row("US Open", sco["gs_uso"], aco["gs_uso"]),
        _comparison_row("Grand Slam W/L", sv.get("grand_slams_wl", "—"), av.get("grand_slams_wl", "—")),
        _comparison_row("GS Win %", f'{_pct(*s_gs_wl)}%', f'{_pct(*a_gs_wl)}%'),
        _comparison_row("GS Finals Reached", "—", "—"),
    ])

    faqs = [
        ("How many Grand Slams have Sinner and Alcaraz won?",
         f"As of April 2026, Alcaraz has won {aco['gs_total']} Grand Slam titles (AO {aco['gs_ao']}, RG {aco['gs_rg']}, Wimbledon {aco['gs_wimbledon']}, USO {aco['gs_uso']}) while Sinner has {sco['gs_total']} (AO {sco['gs_ao']}, RG {sco['gs_rg']}, Wimbledon {sco['gs_wimbledon']}, USO {sco['gs_uso']}). Alcaraz achieved the Career Grand Slam earlier, while Sinner's Australian Open dominance anchors his total."),
        ("Who has the better Grand Slam win percentage?",
         f"Alcaraz wins {_pct(*a_gs_wl)}% of Grand Slam matches ({av.get('grand_slams_wl','—')}) vs Sinner's {_pct(*s_gs_wl)}% ({sv.get('grand_slams_wl','—')}). Alcaraz's remarkably low loss count at Slams reflects his ability to peak for the biggest events."),
        ("Have Sinner and Alcaraz played in a Grand Slam final?",
         "Yes — the 2025 Roland Garros final (Alcaraz won in 5 sets, 5h29m, the longest Grand Slam final ever), the 2025 Wimbledon final (Sinner won in 4 sets), and the 2025 US Open final (Alcaraz won in 4 sets). Their Slam final meetings have already produced historic tennis."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Grand Slams</div>

<h1>Sinner vs Alcaraz Grand Slams: Titles & Win Rate (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
At age 22, Alcaraz already holds {aco['gs_total']} Grand Slam titles across all four surfaces — a Career Grand Slam
he completed faster than nearly anyone in history. Sinner has {sco['gs_total']} Slams at 24, led by his {sco['gs_ao']}
Australian Open titles. Together they've combined for {sco['gs_total'] + aco['gs_total']} Major titles before either
has turned 25.
</p>

<h2>Grand Slam Titles Breakdown</h2>
{_stat_table(rows)}

<div class="stat-grid" style="max-width:480px;margin-top:24px">
  <div class="stat-box">
    <div class="lbl">Sinner GS Titles</div>
    <div class="val" style="color:var(--sinner)">{sco['gs_total']}</div>
    <div class="lbl">AO {sco['gs_ao']} · RG {sco['gs_rg']} · W {sco['gs_wimbledon']} · USO {sco['gs_uso']}</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz GS Titles</div>
    <div class="val" style="color:var(--alcaraz)">{aco['gs_total']}</div>
    <div class="lbl">AO {aco['gs_ao']} · RG {aco['gs_rg']} · W {aco['gs_wimbledon']} · USO {aco['gs_uso']}</div>
  </div>
</div>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Alcaraz's surface versatility is historically rare.</strong> Winning at Roland Garros ({aco['gs_rg']}), Wimbledon ({aco['gs_wimbledon']}),
and the US Open ({aco['gs_uso']}) by age 22 puts him in territory occupied only by all-time greats.
His clay-to-grass adaptability in particular mirrors peak Nadal and Djokovic.
</div>
<div class="note-box">
<strong>2. Sinner dominates in Melbourne.</strong> With {sco['gs_ao']} Australian Open titles, Sinner has made the hard courts
of Melbourne Park his fortress. His late-January form and ability to peak after a full pre-season are consistent advantages.
</div>
<div class="note-box">
<strong>3. The GS win-rate gap matters most.</strong> Alcaraz's {_pct(*a_gs_wl)}% Grand Slam win rate vs Sinner's {_pct(*s_gs_wl)}%
shows fewer early exits. At the Majors, Alcaraz is simply harder to beat round-for-round.
</div>

<a class="cta" href="/">📊 Full Live Stats & Rivalry Dashboard → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("grand-slam-record")}
"""
    return {
        "slug": "sinner-vs-alcaraz-grand-slams",
        "title": f"Sinner vs Alcaraz Grand Slams: {sco['gs_total']} vs {aco['gs_total']} Titles",
        "description": f"Alcaraz leads {aco['gs_total']}–{sco['gs_total']} in Grand Slams with a {_pct(*a_gs_wl)}% win rate vs {_pct(*s_gs_wl)}%. AO, RG, Wimbledon, USO breakdown and Slam final history.",
        "body": body,
        "faqs": faqs,
    }


def _page_break_points(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sc, ac = s["career"], a["career"]

    rows = "".join([
        _comparison_row("Break Points Saved %", f'{sc["bp_saved_pct"]}%', f'{ac["bp_saved_pct"]}%'),
        _comparison_row("Break Points Faced", f'{sc["bp_faced"]:,}', f'{ac["bp_faced"]:,}'),
        _comparison_row("Break Points Converted %", f'{sc["bp_converted_pct"]}%', f'{ac["bp_converted_pct"]}%'),
        _comparison_row("Break Point Opportunities", f'{sc["bp_opportunities"]:,}', f'{ac["bp_opportunities"]:,}'),
        _comparison_row("Return Games Won %", f'{sc["return_games_won_pct"]}%', f'{ac["return_games_won_pct"]}%'),
        _comparison_row("Service Games Won %", f'{sc["service_games_won_pct"]}%', f'{ac["service_games_won_pct"]}%'),
    ])

    faqs = [
        ("Who saves more break points, Sinner or Alcaraz?",
         f"Sinner saves {sc['bp_saved_pct']}% of break points faced compared to Alcaraz's {ac['bp_saved_pct']}%. Over his career Sinner has faced {sc['bp_faced']:,} break points vs {ac['bp_faced']:,} for Alcaraz, meaning Sinner also faces fewer break points per service game."),
        ("Who converts more break points?",
         f"Sinner converts {sc['bp_converted_pct']}% of break point opportunities vs {ac['bp_converted_pct']}% for Alcaraz. The difference is marginal, but in a five-set match even 1% matters. Sinner has had {sc['bp_opportunities']:,} total chances vs {ac['bp_opportunities']:,} for Alcaraz."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Break Points</div>

<h1>Sinner vs Alcaraz Break Points: Saved %, Converted (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Break points separate champions from contenders, and both Sinner and Alcaraz are elite on both sides of
the equation. Sinner saves {sc['bp_saved_pct']}% of break points faced — among the best on Tour — while Alcaraz
breaks serve {ac['return_games_won_pct']}% of the time, creating relentless pressure on opponents' service games.
</p>

<h2>Break Point Statistics</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Sinner is the tougher hold.</strong> At {sc['service_games_won_pct']}% service games won and {sc['bp_saved_pct']}%
break points saved, Sinner's serve is a fortress. Opponents need 2-3 break chances per set just to get one break,
making him especially dangerous in tiebreak-heavy matches.
</div>
<div class="note-box">
<strong>2. Alcaraz applies more return pressure.</strong> His {ac['return_games_won_pct']}% return games won rate is elite — he doesn't
need as many break chances because he generates them more consistently. Against weaker servers, Alcaraz often
breaks multiple times per set.
</div>
<div class="note-box">
<strong>3. Conversion rates are a wash.</strong> At {sc['bp_converted_pct']}% vs {ac['bp_converted_pct']}%, both players
execute at nearly the same rate when they reach 15-40 or deuce. The rivalry is decided by who creates more
opportunities and who defends them better — not by clutch conversion.
</div>

<a class="cta" href="/">📊 Full Break Point & Serve Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("break-points")}
"""
    return {
        "slug": "sinner-vs-alcaraz-break-points",
        "title": f"Sinner vs Alcaraz Break Points: {sc['bp_saved_pct']}% vs {ac['bp_saved_pct']}% Saved",
        "description": f"Sinner saves {sc['bp_saved_pct']}% of break points vs Alcaraz's {ac['bp_saved_pct']}%. Conversion rates, opportunities created, and service game dominance compared.",
        "body": body,
        "faqs": faqs,
    }


def _page_tiebreak_record(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    s_tb = _parse_wl(sv.get("tiebreak_wl", "0-0"))
    a_tb = _parse_wl(av.get("tiebreak_wl", "0-0"))

    rows = "".join([
        _comparison_row("Tiebreak Record", sv.get("tiebreak_wl", "—"), av.get("tiebreak_wl", "—")),
        _comparison_row("Tiebreak Win %", f'{s["computed"]["tiebreaks_won_pct"]}%', f'{a["computed"]["tiebreaks_won_pct"]}%'),
        _comparison_row("Tiebreaks Played", s_tb[0]+s_tb[1], a_tb[0]+a_tb[1]),
    ])

    faqs = [
        ("Who wins more tiebreaks, Sinner or Alcaraz?",
         f"Sinner has the better tiebreak record at {s['computed']['tiebreaks_won_pct']}% ({sv.get('tiebreak_wl','—')}) compared to Alcaraz's {a['computed']['tiebreaks_won_pct']}% ({av.get('tiebreak_wl','—')}). Sinner's bigger serve and point-ending ability in short rallies give him an edge when every point matters."),
        ("How many tiebreaks have Sinner and Alcaraz played against each other?",
         "Their head-to-head matches frequently go to tiebreaks — key examples include the 2025 ATP Finals final (7-6 in the first set), the 2022 US Open quarterfinal, and the 2025 Roland Garros final where the 4th and 5th sets both went to tiebreaks."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Tiebreaks</div>

<h1>Sinner vs Alcaraz Tiebreak Record: Who Wins the Big Points?</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
In the tightest moments of a match, Sinner has the edge. He wins {s['computed']['tiebreaks_won_pct']}% of career tiebreaks
({sv.get('tiebreak_wl','—')}) compared to Alcaraz's {a['computed']['tiebreaks_won_pct']}% ({av.get('tiebreak_wl','—')}).
With {s_tb[0]+s_tb[1]} tiebreaks played, Sinner's ability to execute under point-by-point pressure
has been one of the defining features of his game.
</p>

<h2>Tiebreak Comparison</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Sinner's serve is the tiebreak weapon.</strong> His {s['career']['first_serve_won_pct']}% first-serve points won
means he's more likely to hold serve points in tiebreaks, where one mini-break can decide the set.
The flatter, harder delivery forces weak returns that Sinner can put away.
</div>
<div class="note-box">
<strong>2. Alcaraz's tiebreak percentage is still elite.</strong> At {a['computed']['tiebreaks_won_pct']}%, he's above
the ATP Tour average. The gap between them (about 3 percentage points) amounts to roughly 1 extra tiebreak
lost per 30 played — small but meaningful across a season.
</div>
<div class="note-box">
<strong>3. Tiebreaks define their rivalry.</strong> Their head-to-head matches frequently reach tiebreaks — from the
2025 ATP Finals to the 2022 US Open. In these pressure-cooker moments, the mental edge matters as much as the serve.
</div>

<a class="cta" href="/">📊 Full H2H Stats & Match Data → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("tiebreak-record")}
"""
    return {
        "slug": "sinner-vs-alcaraz-tiebreak-record",
        "title": f"Sinner vs Alcaraz Tiebreaks: {s['computed']['tiebreaks_won_pct']}% vs {a['computed']['tiebreaks_won_pct']}%",
        "description": f"Sinner: {sv.get('tiebreak_wl','—')} tiebreaks ({s['computed']['tiebreaks_won_pct']}%). Alcaraz: {av.get('tiebreak_wl','—')} ({a['computed']['tiebreaks_won_pct']}%). Who wins more big points? Full analysis.",
        "body": body,
        "faqs": faqs,
    }


def _page_ranking_history(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]

    s_yer = sco.get("year_end_rankings") or {}
    a_yer = aco.get("year_end_rankings") or {}

    year_rows = ""
    years = sorted(set(list(s_yer.keys()) + list(a_yer.keys())))
    for yr in years:
        sv = s_yer.get(yr, "—")
        av = a_yer.get(yr, "—")
        year_rows += _comparison_row(yr, f'#{sv}' if sv != "—" else "—", f'#{av}' if av != "—" else "—", False)

    summary_rows = "".join([
        _comparison_row("Current Ranking", f'#{s["ranking"]}', f'#{a["ranking"]}', False),
        _comparison_row("Weeks at No. 1", sco["weeks_at_no1"], aco["weeks_at_no1"]),
        _comparison_row("Days at No. 1", sco["days_at_no1"], aco["days_at_no1"]),
        _comparison_row("Year-End No. 1 Finishes", sum(1 for v in s_yer.values() if v == 1), sum(1 for v in a_yer.values() if v == 1)),
    ])

    faqs = [
        ("Who has been No. 1 longer, Sinner or Alcaraz?",
         f"Sinner has held the No. 1 ranking for {sco['weeks_at_no1']} weeks ({sco['days_at_no1']} days) compared to Alcaraz's {aco['weeks_at_no1']} weeks ({aco['days_at_no1']} days). The No. 1 ranking has changed hands between them multiple times since 2024."),
        ("What are Sinner and Alcaraz's year-end rankings?",
         f"Sinner's year-end rankings have been: {', '.join(f'{yr}: #{v}' for yr, v in sorted(s_yer.items()))}. Alcaraz's rankings data is tracked from his breakthrough year. Both have improved dramatically from outside the top 30 to trading the No. 1 spot."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Rankings</div>

<h1>Sinner vs Alcaraz Ranking History: The Race for No. 1</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
The race for No. 1 defines this rivalry. Sinner has spent {sco['weeks_at_no1']} weeks at the top
vs {aco['weeks_at_no1']} for Alcaraz — a margin of just {abs(sco['weeks_at_no1']-aco['weeks_at_no1'])} weeks.
Currently, Sinner holds the No. {s['ranking']} ranking while Alcaraz is No. {a['ranking']}.
Their parallel rises from outside the top 30 to alternating at World No. 1 has no modern equivalent.
</p>

<h2>Ranking Summary</h2>
{_stat_table(summary_rows)}

<h2>Year-End Rankings Comparison</h2>
{_stat_table(year_rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. The closest No. 1 race in ATP history.</strong> Just {abs(sco['weeks_at_no1']-aco['weeks_at_no1'])} weeks separate them
in total time at No. 1. Unlike Federer-Nadal where Federer's early dominance built a huge lead, Sinner and
Alcaraz have traded the ranking back and forth since 2024.
</div>
<div class="note-box">
<strong>2. Alcaraz's rise was faster.</strong> Alcaraz first reached No. 1 at 19 years old after the 2022 US Open.
Sinner took the spot in January 2024 at age 22. But Sinner's consistency since then — spending the majority of
2024-2025 at No. 1 — shows sustained excellence rather than early peaks.
</div>
<div class="note-box">
<strong>3. Year-end No. 1 is the prestige metric.</strong> Finishing the season at the top requires 11 months of
consistent performance, not just a single tournament spike. It's the stat that matters most for legacy discussions.
</div>

<a class="cta" href="/">📊 Live Rankings & Full Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("ranking-history")}
"""
    return {
        "slug": "sinner-vs-alcaraz-ranking-history",
        "title": f"Sinner vs Alcaraz Rankings: {sco['weeks_at_no1']} vs {aco['weeks_at_no1']} Weeks at #1",
        "description": f"Sinner: {sco['weeks_at_no1']} weeks at No. 1. Alcaraz: {aco['weeks_at_no1']}. Year-end rankings since 2019, No. 1 race timeline, and career trajectory compared.",
        "body": body,
        "faqs": faqs,
    }


def _page_career_titles(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]
    sv, av = s["vision_wl"], a["vision_wl"]

    rows = "".join([
        _comparison_row("Career Titles", s["career_titles"], a["career_titles"]),
        _comparison_row("Grand Slam Titles", sco["gs_total"], aco["gs_total"]),
        _comparison_row("Masters 1000 Titles", sco["masters_titles"], aco["masters_titles"]),
        _comparison_row("Big Titles (GS + Masters)", sco["big_titles"], aco["big_titles"]),
        _comparison_row("Finals Record", sv.get("finals_wl", "—"), av.get("finals_wl", "—")),
        _comparison_row("Career Win %", f'{s["career_win_pct"]}%', f'{a["career_win_pct"]}%'),
        _comparison_row("2026 YTD Titles", s["ytd_titles"], a["ytd_titles"]),
    ])

    faqs = [
        ("How many titles have Sinner and Alcaraz won?",
         f"Sinner has won {s['career_titles']} career titles and Alcaraz has {a['career_titles']}. In big titles (Grand Slams + Masters 1000), Alcaraz leads {aco['big_titles']} to {sco['big_titles']}. Both have {sco['masters_titles']} Masters titles each."),
        ("Who has the higher career win percentage?",
         f"Alcaraz has a career win rate of {a['career_win_pct']}% ({a['career_wl']}) vs Sinner's {s['career_win_pct']}% ({s['career_wl']}). The {a['career_win_pct'] - s['career_win_pct']:.1f}% gap reflects Alcaraz's fewer early losses as he burst onto the Tour."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Titles</div>

<h1>Sinner vs Alcaraz Career Titles: Who Has Won More? (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Sinner leads the overall title count {s['career_titles']} to {a['career_titles']}, but Alcaraz holds
more of the titles that define a legacy. With {aco['gs_total']} Grand Slams to Sinner's {sco['gs_total']}
and {aco['big_titles']} big titles (GS + Masters) to {sco['big_titles']}, the quality of Alcaraz's
title haul edges ahead despite the raw number gap.
</p>

<h2>Titles Breakdown</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Quality vs quantity.</strong> Sinner's {s['career_titles']} titles include more 250/500 level events,
while Alcaraz's {a['career_titles']} lean heavier toward Slams and Masters. In the ATP's points hierarchy,
Alcaraz's trophy case carries more weight per title.
</div>
<div class="note-box">
<strong>2. Masters parity.</strong> Both hold exactly {sco['masters_titles']} Masters 1000 titles. This is the level
where they've been most evenly matched — neither has been able to dominate the other at the 1000-level consistently.
</div>
<div class="note-box">
<strong>3. Finals record tells the full story.</strong> Sinner's {sv.get('finals_wl','—')} finals record
vs Alcaraz's {av.get('finals_wl','—')} shows how often they reach and win championship matches. Both
are elite closers, converting the majority of their finals into titles.
</div>

<a class="cta" href="/">📊 Live Titles, Rankings & Full Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("career-titles")}
"""
    return {
        "slug": "sinner-vs-alcaraz-career-titles",
        "title": f"Sinner vs Alcaraz Titles: {s['career_titles']} vs {a['career_titles']} (2026)",
        "description": f"Sinner: {s['career_titles']} titles ({sco['gs_total']} Slams). Alcaraz: {a['career_titles']} titles ({aco['gs_total']} Slams). Masters parity at {sco['masters_titles']} each. Full breakdown.",
        "body": body,
        "faqs": faqs,
    }


def _page_five_set_record(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sco, aco = s["computed"], a["computed"]
    s_5s = _parse_wl(sv.get("fifth_set_wl", "0-0"))
    a_5s = _parse_wl(av.get("fifth_set_wl", "0-0"))
    s_ds = _parse_wl(sv.get("deciding_set_wl", "0-0"))
    a_ds = _parse_wl(av.get("deciding_set_wl", "0-0"))

    rows = "".join([
        _comparison_row("5th Set Record", sv.get("fifth_set_wl", "—"), av.get("fifth_set_wl", "—")),
        _comparison_row("5th Set Win %", f'{_pct(*s_5s)}%', f'{_pct(*a_5s)}%'),
        _comparison_row("Deciding Set Record (all)", sv.get("deciding_set_wl", "—"), av.get("deciding_set_wl", "—")),
        _comparison_row("Deciding Sets Won %", f'{sco["deciding_sets_won_pct"]}%', f'{aco["deciding_sets_won_pct"]}%'),
        _comparison_row("After Winning 1st Set", f'{sco["after_winning_first_set_pct"]}%', f'{aco["after_winning_first_set_pct"]}%'),
        _comparison_row("After Losing 1st Set", f'{sco["after_losing_first_set_pct"]}%', f'{aco["after_losing_first_set_pct"]}%'),
    ])

    faqs = [
        ("Who is better in five-set matches, Sinner or Alcaraz?",
         f"Alcaraz is dramatically better in five-set matches with a {av.get('fifth_set_wl','—')} record ({_pct(*a_5s)}% win rate) compared to Sinner's {sv.get('fifth_set_wl','—')} ({_pct(*s_5s)}%). Alcaraz's physical fitness and mental resilience in fifth sets have been one of his biggest advantages at Grand Slams."),
        ("Who is better after losing the first set?",
         f"Alcaraz recovers from losing the first set {aco['after_losing_first_set_pct']}% of the time vs {sco['after_losing_first_set_pct']}% for Sinner. Both are strong front-runners — Sinner wins {sco['after_winning_first_set_pct']}% after taking the first set vs {aco['after_winning_first_set_pct']}% for Alcaraz."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Five-Set Record</div>

<h1>Sinner vs Alcaraz Five-Set Record: Who Wins the Distance?</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
When a match goes the distance, Alcaraz has a massive edge. His {av.get('fifth_set_wl','—')} record in five-setters
({_pct(*a_5s)}%) is one of the most remarkable stats in modern tennis. Sinner's {sv.get('fifth_set_wl','—')} record
({_pct(*s_5s)}%) is his most notable weakness — and one that has cost him multiple Grand Slam opportunities.
</p>

<h2>Deciding Set Statistics</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Alcaraz's {av.get('fifth_set_wl','—')} fifth-set record is extraordinary.</strong> {_pct(*a_5s)}% in five-setters
means he essentially never loses when a Grand Slam match goes the full distance. His 2025 Roland Garros final win
over Sinner from 0-2 down epitomizes this ability — when others fatigue, Alcaraz elevates.
</div>
<div class="note-box">
<strong>2. Sinner's fifth-set struggles are real.</strong> At {sv.get('fifth_set_wl','—')}, Sinner has lost more
fifth sets than he's won. This isn't a fitness issue — it's about mental approach. In tight fifth sets, Sinner tends
to tighten up rather than swing freely, which plays into opponents' hands.
</div>
<div class="note-box">
<strong>3. Both are deadly front-runners.</strong> Sinner wins {sco['after_winning_first_set_pct']}% of matches after
taking the first set; Alcaraz wins {aco['after_winning_first_set_pct']}%. Once either player gets ahead, the match
is almost always over — which makes comebacks against them all the more remarkable.
</div>

<a class="cta" href="/">📊 Full Clutch & Pressure Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("five-set-record")}
"""
    return {
        "slug": "sinner-vs-alcaraz-five-set-record",
        "title": f"Sinner vs Alcaraz Five-Set Record: {sv.get('fifth_set_wl','—')} vs {av.get('fifth_set_wl','—')}",
        "description": f"Alcaraz: {av.get('fifth_set_wl','—')} in 5-setters ({_pct(*a_5s)}%). Sinner: {sv.get('fifth_set_wl','—')} ({_pct(*s_5s)}%). Deciding sets, comeback rates, and who wins when it goes the distance.",
        "body": body,
        "faqs": faqs,
    }


def _page_clutch_stats(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sco, aco = s["computed"], a["computed"]
    sc, ac = s["career"], a["career"]
    s_t10 = _parse_wl(sv.get("vs_top10_wl", "0-0"))
    a_t10 = _parse_wl(av.get("vs_top10_wl", "0-0"))

    rows = "".join([
        _comparison_row("After Winning 1st Set", f'{sco["after_winning_first_set_pct"]}%', f'{aco["after_winning_first_set_pct"]}%'),
        _comparison_row("After Losing 1st Set", f'{sco["after_losing_first_set_pct"]}%', f'{aco["after_losing_first_set_pct"]}%'),
        _comparison_row("Tiebreak Win %", f'{sco["tiebreaks_won_pct"]}%', f'{aco["tiebreaks_won_pct"]}%'),
        _comparison_row("Deciding Sets Won %", f'{sco["deciding_sets_won_pct"]}%', f'{aco["deciding_sets_won_pct"]}%'),
        _comparison_row("Break Points Saved %", f'{sc["bp_saved_pct"]}%', f'{ac["bp_saved_pct"]}%'),
        _comparison_row("vs Top 10 Record", sv.get("vs_top10_wl", "—"), av.get("vs_top10_wl", "—")),
        _comparison_row("vs Top 10 Win %", f'{_pct(*s_t10)}%', f'{_pct(*a_t10)}%'),
        _comparison_row("Finals Record", sv.get("finals_wl", "—"), av.get("finals_wl", "—")),
    ])

    faqs = [
        ("Who is more clutch, Sinner or Alcaraz?",
         f"It depends on the situation. Sinner is better in tiebreaks ({sco['tiebreaks_won_pct']}% vs {aco['tiebreaks_won_pct']}%) and at saving break points ({sc['bp_saved_pct']}% vs {ac['bp_saved_pct']}%). Alcaraz is better in deciding sets ({aco['deciding_sets_won_pct']}% vs {sco['deciding_sets_won_pct']}%) and after losing the first set ({aco['after_losing_first_set_pct']}% vs {sco['after_losing_first_set_pct']}%). Sinner performs under immediate point pressure; Alcaraz performs under match-level adversity."),
        ("What is Sinner and Alcaraz's record against Top 10 players?",
         f"Sinner is {sv.get('vs_top10_wl','—')} ({_pct(*s_t10)}%) against Top 10 opponents while Alcaraz is {av.get('vs_top10_wl','—')} ({_pct(*a_t10)}%). Both have elite records, but Alcaraz's win percentage against the world's best is slightly higher."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Clutch Stats</div>

<h1>Sinner vs Alcaraz Under Pressure: Who's More Clutch? (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Who's more clutch? The answer isn't simple. Sinner is the better point-by-point pressure player —
winning {sco['tiebreaks_won_pct']}% of tiebreaks and saving {sc['bp_saved_pct']}% of break points. But Alcaraz
is the better match-level competitor — winning {aco['deciding_sets_won_pct']}% of deciding sets and recovering
from a set down {aco['after_losing_first_set_pct']}% of the time. They're clutch in different ways.
</p>

<h2>Pressure Performance Comparison</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Two types of clutch.</strong> Sinner is a micro-clutch player — he thrives on individual big points
(tiebreaks, break points). Alcaraz is a macro-clutch player — he thrives across long matches and adverse situations
(fifth sets, comebacks). Their rivalry is partly defined by this difference.
</div>
<div class="note-box">
<strong>2. The vs Top 10 records confirm their elite status.</strong> Sinner's {sv.get('vs_top10_wl','—')} and Alcaraz's
{av.get('vs_top10_wl','—')} against the world's best are both outstanding. These are players who consistently beat other
elite players — not merely accumulate wins against lower-ranked opponents.
</div>
<div class="note-box">
<strong>3. Finals performance is nearly identical.</strong> Sinner's {sv.get('finals_wl','—')} finals record vs Alcaraz's
{av.get('finals_wl','—')} shows both convert finals into trophies at roughly the same rate. Neither chokes on the biggest
stage — they simply find each other there more often.
</div>

<a class="cta" href="/">📊 Full Rivalry Stats & Analysis → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("clutch-stats")}
"""
    return {
        "slug": "sinner-vs-alcaraz-clutch-stats",
        "title": "Sinner vs Alcaraz Clutch Stats: Pressure Performance 2026",
        "description": f"Sinner: {sco['tiebreaks_won_pct']}% tiebreaks, {sc['bp_saved_pct']}% BP saved. Alcaraz: {aco['deciding_sets_won_pct']}% deciding sets, {aco['after_losing_first_set_pct']}% comebacks. Who's more clutch?",
        "body": body,
        "faqs": faqs,
    }


def _page_prize_money(stats):
    s, a = stats["sinner"], stats["alcaraz"]

    rows = "".join([
        _comparison_row("Career Prize Money", s["prize_career"], a["prize_career"]),
        _comparison_row("Career Titles", s["career_titles"], a["career_titles"]),
        _comparison_row("Grand Slam Titles", s["computed"]["gs_total"], a["computed"]["gs_total"]),
        _comparison_row("Career W/L", s["career_wl"], a["career_wl"]),
        _comparison_row("Career Win %", f'{s["career_win_pct"]}%', f'{a["career_win_pct"]}%'),
        _comparison_row("Age", s["computed"]["age"], a["computed"]["age"], False),
    ])

    s_prize = s["prize_career"]
    a_prize = a["prize_career"]

    faqs = [
        ("Who has earned more prize money, Sinner or Alcaraz?",
         f"Alcaraz has earned {a_prize} in career prize money compared to Sinner's {s_prize}. Despite Sinner having more overall titles ({s['career_titles']} vs {a['career_titles']}), Alcaraz's superior Grand Slam results ({a['computed']['gs_total']} titles vs {s['computed']['gs_total']}) drive his higher earnings total."),
        ("What is the prize money difference between Sinner and Alcaraz?",
         f"Alcaraz leads by approximately $2.6 million in career earnings ({a_prize} vs {s_prize}). Given both players are under 25, their career earnings will likely surpass $100 million each before they're done — Grand Slam prize pools have grown significantly and both dominate the biggest events."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Prize Money</div>

<h1>Sinner vs Alcaraz Prize Money: Career Earnings Compared (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Alcaraz has earned {a_prize} in career prize money compared to Sinner's {s_prize}.
The gap is driven primarily by Grand Slam performance — Alcaraz's {a['computed']['gs_total']} Slam titles
generate significantly more prize money than lower-level tournament wins. Both are already among
the 20 highest earners in tennis history at ages {s['computed']['age']} and {a['computed']['age']}.
</p>

<h2>Earnings & Career Overview</h2>
{_stat_table(rows)}

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Grand Slams drive the gap.</strong> With Slam prize pools now exceeding $60M per tournament,
Alcaraz's {a['computed']['gs_total']}-title advantage generates millions more than Sinner's edge in 250/500
events. A single Grand Slam title is worth more than winning three ATP 500 events.
</div>
<div class="note-box">
<strong>2. Both are on pace for $100M+ careers.</strong> At their current rates — averaging ~$10M/year in prize
money alone — both will surpass $100M in career earnings before turning 30. Add endorsements and both are
already among the highest-paid athletes in tennis.
</div>
<div class="note-box">
<strong>3. Earnings per match played tells a story.</strong> Alcaraz's {a['career_win_pct']}% career win rate means
fewer matches played per title won — he reaches deeper rounds while playing fewer overall matches, maximizing
earnings efficiency. Sinner's {s['career_win_pct']}% is excellent but translates to slightly more wear per dollar earned.
</div>

<a class="cta" href="/">📊 Full Career Stats & Live Data → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("prize-money")}
"""
    return {
        "slug": "sinner-vs-alcaraz-prize-money",
        "title": f"Sinner vs Alcaraz Prize Money: {s_prize} vs {a_prize}",
        "description": f"Alcaraz: {a_prize} career earnings. Sinner: {s_prize}. Who earns more per match? Grand Slam prize money breakdown and earnings trajectory.",
        "body": body,
        "faqs": faqs,
    }


# --- Demand-capture pages (high-volume keywords) ---

def _page_head_to_head(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sc, ac = s["career"], a["career"]
    matches = stats.get("h2h_matches", [])
    derived = stats.get("h2h_derived", {})

    h2h_leader = "Alcaraz" if a["h2h_wins"] > s["h2h_wins"] else "Sinner"
    h2h_score = f'{max(a["h2h_wins"], s["h2h_wins"])}–{min(a["h2h_wins"], s["h2h_wins"])}'

    # Surface H2H breakdown
    surf_h2h = {"clay": [0,0], "hard": [0,0], "grass": [0,0]}
    for m in matches:
        surf = m.get("surface","hard").lower()
        if surf in surf_h2h:
            if m.get("winner") == "sinner": surf_h2h[surf][0] += 1
            else: surf_h2h[surf][1] += 1

    rows = "".join([
        _comparison_row("H2H Record", f'{s["h2h_wins"]} wins', f'{a["h2h_wins"]} wins'),
        _comparison_row("H2H on Clay", surf_h2h["clay"][0], surf_h2h["clay"][1]),
        _comparison_row("H2H on Hard", surf_h2h["hard"][0], surf_h2h["hard"][1]),
        _comparison_row("H2H on Grass", surf_h2h["grass"][0], surf_h2h["grass"][1]),
        _comparison_row("Last 5 Meetings", derived.get("last5_sinner", "—"), derived.get("last5_alcaraz", "—")),
        _comparison_row("Sets Won (Career H2H)", derived.get("sinner_sets_won", "—"), derived.get("alcaraz_sets_won", "—")),
        _comparison_row("Current Ranking", f'#{s["ranking"]}', f'#{a["ranking"]}'),
        _comparison_row("Career Win %", f'{s["career_win_pct"]}%', f'{a["career_win_pct"]}%'),
        _comparison_row("Grand Slam Titles", sco["gs_total"], aco["gs_total"]),
        _comparison_row("Career Titles", s["career_titles"], a["career_titles"]),
    ])

    # Recent matches table
    recent_rows = ""
    for m in matches[:10]:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        recent_rows += f'<tr><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td>{m.get("surface","").title()}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    faqs = [
        ("What is the Sinner vs Alcaraz head-to-head record?",
         f"Alcaraz leads the head-to-head {a['h2h_wins']}–{s['h2h_wins']} across {len(matches)} ATP meetings. On clay: {surf_h2h['clay'][1]}–{surf_h2h['clay'][0]} Alcaraz. On hard courts: {surf_h2h['hard'][1]}–{surf_h2h['hard'][0]} Alcaraz. On grass: {surf_h2h['grass'][0]}–{surf_h2h['grass'][1]} Sinner. The sets won are nearly tied at {derived.get('alcaraz_sets_won','—')}–{derived.get('sinner_sets_won','—')}."),
        ("How many times have Sinner and Alcaraz played each other?",
         f"They have played {len(matches)} times on the ATP Tour since their first meeting at the 2021 Paris Masters. Their rivalry spans Grand Slam finals (Roland Garros 2025, Wimbledon 2025, US Open 2025), Masters 1000 finals, and early-round encounters."),
        ("Who leads the Sinner vs Alcaraz rivalry in 2026?",
         f"In their most recent meeting at the 2026 Monte-Carlo Masters final, Sinner won 7–6(5) 6–3. In the last 5 meetings, Sinner leads {derived.get('last5_sinner','—')}–{derived.get('last5_alcaraz','—')}. The overall H2H remains {a['h2h_wins']}–{s['h2h_wins']} in favor of Alcaraz."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › Head to Head</div>

<h1>Sinner vs Alcaraz Head to Head Record ({len(matches)} Matches)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
{h2h_leader} leads the head-to-head <strong>{h2h_score}</strong> across {len(matches)} ATP Tour meetings.
But the rivalry is closer than the scoreline suggests — the total sets won are {derived.get('sinner_sets_won','—')}–{derived.get('alcaraz_sets_won','—')},
and in their last 5 meetings Sinner leads {derived.get('last5_sinner','—')}–{derived.get('last5_alcaraz','—')}.
This is the defining tennis rivalry of the 2020s.
</p>

<div class="stat-grid" style="max-width:500px">
  <div class="stat-box">
    <div class="lbl">Sinner Wins</div>
    <div class="val" style="color:var(--sinner)">{s['h2h_wins']}</div>
    <div class="lbl">of {len(matches)} meetings</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz Wins</div>
    <div class="val" style="color:var(--alcaraz)">{a['h2h_wins']}</div>
    <div class="lbl">of {len(matches)} meetings</div>
  </div>
</div>

<h2>Full H2H Comparison</h2>
{_stat_table(rows)}

<h2>Recent Meetings</h2>
<table class="match-table">
<thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Surface</th><th>Winner</th><th>Score</th></tr></thead>
<tbody>{recent_rows}</tbody>
</table>
<p style="margin-top:12px"><a href="/matches/">→ View all {len(matches)} match reports with set-by-set breakdowns</a></p>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. The sets tell a different story.</strong> Despite {h2h_leader} leading the match count {h2h_score},
the total sets won are nearly even ({derived.get('sinner_sets_won','—')}–{derived.get('alcaraz_sets_won','—')}). Many of
their matches have gone to five sets or tight tiebreaks — the margins between them are razor-thin.
</div>
<div class="note-box">
<strong>2. Surface matters enormously.</strong> Alcaraz dominates on clay ({surf_h2h['clay'][1]}–{surf_h2h['clay'][0]}),
but Sinner has the edge on grass ({surf_h2h['grass'][0]}–{surf_h2h['grass'][1]}). Hard courts — where they meet most
often — lean {surf_h2h['hard'][1]}–{surf_h2h['hard'][0]} to Alcaraz but include Sinner's 2025 ATP Finals title.
</div>
<div class="note-box">
<strong>3. Momentum has shifted.</strong> In their last 5 meetings, Sinner leads {derived.get('last5_sinner','—')}–{derived.get('last5_alcaraz','—')},
including the 2025 Wimbledon final and 2026 Monte-Carlo Masters final. The H2H gap is closing.
</div>

<a class="cta" href="/">📊 Live Stats, Rankings & Full Rivalry Data → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("head-to-head")}
"""
    return {
        "slug": "sinner-vs-alcaraz-head-to-head",
        "title": f"Sinner vs Alcaraz H2H: {s['h2h_wins']}–{a['h2h_wins']} Record ({len(matches)} Matches)",
        "description": f"Alcaraz leads {a['h2h_wins']}–{s['h2h_wins']} in {len(matches)} meetings. Surface splits, last 5 results, set counts, and every match score. Updated April 2026.",
        "body": body,
        "faqs": faqs,
    }


def _page_who_is_better(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sc, ac = s["career"], a["career"]

    # Tally who leads in each category
    categories = [
        ("Grand Slam Titles", sco["gs_total"], aco["gs_total"]),
        ("Career Titles", s["career_titles"], a["career_titles"]),
        ("Career Win %", s["career_win_pct"], a["career_win_pct"]),
        ("H2H Record", s["h2h_wins"], a["h2h_wins"]),
        ("Weeks at No. 1", sco["weeks_at_no1"], aco["weeks_at_no1"]),
        ("Tiebreak Win %", sco["tiebreaks_won_pct"], aco["tiebreaks_won_pct"]),
        ("Deciding Sets Won %", sco["deciding_sets_won_pct"], aco["deciding_sets_won_pct"]),
        ("Service Games Won %", sc["service_games_won_pct"], ac["service_games_won_pct"]),
        ("Return Games Won %", sc["return_games_won_pct"], ac["return_games_won_pct"]),
        ("Break Points Saved %", sc["bp_saved_pct"], ac["bp_saved_pct"]),
    ]
    s_leads = sum(1 for _, sv_, av_ in categories if sv_ > av_)
    a_leads = sum(1 for _, sv_, av_ in categories if av_ > sv_)

    rows = ""
    for label, sv_, av_ in categories:
        rows += _comparison_row(label, sv_, av_)

    faqs = [
        ("Who is better, Sinner or Alcaraz?",
         f"It depends on what you value. Alcaraz leads in Grand Slams ({aco['gs_total']} vs {sco['gs_total']}), H2H record ({a['h2h_wins']}–{s['h2h_wins']}), and career win percentage ({a['career_win_pct']}% vs {s['career_win_pct']}%). Sinner leads in career titles ({s['career_titles']} vs {a['career_titles']}), weeks at No. 1 ({sco['weeks_at_no1']} vs {aco['weeks_at_no1']}), and tiebreak win rate ({sco['tiebreaks_won_pct']}% vs {aco['tiebreaks_won_pct']}%). Across 10 major statistical categories, Sinner leads {s_leads} and Alcaraz leads {a_leads}."),
        ("Is Sinner or Alcaraz the best player in the world right now?",
         f"Sinner currently holds the No. {s['ranking']} ATP ranking with a {s['ytd_wl']} record ({s['ytd_win_pct']}% win rate) and {s['ytd_titles']} titles in 2026. Alcaraz is No. {a['ranking']} with a {a['ytd_wl']} record ({a['ytd_win_pct']}%). Both have legitimate claims — Sinner's consistency vs Alcaraz's peak level at Grand Slams."),
        ("Who will end up with more Grand Slams, Sinner or Alcaraz?",
         f"Alcaraz currently leads {aco['gs_total']}–{sco['gs_total']} in Grand Slams and is 2 years younger ({aco['age']} vs {sco['age']}). His {a['career_win_pct']}% overall win rate and {_pct(*_parse_wl(av.get('grand_slams_wl','0-0')))}% Grand Slam win rate suggest sustained Slam dominance. But Sinner's {sco['gs_ao']} Australian Open titles show he can dominate specific Slams. Both are on track for double-digit totals."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › Who Is Better?</div>

<h1>Who Is Better: Sinner or Alcaraz? (2026 Stats Verdict)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
The honest answer: it depends on how you define "better." Across 10 major statistical categories,
Sinner leads in <strong>{s_leads}</strong> and Alcaraz leads in <strong>{a_leads}</strong>.
Alcaraz has more Grand Slams ({aco['gs_total']} to {sco['gs_total']}), a better career win rate
({a['career_win_pct']}% to {s['career_win_pct']}%), and the H2H advantage ({a['h2h_wins']}–{s['h2h_wins']}).
Sinner has more total titles ({s['career_titles']} to {a['career_titles']}), more weeks at No. 1
({sco['weeks_at_no1']} to {aco['weeks_at_no1']}), and dominates tiebreaks ({sco['tiebreaks_won_pct']}% to {aco['tiebreaks_won_pct']}%).
</p>

<h2>The Verdict: 10 Key Stats Compared</h2>
{_stat_table(rows)}

<div class="stat-grid" style="max-width:500px;margin-top:24px">
  <div class="stat-box">
    <div class="lbl">Categories Sinner Leads</div>
    <div class="val" style="color:var(--sinner)">{s_leads}</div>
    <div class="lbl">of 10 categories</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Categories Alcaraz Leads</div>
    <div class="val" style="color:var(--alcaraz)">{a_leads}</div>
    <div class="lbl">of 10 categories</div>
  </div>
</div>

<h2>The Case for Each Player</h2>

<div class="note-box" style="border-left-color:var(--sinner)">
<strong>The Case for Sinner:</strong> More career titles ({s['career_titles']}), more weeks at World No. 1
({sco['weeks_at_no1']}), better tiebreak record ({sco['tiebreaks_won_pct']}%), and superior serve stats
(aces: {sc['aces']:,}, 1st serve won: {sc['first_serve_won_pct']}%). He's the more consistent player week-to-week,
with a {s['ytd_wl']} record in 2026 ({s['ytd_win_pct']}%). His {sco['gs_ao']} Australian Open titles prove he can
dominate at the highest level.
</div>

<div class="note-box" style="border-left-color:var(--alcaraz)">
<strong>The Case for Alcaraz:</strong> More Grand Slams ({aco['gs_total']}) across all four surfaces (Career Grand Slam),
better H2H record ({a['h2h_wins']}–{s['h2h_wins']}), higher career win percentage ({a['career_win_pct']}%), and
superior return game ({ac['return_games_won_pct']}% break rate). He's 2 years younger and wins {aco['deciding_sets_won_pct']}%
of deciding sets. His peak level — like the 5h29m 2025 Roland Garros final — may be the highest in tennis.
</div>

<h2>Bottom Line</h2>
<p style="font-size:15px;line-height:1.7;margin-bottom:24px">
If you value Grand Slam titles and peak performance, Alcaraz has the edge.
If you value consistency, serve dominance, and No. 1 longevity, Sinner leads.
They are the two best players in the world by any measure — and the gap between them
is smaller than any rivalry since Federer-Nadal.
</p>

<a class="cta" href="/">📊 Full Live Stats & Rivalry Dashboard → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("who-is-better")}
"""
    return {
        "slug": "who-is-better-sinner-or-alcaraz",
        "title": f"Who Is Better: Sinner or Alcaraz? 2026 Stats Compared",
        "description": f"Sinner leads {s_leads}/10 stat categories (titles, No. 1 weeks, tiebreaks). Alcaraz leads {a_leads}/10 (Grand Slams, H2H, win %). Data-driven verdict inside.",
        "body": body,
        "faqs": faqs,
    }


def _page_clay_stats(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sco, aco = s["computed"], a["computed"]
    matches = stats.get("h2h_matches", [])
    clay_matches = [m for m in matches if m.get("surface","").lower() == "clay"]
    s_clay = _parse_wl(sv.get("on_clay_wl", "0-0"))
    a_clay = _parse_wl(av.get("on_clay_wl", "0-0"))
    s_clay_h2h = sum(1 for m in clay_matches if m.get("winner") == "sinner")
    a_clay_h2h = sum(1 for m in clay_matches if m.get("winner") == "alcaraz")

    rows = "".join([
        _comparison_row("Clay H2H Record", f'{s_clay_h2h} wins', f'{a_clay_h2h} wins'),
        _comparison_row("Career Clay Record", sv.get("on_clay_wl","—"), av.get("on_clay_wl","—")),
        _comparison_row("Career Clay Win %", f'{_pct(*s_clay)}%', f'{_pct(*a_clay)}%'),
        _comparison_row("Roland Garros Titles", sco["gs_rg"], aco["gs_rg"]),
        _comparison_row("Grand Slam Titles (Total)", sco["gs_total"], aco["gs_total"]),
        _comparison_row("Career Win %", f'{s["career_win_pct"]}%', f'{a["career_win_pct"]}%'),
    ])

    # Clay H2H match list
    clay_rows = ""
    for m in clay_matches:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        clay_rows += f'<tr><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    faqs = [
        ("What is the Sinner vs Alcaraz record on clay?",
         f"Alcaraz leads the clay H2H {a_clay_h2h}–{s_clay_h2h} across {len(clay_matches)} clay court meetings. Their clay encounters include the historic 2025 Roland Garros final (5h29m, longest Slam final ever), the 2024 Roland Garros semifinal, the 2025 Italian Open final, the 2022 Croatia Open final, and the 2026 Monte-Carlo Masters final."),
        ("Who is better on clay, Sinner or Alcaraz?",
         f"Alcaraz has the superior overall clay record at {av.get('on_clay_wl','—')} ({_pct(*a_clay)}%) compared to Sinner's {sv.get('on_clay_wl','—')} ({_pct(*s_clay)}%). Alcaraz also has {aco['gs_rg']} Roland Garros titles vs {sco['gs_rg']} for Sinner. However, Sinner won their most recent clay meeting at 2026 Monte-Carlo."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Clay Stats</div>

<h1>Sinner vs Alcaraz on Clay: H2H Record & Stats (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Clay is where this rivalry burns hottest. Alcaraz leads the clay H2H {a_clay_h2h}–{s_clay_h2h} across
{len(clay_matches)} meetings, including the 2025 Roland Garros final — at 5 hours 29 minutes, the longest
Grand Slam final in history. But Sinner took the most recent clay meeting at the 2026 Monte-Carlo Masters,
winning 7–6(5) 6–3 to close the gap.
</p>

<h2>Clay Court Comparison</h2>
{_stat_table(rows)}

<h2>All Clay H2H Matches</h2>
<table class="match-table">
<thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Winner</th><th>Score</th></tr></thead>
<tbody>{clay_rows}</tbody>
</table>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Alcaraz's clay pedigree is elite.</strong> A {av.get('on_clay_wl','—')} career clay record ({_pct(*a_clay)}% win rate)
with {aco['gs_rg']} Roland Garros titles puts him in rare company. His movement, drop shots, and tactical variety
on clay make him the most dangerous clay-courter since Nadal.
</div>
<div class="note-box">
<strong>2. Sinner is closing the gap.</strong> His 2026 Monte-Carlo title (beating Alcaraz in the final) shows
he's evolved his clay game. At {sv.get('on_clay_wl','—')} ({_pct(*s_clay)}%), Sinner is no longer a hard-court
specialist — he's a genuine threat on every surface.
</div>
<div class="note-box">
<strong>3. Roland Garros is the ultimate battleground.</strong> Their 2024 semifinal (Alcaraz won in 5) and
2025 final (Alcaraz won saving 3 match points) were two of the greatest clay matches ever played. This
is where legacies are built and their rivalry reaches its highest level.
</div>

<a class="cta" href="/">📊 Full Surface Stats & Live Data → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("clay-stats")}
"""
    return {
        "slug": "sinner-vs-alcaraz-clay-stats",
        "title": f"Sinner vs Alcaraz Clay Record: {s_clay_h2h}–{a_clay_h2h} H2H Stats",
        "description": f"Alcaraz leads {a_clay_h2h}–{s_clay_h2h} on clay. Career clay records: Alcaraz {av.get('on_clay_wl','—')} ({_pct(*a_clay)}%), Sinner {sv.get('on_clay_wl','—')} ({_pct(*s_clay)}%). All clay matches & analysis.",
        "body": body,
        "faqs": faqs,
    }


def _page_grass_record(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sco, aco = s["computed"], a["computed"]
    matches = stats.get("h2h_matches", [])
    grass_matches = [m for m in matches if m.get("surface","").lower() == "grass"]
    s_grass = _parse_wl(sv.get("on_grass_wl", "0-0"))
    a_grass = _parse_wl(av.get("on_grass_wl", "0-0"))
    s_grass_h2h = sum(1 for m in grass_matches if m.get("winner") == "sinner")
    a_grass_h2h = sum(1 for m in grass_matches if m.get("winner") == "alcaraz")

    rows = "".join([
        _comparison_row("Grass H2H Record", f'{s_grass_h2h} wins', f'{a_grass_h2h} wins'),
        _comparison_row("Career Grass Record", sv.get("on_grass_wl","—"), av.get("on_grass_wl","—")),
        _comparison_row("Career Grass Win %", f'{_pct(*s_grass)}%', f'{_pct(*a_grass)}%'),
        _comparison_row("Wimbledon Titles", sco["gs_wimbledon"], aco["gs_wimbledon"]),
        _comparison_row("1st Serve Won %", f'{s["career"]["first_serve_won_pct"]}%', f'{a["career"]["first_serve_won_pct"]}%'),
        _comparison_row("Aces / Match", sco["avg_aces_match"], aco["avg_aces_match"]),
    ])

    grass_rows = ""
    for m in grass_matches:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        grass_rows += f'<tr><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    faqs = [
        ("What is the Sinner vs Alcaraz record on grass?",
         f"Sinner leads the grass H2H {s_grass_h2h}–{a_grass_h2h}. He won the 2025 Wimbledon final 4–6 6–4 6–4 6–4, ending Alcaraz's 24-match grass winning streak, and also won their 2022 Wimbledon R16 match. The grass court is Sinner's best surface against Alcaraz."),
        ("Who is better on grass, Sinner or Alcaraz?",
         f"Alcaraz has the higher overall grass win rate at {_pct(*a_grass)}% ({av.get('on_grass_wl','—')}) vs Sinner's {_pct(*s_grass)}% ({sv.get('on_grass_wl','—')}). But Sinner wins their head-to-head on grass {s_grass_h2h}–{a_grass_h2h}. Both have Wimbledon titles — Sinner {sco['gs_wimbledon']}, Alcaraz {aco['gs_wimbledon']}."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Grass Record</div>

<h1>Sinner vs Alcaraz on Grass: H2H Record & Wimbledon Stats</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Grass is Sinner's surface in this rivalry. He leads the grass H2H <strong>{s_grass_h2h}–{a_grass_h2h}</strong>,
including the 2025 Wimbledon final where he ended Alcaraz's 24-match grass winning streak. Both have
strong overall grass records — Alcaraz at {av.get('on_grass_wl','—')} ({_pct(*a_grass)}%) and Sinner at
{sv.get('on_grass_wl','—')} ({_pct(*s_grass)}%) — but when they meet on the lawns, Sinner's bigger serve
and flatter ball-striking give him the edge.
</p>

<h2>Grass Court Comparison</h2>
{_stat_table(rows)}

<h2>All Grass H2H Matches</h2>
<table class="match-table">
<thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Winner</th><th>Score</th></tr></thead>
<tbody>{grass_rows}</tbody>
</table>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Sinner's serve dominates on grass.</strong> His {s['career']['first_serve_won_pct']}% first-serve points won
and {sco['avg_aces_match']} aces per match are amplified on the faster grass surface. The low bounce reduces Alcaraz's
ability to generate topspin returns — his biggest weapon on clay.
</div>
<div class="note-box">
<strong>2. The 2025 Wimbledon final was a turning point.</strong> Sinner lost the first set 4–6 then won 18 of the
next 20 games. It was the most dominant grass-court performance in their rivalry and ended Alcaraz's
consecutive grass win streak that stretched back to 2023.
</div>

<a class="cta" href="/">📊 Full Surface & Serve Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("grass-record")}
"""
    return {
        "slug": "sinner-vs-alcaraz-grass-record",
        "title": f"Sinner vs Alcaraz Grass Record: {s_grass_h2h}–{a_grass_h2h} H2H & Wimbledon",
        "description": f"Sinner leads {s_grass_h2h}–{a_grass_h2h} on grass, including the 2025 Wimbledon final. Career grass: Alcaraz {av.get('on_grass_wl','—')}, Sinner {sv.get('on_grass_wl','—')}. Full analysis.",
        "body": body,
        "faqs": faqs,
    }


def _page_hard_court_stats(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sv, av = s["vision_wl"], a["vision_wl"]
    sco, aco = s["computed"], a["computed"]
    matches = stats.get("h2h_matches", [])
    hard_matches = [m for m in matches if m.get("surface","").lower() == "hard"]
    s_hard = _parse_wl(sv.get("on_hard_wl", "0-0"))
    a_hard = _parse_wl(av.get("on_hard_wl", "0-0"))
    s_hard_h2h = sum(1 for m in hard_matches if m.get("winner") == "sinner")
    a_hard_h2h = sum(1 for m in hard_matches if m.get("winner") == "alcaraz")

    rows = "".join([
        _comparison_row("Hard Court H2H", f'{s_hard_h2h} wins', f'{a_hard_h2h} wins'),
        _comparison_row("Career Hard Record", sv.get("on_hard_wl","—"), av.get("on_hard_wl","—")),
        _comparison_row("Career Hard Win %", f'{_pct(*s_hard)}%', f'{_pct(*a_hard)}%'),
        _comparison_row("AO Titles", sco["gs_ao"], aco["gs_ao"]),
        _comparison_row("USO Titles", sco["gs_uso"], aco["gs_uso"]),
        _comparison_row("Indoor Record", sv.get("indoor_wl","—"), av.get("indoor_wl","—")),
    ])

    hard_rows = ""
    for m in hard_matches[:10]:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        hard_rows += f'<tr><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    faqs = [
        ("What is the Sinner vs Alcaraz record on hard courts?",
         f"Alcaraz leads the hard-court H2H {a_hard_h2h}–{s_hard_h2h} across {len(hard_matches)} meetings. Notable hard-court matches include the 2022 US Open quarterfinal (finished at 2:50 AM), 2025 ATP Finals final, and 2025 US Open final."),
        ("Who is better on hard courts, Sinner or Alcaraz?",
         f"Sinner has the better overall hard-court record at {sv.get('on_hard_wl','—')} ({_pct(*s_hard)}%) vs Alcaraz's {av.get('on_hard_wl','—')} ({_pct(*a_hard)}%). Sinner dominates the Australian Open ({sco['gs_ao']} titles) while Alcaraz owns the US Open ({aco['gs_uso']} titles). Head-to-head on hard courts, Alcaraz leads but the margins are tight."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Hard Court Stats</div>

<h1>Sinner vs Alcaraz Hard Court Stats: H2H Record & Analysis (2026)</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Hard courts are where Sinner and Alcaraz meet most often, with {len(hard_matches)} of their {len(matches)}
career meetings on this surface. Alcaraz leads the hard-court H2H {a_hard_h2h}–{s_hard_h2h}, but Sinner's
overall hard-court record is superior: {sv.get('on_hard_wl','—')} ({_pct(*s_hard)}%) vs
{av.get('on_hard_wl','—')} ({_pct(*a_hard)}%). Sinner dominates Melbourne ({sco['gs_ao']} AO titles);
Alcaraz rules Flushing Meadows ({aco['gs_uso']} USO titles).
</p>

<h2>Hard Court Comparison</h2>
{_stat_table(rows)}

<h2>Recent Hard Court Meetings</h2>
<table class="match-table">
<thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Winner</th><th>Score</th></tr></thead>
<tbody>{hard_rows}</tbody>
</table>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Sinner is the hard-court king by volume.</strong> At {sv.get('on_hard_wl','—')} ({_pct(*s_hard)}%),
Sinner's hard-court record is the best in the current top 10. His indoor record of {sv.get('indoor_wl','—')}
adds another dimension — he's lethal on fast indoor hard courts where his serve and ball-striking are maximized.
</div>
<div class="note-box">
<strong>2. Different hard-court Slams, same dominance.</strong> Sinner's {sco['gs_ao']} Australian Open titles vs
Alcaraz's {aco['gs_uso']} US Open titles shows they've carved out hard-court territories. The conditions differ
— Melbourne's heat vs New York's atmosphere — and each player thrives in their preferred environment.
</div>

<a class="cta" href="/">📊 Full Surface & Career Stats → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("hard-court-stats")}
"""
    return {
        "slug": "sinner-vs-alcaraz-hard-court-stats",
        "title": f"Sinner vs Alcaraz Hard Court: {s_hard_h2h}–{a_hard_h2h} H2H Stats (2026)",
        "description": f"Alcaraz leads {a_hard_h2h}–{s_hard_h2h} on hard courts. Career records: Sinner {sv.get('on_hard_wl','—')} ({_pct(*s_hard)}%), Alcaraz {av.get('on_hard_wl','—')} ({_pct(*a_hard)}%). AO vs USO analysis.",
        "body": body,
        "faqs": faqs,
    }


def _page_2026_stats(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    sco, aco = s["computed"], a["computed"]
    matches = stats.get("h2h_matches", [])
    matches_2026 = [m for m in matches if "2026" in m.get("date","")]
    derived = stats.get("h2h_derived", {})

    rows = "".join([
        _comparison_row("2026 Record", s["ytd_wl"], a["ytd_wl"]),
        _comparison_row("2026 Win %", f'{s["ytd_win_pct"]}%', f'{a["ytd_win_pct"]}%'),
        _comparison_row("2026 Titles", s["ytd_titles"], a["ytd_titles"]),
        _comparison_row("Current Ranking", f'#{s["ranking"]}', f'#{a["ranking"]}'),
        _comparison_row("Career Win %", f'{s["career_win_pct"]}%', f'{a["career_win_pct"]}%'),
        _comparison_row("Grand Slam Titles", sco["gs_total"], aco["gs_total"]),
        _comparison_row("H2H Record (All-Time)", f'{s["h2h_wins"]}', f'{a["h2h_wins"]}'),
    ])

    m2026_rows = ""
    for m in matches_2026:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        m2026_rows += f'<tr><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    faqs = [
        ("What is the Sinner vs Alcaraz record in 2026?",
         f"In 2026, Sinner and Alcaraz have met {len(matches_2026)} time(s). Sinner has a {s['ytd_wl']} overall 2026 record ({s['ytd_win_pct']}%) with {s['ytd_titles']} titles, while Alcaraz is {a['ytd_wl']} ({a['ytd_win_pct']}%) with {a['ytd_titles']} titles."),
        ("Who is having a better 2026 season, Sinner or Alcaraz?",
         f"Sinner edges Alcaraz in 2026 with a {s['ytd_win_pct']}% win rate (vs {a['ytd_win_pct']}%), {s['ytd_titles']} titles (vs {a['ytd_titles']}), and the current No. {s['ranking']} ranking. He won their most recent meeting at Monte-Carlo."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › 2026 Stats</div>

<h1>Sinner vs Alcaraz 2026: Season Stats & H2H Results</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
The 2026 season so far: Sinner holds the No. {s['ranking']} ranking with a {s['ytd_wl']} record
({s['ytd_win_pct']}% win rate) and {s['ytd_titles']} titles. Alcaraz is No. {a['ranking']} at {a['ytd_wl']}
({a['ytd_win_pct']}%) with {a['ytd_titles']} titles. They've met {len(matches_2026)} time(s) in 2026
{('— most recently at the Monte-Carlo Masters final, won by Sinner 7–6(5) 6–3.' if matches_2026 else '.')}
</p>

<h2>2026 Season Comparison</h2>
{_stat_table(rows)}

{'<h2>2026 H2H Meetings</h2><table class="match-table"><thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Winner</th><th>Score</th></tr></thead><tbody>' + m2026_rows + '</tbody></table>' if m2026_rows else ''}

<div class="stat-grid" style="max-width:500px;margin-top:24px">
  <div class="stat-box">
    <div class="lbl">Sinner 2026</div>
    <div class="val" style="color:var(--sinner)">{s['ytd_wl']}</div>
    <div class="lbl">{s['ytd_win_pct']}% · {s['ytd_titles']} titles</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz 2026</div>
    <div class="val" style="color:var(--alcaraz)">{a['ytd_wl']}</div>
    <div class="lbl">{a['ytd_win_pct']}% · {a['ytd_titles']} titles</div>
  </div>
</div>

<h2>Key 2026 Storylines</h2>
<div class="note-box">
<strong>1. Sinner's consistency is remarkable.</strong> A {s['ytd_win_pct']}% win rate through April puts him
on pace for one of the best seasons in recent Tour history. Only 2 losses all year show a player
who rarely drops his level.
</div>
<div class="note-box">
<strong>2. The rivalry continues to produce drama.</strong> Their Monte-Carlo final saw Sinner claim his first
clay Masters title, a surface where Alcaraz had been dominant. The H2H stands at {a['h2h_wins']}–{s['h2h_wins']}
overall but Sinner is gaining ground.
</div>
<div class="note-box">
<strong>3. Roland Garros looms.</strong> The French Open will be the next major battleground. After their
epic 2025 final (Alcaraz won in 5 sets), a 2026 rematch would be the most anticipated match of the year.
</div>

<a class="cta" href="/">📊 Live 2026 Stats Updated Daily → sincaraz.app</a>

{_faq_html(faqs)}

{_internal_links("2026-stats")}
"""
    return {
        "slug": "sinner-vs-alcaraz-2026-stats",
        "title": f"Sinner vs Alcaraz 2026: {s['ytd_wl']} vs {a['ytd_wl']} Season Stats",
        "description": f"Sinner: {s['ytd_wl']} ({s['ytd_win_pct']}%), {s['ytd_titles']} titles. Alcaraz: {a['ytd_wl']} ({a['ytd_win_pct']}%), {a['ytd_titles']} titles. 2026 H2H results and season comparison.",
        "body": body,
        "faqs": faqs,
    }


def _page_last_5_matches(stats):
    s, a = stats["sinner"], stats["alcaraz"]
    matches = stats.get("h2h_matches", [])
    derived = stats.get("h2h_derived", {})
    last5 = matches[:5]

    s5 = derived.get("last5_sinner", 0)
    a5 = derived.get("last5_alcaraz", 0)

    match_rows = ""
    for m in last5:
        w = "Sinner" if m.get("winner") == "sinner" else "Alcaraz"
        w_cls = "s" if m.get("winner") == "sinner" else "a"
        match_rows += f'<tr class="win-{m.get("winner","")[0]}"><td>{m.get("date","")}</td><td>{m.get("tournament","")}</td><td>{m.get("round","")}</td><td>{m.get("surface","").title()}</td><td><span class="badge {w_cls}">{w}</span></td><td style="font-family:monospace">{m.get("score","")}</td></tr>'

    # Analyze surface split in last 5
    l5_surfaces = {}
    for m in last5:
        surf = m.get("surface","").lower()
        winner = m.get("winner","")
        if surf not in l5_surfaces:
            l5_surfaces[surf] = {"sinner":0,"alcaraz":0}
        l5_surfaces[surf][winner] += 1

    faqs = [
        ("What happened in the last 5 Sinner vs Alcaraz matches?",
         f"In their last 5 meetings, Sinner leads {s5}–{a5}. The matches: " + "; ".join(
             f'{m.get("tournament","")} {m.get("date","")} — {"Sinner" if m.get("winner")=="sinner" else "Alcaraz"} won {m.get("score","")}'
             for m in last5
         ) + "."),
        ("Who has momentum in the Sinner-Alcaraz rivalry?",
         f"Sinner has won {s5} of the last 5 meetings, including the 2026 Monte-Carlo Masters final and 2025 Wimbledon final. The overall H2H still favors Alcaraz {a['h2h_wins']}–{s['h2h_wins']}, but the recent trend has shifted toward Sinner."),
    ]

    body = f"""<div class="breadcrumb"><a href="/">Home</a> › <a href="/sinner-vs-alcaraz-head-to-head/">H2H</a> › Last 5 Matches</div>

<h1>Sinner vs Alcaraz Last 5 Matches: Results & Momentum</h1>

<p style="font-size:16px;line-height:1.7;margin-bottom:24px">
Recent form says Sinner. He leads the last 5 meetings <strong>{s5}–{a5}</strong>,
reversing what was once a lopsided rivalry. The all-time H2H remains {a['h2h_wins']}–{s['h2h_wins']}
in Alcaraz's favor, but the momentum has clearly shifted — Sinner has won on clay (Monte-Carlo 2026),
grass (Wimbledon 2025), and hard courts (ATP Finals 2025) in recent meetings.
</p>

<div class="stat-grid" style="max-width:500px">
  <div class="stat-box">
    <div class="lbl">Sinner (Last 5)</div>
    <div class="val" style="color:var(--sinner)">{s5}</div>
    <div class="lbl">wins</div>
  </div>
  <div class="stat-box">
    <div class="lbl">Alcaraz (Last 5)</div>
    <div class="val" style="color:var(--alcaraz)">{a5}</div>
    <div class="lbl">wins</div>
  </div>
</div>

<h2>Last 5 Meetings</h2>
<table class="match-table">
<thead><tr><th>Date</th><th>Tournament</th><th>Round</th><th>Surface</th><th>Winner</th><th>Score</th></tr></thead>
<tbody>{match_rows}</tbody>
</table>

<h2>Key Insights</h2>
<div class="note-box">
<strong>1. Sinner now wins on every surface.</strong> His last 5 results include wins on clay (Monte-Carlo), grass (Wimbledon),
and hard courts (ATP Finals). Early in the rivalry, Alcaraz dominated across surfaces — that's no longer the case.
Sinner has become a complete player who can beat Alcaraz anywhere.
</div>
<div class="note-box">
<strong>2. The quality of Sinner's recent wins matters.</strong> These aren't early-round flukes — they're finals.
Monte-Carlo Masters final, Wimbledon final, ATP Finals final. Sinner is beating Alcaraz in the biggest moments,
which is the most meaningful trend shift.
</div>
<div class="note-box">
<strong>3. Sets remain razor-close.</strong> Total sets in the rivalry: {derived.get('sinner_sets_won','—')}–{derived.get('alcaraz_sets_won','—')}.
Even as Sinner wins more matches recently, the individual sets are still tight. This is a rivalry where
one or two points can flip the result.
</div>

<a class="cta" href="/">📊 Live H2H Stats Updated Daily → sincaraz.app</a>

<p style="margin-top:16px"><a href="/matches/">→ View all {len(matches)} match reports with full breakdowns</a></p>

{_faq_html(faqs)}

{_internal_links("last-5-matches")}
"""
    return {
        "slug": "sinner-vs-alcaraz-last-5-matches",
        "title": f"Sinner vs Alcaraz Last 5 Matches: {s5}–{a5} Recent Form",
        "description": f"Sinner leads the last 5 meetings {s5}–{a5}. Monte-Carlo 2026, Wimbledon 2025, ATP Finals 2025 — full results, scores, and momentum analysis.",
        "body": body,
        "faqs": faqs,
    }


TOPIC_GENERATORS = [
    # Demand-capture pages (high volume)
    _page_head_to_head,
    _page_who_is_better,
    _page_clay_stats,
    _page_grass_record,
    _page_hard_court_stats,
    _page_2026_stats,
    _page_last_5_matches,
    # Deep-analysis pages (long tail)
    _page_serve_comparison,
    _page_return_stats,
    _page_grand_slam_record,
    _page_break_points,
    _page_tiebreak_record,
    _page_ranking_history,
    _page_career_titles,
    _page_five_set_record,
    _page_clutch_stats,
    _page_prize_money,
]


def generate_topic_pages():
    """Generate all keyword-rich SEO topic pages at root-level URLs."""
    stats = _load_stats()
    if not stats:
        print("  ⚠ Could not load scraped_stats.json, skipping topic pages")
        return []

    slugs = []
    for gen_fn in TOPIC_GENERATORS:
        page = gen_fn(stats)
        slug = page["slug"]
        slugs.append(slug)
        canonical = f"{BASE_URL}/{slug}/"
        schema = _faq_schema(page["faqs"])
        html = html_page(page["title"], page["description"], canonical, page["body"], schema)
        write(f"{slug}/index.html", html)

    return slugs


# ─── Sitemap ──────────────────────────────────────────────────────────────────

def generate_sitemap(all_matches, topic_slugs=None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        f"  <url><loc>{BASE_URL}/</loc><changefreq>daily</changefreq><priority>1.0</priority><lastmod>{today}</lastmod></url>",
        f"  <url><loc>{BASE_URL}/matches/</loc><changefreq>weekly</changefreq><priority>0.9</priority><lastmod>{today}</lastmod></url>",
    ]
    for surf in SURFACE_INFO:
        urls.append(f"  <url><loc>{BASE_URL}/surface/{surf}/</loc><changefreq>weekly</changefreq><priority>0.8</priority><lastmod>{today}</lastmod></url>")
    for slug in (topic_slugs or []):
        urls.append(f"  <url><loc>{BASE_URL}/{slug}/</loc><changefreq>weekly</changefreq><priority>0.8</priority><lastmod>{today}</lastmod></url>")
    for m in all_matches:
        urls.append(f"  <url><loc>{BASE_URL}/matches/{m['slug']}/</loc><changefreq>monthly</changefreq><priority>0.7</priority><lastmod>{today}</lastmod></url>")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


# ─── Main ─────────────────────────────────────────────────────────────────────

# ATP tournament name aliases — maps scraped names → canonical names used in editorial slugs
_TOURNAMENT_ALIASES = {
    "nitto atp finals": "atp finals",
    "atp finals": "atp finals",
    "atp masters 1000 rome": "italian open",
    "atp masters 1000 cincinnati": "cincinnati open",
    "atp masters 1000 indian wells": "indian wells",
    "atp masters 1000 paris": "paris masters",
    "atp masters 1000 miami": "miami open",
    "atp masters 1000 monte-carlo": "monte-carlo",
    "atp masters 1000 monte carlo": "monte-carlo",
    "beijing": "china open",
    "umag": "croatia open",
}

def _canonical_tournament(name):
    return _TOURNAMENT_ALIASES.get(name.lower().strip(), name.lower().strip())


def load_scraped_matches():
    """Use editorial MATCHES as primary source, then append any brand-new scraped matches.

    New matches are those in scraped h2h_matches whose year+canonical-tournament
    doesn't match any editorial slug — they get auto-generated minimal pages.
    """
    try:
        with open("scraped_stats.json") as f:
            data = json.load(f)
        scraped = data.get("h2h_matches", [])
        if not scraped:
            return MATCHES

        # Build keyword fingerprints for all editorial slugs
        editorial_slugs = {m["slug"] for m in MATCHES}
        # e.g. {"2025-atp-finals": {"atp","finals","2025"}, ...}
        slug_keywords = {}
        for m in MATCHES:
            yr = m.get("year", "")
            words = set(m["slug"].replace("-", " ").split())
            slug_keywords[m["slug"]] = words | {yr}

        def is_known(year, tournament):
            """Return True if this scraped entry maps to an editorial slug."""
            canon = _canonical_tournament(tournament)
            canon_words = {w for w in canon.split() if len(w) > 3}
            for slug, kws in slug_keywords.items():
                if year in kws and canon_words & kws:
                    return True
            return False

        extra = []
        seen_extra = set()
        for sm in scraped:
            date_str = sm.get("date", "")
            year = next((y for y in ["2026","2025","2024","2023","2022","2021","2020"] if y in date_str), "")
            tournament = sm.get("tournament", "")
            if is_known(year, tournament):
                continue
            # Brand-new match — generate a minimal page
            canon = _canonical_tournament(tournament)
            event_key = re.sub(r"[^a-z0-9]+", "-", (canon + "-" + sm.get("round", "")).lower())
            slug_guess = f"{year}-{event_key}"[:50].strip("-")
            if slug_guess not in seen_extra and slug_guess not in editorial_slugs:
                extra.append({
                    "slug":    slug_guess,
                    "date":    date_str,
                    "year":    year,
                    "event":   tournament,
                    "location":"",
                    "round":   sm.get("round", ""),
                    "surface": sm.get("surface", "hard").lower(),
                    "winner":  sm.get("winner", "").lower(),
                    "score":   sm.get("score", "").replace("-", "–"),
                    "duration":"",
                    "note":    auto_generate_note(sm) if sm.get("winner") else "",
                    "sinner_rank": "—", "alcaraz_rank": "—",
                })
                seen_extra.add(slug_guess)

        return MATCHES + extra
    except Exception as e:
        print(f"  Note: could not load scraped matches ({e}), using hardcoded data")
        return MATCHES


def main():
    print(f"=== generate_pages.py — {datetime.now(timezone.utc).isoformat()} ===\n")

    all_matches = load_scraped_matches()
    print(f"  {len(all_matches)} matches loaded\n")

    # Match pages
    print("[1/5] Match pages")
    for m in all_matches:
        write(f"matches/{m['slug']}/index.html", generate_match_page(m, all_matches))

    # Matches index
    print("\n[2/5] Matches index")
    write("matches/index.html", generate_matches_index(all_matches))

    # Surface pages
    print("\n[3/5] Surface pages")
    for surf in SURFACE_INFO:
        write(f"surface/{surf}/index.html", generate_surface_page(surf, all_matches))

    # Topic / comparison pages (long-tail SEO)
    print("\n[4/5] Topic pages (long-tail SEO)")
    topic_slugs = generate_topic_pages()

    # Sitemap
    print("\n[5/5] Sitemap")
    write("sitemap.xml", generate_sitemap(all_matches, topic_slugs))

    total = len(all_matches) + 1 + len(SURFACE_INFO) + len(topic_slugs) + 1
    print(f"\n✅ {total} files generated ({len(all_matches)} match pages, {len(SURFACE_INFO)} surface pages, {len(topic_slugs)} topic pages, 1 index, sitemap)")


if __name__ == "__main__":
    main()
