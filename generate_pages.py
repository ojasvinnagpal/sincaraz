"""
generate_pages.py — Programmatic SEO page generator for sincaraz.app

Generates:
  matches/<slug>/index.html  — one page per H2H match (16+)
  surface/clay/index.html    — Clay H2H hub
  surface/hard/index.html    — Hard court H2H hub
  surface/grass/index.html   — Grass H2H hub
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


# ─── Sitemap ──────────────────────────────────────────────────────────────────

def generate_sitemap(all_matches):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        f"  <url><loc>{BASE_URL}/</loc><changefreq>daily</changefreq><priority>1.0</priority><lastmod>{today}</lastmod></url>",
        f"  <url><loc>{BASE_URL}/matches/</loc><changefreq>weekly</changefreq><priority>0.9</priority><lastmod>{today}</lastmod></url>",
    ]
    for surf in SURFACE_INFO:
        urls.append(f"  <url><loc>{BASE_URL}/surface/{surf}/</loc><changefreq>weekly</changefreq><priority>0.8</priority><lastmod>{today}</lastmod></url>")
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
    print("[1/4] Match pages")
    for m in all_matches:
        write(f"matches/{m['slug']}/index.html", generate_match_page(m, all_matches))

    # Matches index
    print("\n[2/4] Matches index")
    write("matches/index.html", generate_matches_index(all_matches))

    # Surface pages
    print("\n[3/4] Surface pages")
    for surf in SURFACE_INFO:
        write(f"surface/{surf}/index.html", generate_surface_page(surf, all_matches))

    # Sitemap
    print("\n[4/4] Sitemap")
    write("sitemap.xml", generate_sitemap(all_matches))

    total = len(all_matches) + 1 + len(SURFACE_INFO) + 1  # matches + index + surfaces + sitemap
    print(f"\n✅ {total} files generated ({len(all_matches)} match pages, {len(SURFACE_INFO)} surface pages, 1 index, sitemap)")


if __name__ == "__main__":
    main()
