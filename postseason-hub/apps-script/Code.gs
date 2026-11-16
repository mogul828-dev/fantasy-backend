/**
 * NFL Postseason Survivor: live scoring for Google Sheets.
 *
 * Playoff Hub menu:
 *   - Load player pool         : QB/RB/WR/TE/K rosters (with ESPN IDs) for the teams on "NFL Teams".
 *   - Refresh live scores now  : pulls box scores for the current round (Settings > Current round).
 *   - Turn ON auto-refresh     : refreshes every 5 minutes. Quiet when no games are on (one tiny request).
 *   - Turn OFF auto-refresh
 *   - Re-import a past round   : for stat corrections.
 *
 * Source: ESPN's public site API (free, no key, unofficial). Checked against Sleeper's stats for all
 * 13 games of the 2025-26 playoffs: every stat matched for all 281 players with stats, including
 * field-goal yards, two-point conversions and all 3 pick-sixes.
 *
 * Install: Extensions > Apps Script, paste this file, save, reload the spreadsheet.
 */

var ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl';
var POSITIONS = { QB: 'QB', RB: 'RB', FB: 'RB', WR: 'WR', TE: 'TE', K: 'K', PK: 'K' };
// Stats tab columns E..T, in order (must match the workbook).
var STAT_FIELDS = ['passYds', 'passTd', 'int', 'pick6', 'rushYds', 'rushTd', 'rec', 'recYds', 'recTd',
                   'fumLost', 'twoPt', 'xpMade', 'xpMiss', 'fgMade', 'fgYds', 'fgMiss'];
var PLAYER_LAST = 601, STATS_LAST = 1001;
var SOURCE_COL = 23;   // Stats!W: "ESPN" on rows this script owns; manual rows are left alone.

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Playoff Hub')
    .addItem('Refresh live scores now', 'refreshNow')
    .addItem('Turn ON auto-refresh (every 5 min)', 'enableAutoRefresh')
    .addItem('Turn OFF auto-refresh', 'disableAutoRefresh')
    .addSeparator()
    .addItem('Load player pool from NFL Teams tab', 'loadPlayerPool')
    .addItem('Re-import a past round…', 'reimportPrompt')
    .addToUi();
}

// ---------------------------------------------------------------- menu actions

function refreshNow() {
  var r = refreshRound_(currentRound_(), true);
  SpreadsheetApp.getActive().toast(r.summary, 'Playoff Hub', 8);
}

function enableAutoRefresh() {
  disableAutoRefresh(true);
  ScriptApp.newTrigger('autoRefresh').timeBased().everyMinutes(5).create();
  SpreadsheetApp.getUi().alert('Auto-refresh is ON. Scores update every 5 minutes while games are live.\n' +
    'Remember to change Settings > Current round when a new round starts.');
}

function disableAutoRefresh(silent) {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'autoRefresh') ScriptApp.deleteTrigger(t);
  });
  if (silent !== true) SpreadsheetApp.getUi().alert('Auto-refresh is OFF.');
}

/** Time-driven trigger entry point. */
function autoRefresh() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;     // a previous run is still going
  try { refreshRound_(currentRound_(), false); } finally { lock.releaseLock(); }
}

function reimportPrompt() {
  var ui = SpreadsheetApp.getUi();
  var resp = ui.prompt('Re-import stats', 'Which round? (1 = Wild Card, 2 = Divisional, 3 = Conference, 4 = Super Bowl)',
                       ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  var round = parseInt(resp.getResponseText(), 10);
  if (!(round >= 1 && round <= 4)) throw new Error('Round must be 1-4.');
  ui.alert(refreshRound_(round, true).summary);
}

// ---------------------------------------------------------------- core refresh

function refreshRound_(round, force) {
  var ss = SpreadsheetApp.getActive();
  var set = ss.getSheetByName('Settings');
  var season = set.getRange(findRowByLabel_(set, 'Season (stat import)'), 2).getValue();
  var week = set.getRange(findRowByLabel_(set, 'Round #') + round, 4).getValue();

  var sb = fetchJson_(ESPN + '/scoreboard?seasontype=3&week=' + week + '&dates=' + season);
  var games = gamesFromScoreboard(sb);
  writeGames_(ss, round, games);

  // Skip the heavy part when nothing can have changed (no live games, same set of finished games).
  var props = PropertiesService.getDocumentProperties();
  var sig = round + '|' + games.map(function (g) { return g.id + ':' + g.state; }).join(',');
  var anyLive = games.some(function (g) { return g.state === 'in'; });
  if (!force && !anyLive && props.getProperty('lastSig') === sig) {
    return { summary: 'No live games; nothing new.' };
  }

  var totals = {}, notes = [], started = 0;
  games.forEach(function (g) {
    if (g.state === 'pre') return;
    started++;
    var parsed = parseSummary(fetchJson_(ESPN + '/summary?event=' + g.id));
    mergeTotals_(totals, parsed.players);
    parsed.notes.forEach(function (n) { notes.push([g.name, n]); });
  });

  var res = writeStats_(ss, round, totals);
  res.unmatched.forEach(function (n) { notes.push(['', 'Has stats but is not on the Players tab: ' + n]); });
  writeLog_(ss, round, notes);
  props.setProperty('lastSig', sig);
  return { summary: 'Round ' + round + ': ' + started + ' of ' + games.length + ' games started, ' +
                    res.written + ' players scored' + (anyLive ? ' (live)' : '') + '.' };
}

function currentRound_() {
  var set = SpreadsheetApp.getActive().getSheetByName('Settings');
  var r = parseInt(set.getRange(findRowByLabel_(set, 'Current round (1-4)'), 2).getValue(), 10);
  if (!(r >= 1 && r <= 4)) throw new Error('Settings > Current round must be 1-4.');
  return r;
}

function mergeTotals_(totals, players) {
  Object.keys(players).forEach(function (key) {
    if (!totals[key]) { totals[key] = players[key]; return; }
    STAT_FIELDS.forEach(function (f) { totals[key][f] += players[key][f]; });
  });
}

/** Replaces this round's ESPN rows on the Stats tab. Manual rows (Source blank) are kept. */
function writeStats_(ss, round, totals) {
  // Map ESPN id / name -> name as spelled on the Players tab.
  var pl = ss.getSheetByName('Players').getRange(2, 1, PLAYER_LAST - 1, 13).getValues();
  var byId = {}, byName = {};
  pl.forEach(function (r) {
    var name = String(r[0]).trim();
    if (!name) return;
    byName[normName(name)] = name;
    if (r[12] !== '' && r[12] !== null) byId[String(r[12])] = name;
  });

  var st = ss.getSheetByName('Stats');
  var n = STATS_LAST - 1;
  var keys = st.getRange(2, 1, n, 2).getValues();
  var stats = st.getRange(2, 5, n, STAT_FIELDS.length).getValues();
  var src = st.getRange(2, SOURCE_COL, n, 1).getValues();
  var keepK = [], keepS = [], keepSrc = [];
  for (var i = 0; i < n; i++) {
    if (keys[i][1] === '') continue;
    if (src[i][0] === 'ESPN' && Number(keys[i][0]) === round) continue;
    keepK.push(keys[i]); keepS.push(stats[i]); keepSrc.push(src[i]);
  }
  var written = 0, unmatched = [];
  Object.keys(totals).forEach(function (key) {
    var t = totals[key];
    if (!STAT_FIELDS.some(function (f) { return t[f] !== 0; })) return;
    var name = byId[t.id] || byName[normName(t.name)];
    if (!name) { unmatched.push(t.name); return; }
    keepK.push([round, name]);
    keepS.push(STAT_FIELDS.map(function (f) { return t[f]; }));
    keepSrc.push(['ESPN']);
    written++;
  });
  if (keepK.length > n) throw new Error('Stats tab is full.');
  st.getRange(2, 1, n, 2).clearContent();
  st.getRange(2, 5, n, STAT_FIELDS.length).clearContent();
  st.getRange(2, SOURCE_COL, n, 1).clearContent();
  if (keepK.length) {
    st.getRange(2, 1, keepK.length, 2).setValues(keepK);
    st.getRange(2, 5, keepS.length, STAT_FIELDS.length).setValues(keepS);
    st.getRange(2, SOURCE_COL, keepSrc.length, 1).setValues(keepSrc);
  }
  return { written: written, unmatched: unmatched.sort() };
}

/** Writes the Games tab (team -> game state) that the Live leaderboard uses for "yet to play". */
function writeGames_(ss, round, games) {
  var sh = ss.getSheetByName('Games');
  sh.getRange('A4:F40').clearContent();
  var rows = [];
  games.forEach(function (g) {
    g.teams.forEach(function (t, i) {
      var o = g.teams[1 - i];
      rows.push([t.abbr, g.state, g.detail, o.abbr, t.score + '-' + o.score, g.name]);
    });
  });
  if (rows.length) sh.getRange(4, 1, rows.length, 6).setValues(rows);
  sh.getRange('B1').setValue(round);
  sh.getRange('D1').setValue(new Date());
}

function writeLog_(ss, round, rows) {
  var sh = ss.getSheetByName('Import Log') || ss.insertSheet('Import Log');
  sh.clearContents();
  sh.appendRow(['Round ' + round + ' notes (rewritten on every refresh)', '', new Date()]);
  sh.appendRow(['Game', 'Note']);
  if (!rows.length) rows = [['', 'Nothing to fix.']];
  sh.getRange(3, 1, rows.length, 2).setValues(rows);
}

// ---------------------------------------------------------------- player pool

function loadPlayerPool() {
  var ss = SpreadsheetApp.getActive();
  var teams = ss.getSheetByName('NFL Teams').getRange('A4:A17').getValues()
    .map(function (r) { return String(r[0]).trim(); }).filter(String);
  if (!teams.length) throw new Error('Enter the playoff teams on the NFL Teams tab first.');

  var pl = ss.getSheetByName('Players');
  var existing = pl.getRange(2, 1, PLAYER_LAST - 1, 1).getValues().map(function (r) { return String(r[0]).trim(); });
  var have = {};
  existing.forEach(function (nm) { if (nm) have[normName(nm)] = true; });
  var next = existing.filter(String).length + 2;

  var rows = [];
  teams.forEach(function (abbr) {
    rosterFromJson(fetchJson_(ESPN + '/teams/' + abbr.toLowerCase() + '/roster'), abbr).forEach(function (p) {
      if (!have[normName(p.name)]) { have[normName(p.name)] = true; rows.push(p); }
    });
  });
  if (next + rows.length - 1 > PLAYER_LAST) throw new Error('Players tab is full (600 rows).');
  if (rows.length) {
    pl.getRange(next, 1, rows.length, 3).setValues(rows.map(function (p) { return [p.name, p.pos, p.team]; }));
    pl.getRange(next, 13, rows.length, 1).setValues(rows.map(function (p) { return [p.id]; }));
  }
  SpreadsheetApp.getUi().alert('Added ' + rows.length + ' players. Delete anyone on IR or not worth drafting.');
}

// ---------------------------------------------------------------- pure helpers (unit-tested in Node)

function fetchJson_(url) {
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('ESPN request failed (' + res.getResponseCode() + '): ' + url);
  return JSON.parse(res.getContentText());
}

function findRowByLabel_(sheet, label) {
  var vals = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues();
  for (var i = 0; i < vals.length; i++) if (String(vals[i][0]).trim() === label) return i + 1;
  throw new Error('Could not find "' + label + '" in column A of ' + sheet.getName());
}

function normName(s) {
  return String(s).toLowerCase().replace(/[^a-z]/g, '').replace(/(jr|sr|ii|iii|iv|v)$/, '');
}

function num_(s) {
  var n = parseFloat(String(s).replace(/,/g, ''));
  return isNaN(n) ? 0 : n;
}

function madeAtt_(s) {             // "3/4" -> [3, 4]
  var p = String(s).split('/');
  return [num_(p[0]), num_(p[1])];
}

/** ESPN roster JSON -> [{name, pos, team, id}] for fantasy positions. */
function rosterFromJson(json, abbr) {
  var out = [];
  (json.athletes || []).forEach(function (group) {
    (group.items || []).forEach(function (a) {
      var pos = POSITIONS[(a.position && a.position.abbreviation) || ''];
      if (pos) out.push({ name: a.displayName || a.fullName, pos: pos, team: abbr.toUpperCase(), id: String(a.id || '') });
    });
  });
  return out;
}

/** ESPN scoreboard JSON -> [{id, name, state: pre|in|post, detail, teams: [{abbr, score}]}]. */
function gamesFromScoreboard(sb) {
  return (sb.events || []).map(function (ev) {
    var comp = (ev.competitions || [])[0] || {};
    var st = (ev.status && ev.status.type) || {};
    return {
      id: ev.id,
      name: ev.shortName || ev.name,
      state: st.state || (st.completed ? 'post' : 'pre'),
      detail: st.shortDetail || st.detail || '',
      teams: (comp.competitors || []).map(function (c) {
        return { abbr: c.team && c.team.abbreviation, score: c.score || '0' };
      })
    };
  });
}

function blank_(name, id) {
  var o = { name: name, id: String(id || '') };
  STAT_FIELDS.forEach(function (f) { o[f] = 0; });
  return o;
}

function stat_(group, row, key, label) {
  var i = (group.keys || []).indexOf(key);
  if (i < 0) i = (group.labels || []).indexOf(label);
  return i < 0 ? '0' : row.stats[i];
}

/**
 * ESPN game summary JSON -> { players: {key: stats}, notes: [string] }  (key = ESPN id or name).
 * Field-goal distances and two-point conversions come from the scoring-play text, pick-6 passers
 * from the play-by-play; everything else from the box score.
 */
function parseSummary(json) {
  var players = {}, byName = {}, notes = [], kickers = {};
  function P(name, id) {
    var key = id ? 'id' + id : 'n' + name;
    if (!players[key]) { players[key] = blank_(name, id); byName[name] = players[key]; }
    return players[key];
  }

  ((json.boxscore && json.boxscore.players) || []).forEach(function (team) {
    (team.statistics || []).forEach(function (g) {
      (g.athletes || []).forEach(function (row) {
        var a = row.athlete || {};
        if (!a.displayName || !row.stats || !row.stats.length) return;
        var p;
        switch (g.name) {
          case 'passing':
            p = P(a.displayName, a.id);
            p.passYds += num_(stat_(g, row, 'passingYards', 'YDS'));
            p.passTd += num_(stat_(g, row, 'passingTouchdowns', 'TD'));
            p.int += num_(stat_(g, row, 'interceptions', 'INT'));
            break;
          case 'rushing':
            p = P(a.displayName, a.id);
            p.rushYds += num_(stat_(g, row, 'rushingYards', 'YDS'));
            p.rushTd += num_(stat_(g, row, 'rushingTouchdowns', 'TD'));
            break;
          case 'receiving':
            p = P(a.displayName, a.id);
            p.rec += num_(stat_(g, row, 'receptions', 'REC'));
            p.recYds += num_(stat_(g, row, 'receivingYards', 'YDS'));
            p.recTd += num_(stat_(g, row, 'receivingTouchdowns', 'TD'));
            break;
          case 'fumbles':
            p = P(a.displayName, a.id);
            p.fumLost += num_(stat_(g, row, 'fumblesLost', 'LOST'));
            break;
          case 'kicking':
            p = P(a.displayName, a.id);
            var fg = madeAtt_(stat_(g, row, 'fieldGoalsMade/fieldGoalAttempts', 'FG'));
            var xp = madeAtt_(stat_(g, row, 'extraPointsMade/extraPointAttempts', 'XP'));
            p.fgMade += fg[0];
            p.fgMiss += fg[1] - fg[0];
            p.xpMade += xp[0];
            p.xpMiss += xp[1] - xp[0];
            kickers[a.displayName] = { made: fg[0], found: 0 };
            break;
        }
      });
    });
  });

  (json.scoringPlays || []).forEach(function (sp) {
    var text = String(sp.text || '').trim();
    var type = String((sp.type && sp.type.text) || '');
    var fg = text.match(/^(.*?)\s+(\d+)\s*(?:Yd|Yard|Yds)s?\.?\s+(?:Field Goal|FG)/i);
    if (fg && kickers[fg[1].trim()]) {
      var k = fg[1].trim();
      byName[k].fgYds += parseInt(fg[2], 10);
      kickers[k].found++;
    } else if (/field goal/i.test(type) && !/miss|block/i.test(type)) {
      notes.push('Field goal not matched to a kicker: "' + text + '"');
    }
    if (/two[- ]point/i.test(text) && !/fail|no good|unsuccessful|nullified|reversed/i.test(text)) {
      // "(Caleb Williams Pass to Colston Loveland for Two-Point Conversion)" / "(Saquon Barkley Run for Two-Point Conversion)"
      var m2 = text.match(/\(([^()]+?)\s+(?:Pass to\s+([^()]+?)|Run|Rush)\s+for Two-Point Conversion\)/i);
      var who = m2 ? [m2[1], m2[2]].filter(Boolean).map(function (s) { return s.trim(); }) : [];
      var known = who.filter(function (nm) { return byName[nm]; });
      if (who.length && known.length === who.length) known.forEach(function (nm) { byName[nm].twoPt++; });
      else notes.push('Two-point conversion not credited automatically, enter by hand: "' + text + '"');
    }
  });

  Object.keys(kickers).forEach(function (k) {
    var gap = kickers[k].made - kickers[k].found;
    if (gap > 0) {
      notes.push(k + ': ' + gap + ' made FG(s) have no distance yet (ESPN usually fills it in within minutes). ' +
                 'If it stays, add the yards by hand on the Stats tab.');
    } else if (gap < 0) {
      notes.push(k + ': more FG scoring plays than FGs in the box score, please check.');
    }
  });

  // Pick-sixes: "A.Rodgers pass deep right intended for P.Freiermuth INTERCEPTED by C.Bullock ... TOUCHDOWN."
  var passers = Object.keys(byName).filter(function (nm) { return byName[nm].int > 0; });
  var drives = (json.drives && json.drives.previous) || [];
  if (json.drives && json.drives.current) drives = drives.concat([json.drives.current]);
  var seen = {};
  drives.forEach(function (dr) {
    (dr.plays || []).forEach(function (pl) {
      var t = String((pl.type && pl.type.text) || '');
      var txt = String(pl.text || '');
      if (seen[pl.id] || !/interception return touchdown/i.test(t) || /no play|nullified|reversed/i.test(txt)) return;
      seen[pl.id] = true;
      var m = txt.match(/([A-Z][A-Za-z'\-]*\.\s?[A-Za-z'\-. ]+?)\s+pass\b/);
      var hit = m ? passers.filter(function (nm) { return abbrevName(nm) === abbrevName(m[1]); }) : [];
      if (hit.length === 1) byName[hit[0]].pick6++;
      else if (passers.length === 1) byName[passers[0]].pick6++;
      else notes.push('Pick-6 not matched to a QB, add it by hand: "' + txt.slice(0, 140) + '"');
    });
  });

  return { players: players, notes: notes };
}

/** "Aaron Rodgers" and "A.Rodgers" -> "arodgers" (first initial + last name, suffixes dropped). */
function abbrevName(s) {
  var parts = String(s).replace(/\b(Jr|Sr|II|III|IV|V)\.?$/i, '').trim().split(/[\s.]+/).filter(String);
  if (!parts.length) return '';
  return (parts[0][0] + parts[parts.length - 1]).toLowerCase().replace(/[^a-z]/g, '');
}

// Lets the pure functions be unit-tested in Node; ignored by Apps Script.
if (typeof module !== 'undefined') {
  module.exports = { parseSummary: parseSummary, rosterFromJson: rosterFromJson,
                     gamesFromScoreboard: gamesFromScoreboard, normName: normName, STAT_FIELDS: STAT_FIELDS };
}
