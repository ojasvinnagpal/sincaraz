/**
 * sincaraz.app — Stat comparison & edge logic unit tests
 * Run with: node stats/tests.js
 */

'use strict';

// ── Replicate core functions from index.html ──────────────────────────────

function parseStatValue(raw) {
  if (raw == null) return null;
  var s = String(raw).trim();
  if (!s || s === '—' || s === '-') return null;
  var wl = s.replace(/,/g,'').match(/(\d+)\s*[–\-]\s*(\d+)/);
  if (wl) {
    var w = +wl[1], l = +wl[2];
    if (w + l > 0 && wl[1].length <= 4 && wl[2].length <= 4) return (w / (w + l)) * 100;
  }
  var m = s.replace(/,/g,'').match(/-?\d+\.?\d*/);
  if (!m) return null;
  return parseFloat(m[0]);
}

var EDGE_LOWER_IS_BETTER = ['double fault','dfs','df /','df/','avg. double'];

function computeEdge(sVal, aVal, label) {
  var sNum = parseStatValue(sVal);
  var aNum = parseStatValue(aVal);
  if (sNum == null || aNum == null) return null;
  var lbl = (label || '').toLowerCase();
  var reverse = EDGE_LOWER_IS_BETTER.some(function(k){ return lbl.indexOf(k) !== -1; });
  var sScore = reverse ? -sNum : sNum;
  var aScore = reverse ? -aNum : aNum;
  if (Math.abs(sScore - aScore) < 0.001) return 'tied';
  return sScore > aScore ? 'sinner' : 'alcaraz';
}

// ── Test runner ───────────────────────────────────────────────────────────

var passed = 0, failed = 0;

function assert(desc, actual, expected) {
  if (actual === expected) {
    console.log('  ✓ ' + desc);
    passed++;
  } else {
    console.error('  ✗ ' + desc + ' → expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual));
    failed++;
  }
}

// ── parseStatValue tests ──────────────────────────────────────────────────

console.log('\nparseStatValue:');
assert('null input', parseStatValue(null), null);
assert('em dash', parseStatValue('—'), null);
assert('percentage', parseStatValue('76%'), 76);
assert('integer', parseStatValue('87'), 87);
assert('decimal', parseStatValue('5.9'), 5.9);
assert('win/loss hyphen', parseStatValue('7-10'), 7/17*100);
assert('win/loss en-dash', parseStatValue('7–10'), 7/17*100);
assert('prize money (short)', parseStatValue('$62.3M'), 62.3);
assert('days+ format', parseStatValue('462+'), 462);
assert('W/L with pct "(73%)"', parseStatValue('27-9 (73%)'), 27/36*100);

// ── computeEdge tests ─────────────────────────────────────────────────────

console.log('\ncomputeEdge (higher is better):');
assert('Sinner wins numeric', computeEdge('87%', '85%', '% service games won'), 'sinner');
assert('Alcaraz wins numeric', computeEdge('32%', '34%', '% 1st serve return pts won'), 'alcaraz');
assert('Exact tie', computeEdge('54%', '54%', 'total points won'), 'tied');
assert('Sinner leads tiebreaks', computeEdge('64.7%', '61.6%', '% tiebreaks won'), 'sinner');
assert('Alcaraz leads GS', computeEdge('4', '7', 'grand slams'), 'alcaraz');
assert('Sinner leads H2H wins', computeEdge('7', '10', 'h2h record'), 'alcaraz');
assert('Alcaraz leads clay win%', computeEdge('74.5%', '84.3%', 'clay'), 'alcaraz');
assert('Sinner leads hard win%', computeEdge('82%', '78.3%', 'hard'), 'sinner');

console.log('\ncomputeEdge (lower is better):');
assert('Sinner fewer DFs', computeEdge('1.89', '2.3', 'avg. double faults / match'), 'sinner');
assert('Alcaraz fewer DFs (hypothetical)', computeEdge('2.3', '1.89', 'avg. double faults / match'), 'alcaraz');
assert('DF tie', computeEdge('2.0', '2.0', 'avg. double faults'), 'tied');

console.log('\ncomputeEdge (W/L string comparison):');
assert('Sinner W/L to win%', computeEdge('345-88', '301-68', 'career w/l'), 'alcaraz'); // 79.7% vs 81.6%
assert('Alcaraz clay W/L', computeEdge('70-24', '107-20', 'clay w/l'), 'alcaraz'); // 74.4% vs 84.3%
assert('Sinner grass H2H', computeEdge('2-0', '0-2', 'h2h on grass'), 'sinner');

console.log('\ncomputeEdge (scraped data spot-checks vs known correct values):');
// From scraped_stats.json
assert('BP saved: Sinner 68 vs Alcaraz 64', computeEdge('68%', '64%', '% break points saved'), 'sinner');
assert('BP converted: Sinner 43 vs Alcaraz 42', computeEdge('43%', '42%', '% break points converted'), 'sinner');
assert('1st serve in: Sinner 60 vs Alcaraz 65', computeEdge('60%', '65%', '% 1st serve in'), 'alcaraz');
assert('Ret games won: Sinner 28 vs Alcaraz 31', computeEdge('28%', '31%', '% return games won'), 'alcaraz');
assert('Deciding sets: Sinner 67 vs Alcaraz 71.3', computeEdge('67%', '71.3%', '% deciding sets won'), 'alcaraz');
assert('Tiebreaks: Sinner 64.7 vs Alcaraz 61.6', computeEdge('64.7%', '61.6%', '% tiebreaks won'), 'sinner');
assert('After winning 1st set: Sinner 90.7 vs Alcaraz 93.9', computeEdge('90.7%', '93.9%', 'after winning 1st set'), 'alcaraz');
assert('After losing 1st set: Sinner 43 vs Alcaraz 44.6', computeEdge('43%', '44.6%', 'after losing 1st set'), 'alcaraz');
assert('Avg aces: Sinner 5.9 vs Alcaraz 4.29', computeEdge('5.9', '4.29', 'avg. aces / match'), 'sinner');

console.log('\nH2H data consistency:');
var scraped = require('../scraped_stats.json');
assert('sinner.h2h_wins matches list', scraped.sinner.h2h_wins,
  scraped.h2h_matches.filter(function(m){ return m.winner === 'sinner'; }).length);
assert('alcaraz.h2h_wins matches list', scraped.alcaraz.h2h_wins,
  scraped.h2h_matches.filter(function(m){ return m.winner === 'alcaraz'; }).length);
assert('sinner.h2h_wins == alcaraz.h2h_losses', scraped.sinner.h2h_wins, scraped.alcaraz.h2h_losses);
assert('alcaraz.h2h_wins == sinner.h2h_losses', scraped.alcaraz.h2h_wins, scraped.sinner.h2h_losses);
assert('total matches = 17', scraped.h2h_matches.length, 17);
assert('all matches have winner field', scraped.h2h_matches.every(function(m){ return m.winner === 'sinner' || m.winner === 'alcaraz'; }), true);

// ── Summary ───────────────────────────────────────────────────────────────

console.log('\n──────────────────────────────');
console.log('Results: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
