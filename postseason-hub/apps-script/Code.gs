/**
 * NFL Postseason Survivor: live scoring for Google Sheets.
 *
 * Playoff Hub menu:
 *   - Refresh live scores now  : pulls stats for the current round (Settings > Current round).
 *   - Turn ON auto-refresh     : refreshes every 5 minutes. Quiet when no games are on.
 *   - Turn OFF auto-refresh
 *   - Load player pool         : QB/RB/WR/TE/K on the teams listed on "NFL Teams", with Sleeper IDs.
 *   - Re-import a past round   : for stat corrections.
 *
 * Source: Sleeper's free public API (api.sleeper.app, no key needed). ESPN's API refuses requests
 * from Google Apps Script, so it can't be used here. Sleeper's playoff stats were checked against
 * ESPN box scores for all 13 games of the 2025-26 playoffs and during a live game.
 *
 * Install: Extensions > Apps Script, paste this file, save, reload the spreadsheet.
 */

var SLEEPER = 'https://api.sleeper.app';
var POSITIONS = { QB: 'QB', RB: 'RB', FB: 'RB', WR: 'WR', TE: 'TE', K: 'K' };
// Stats tab columns E..T, in order (must match the workbook).
var STAT_FIELDS = ['passYds', 'passTd', 'int', 'pick6', 'rushYds', 'rushTd', 'rec', 'recYds', 'recTd',
                   'fumLost', 'twoPt', 'xpMade', 'xpMiss', 'fgMade', 'fgYds', 'fgMiss'];
var PLAYER_LAST = 601, STATS_LAST = 1001;
var ID_COL = 13;       // Players!M: Sleeper player ID
var SOURCE_COL = 23;   // Stats!W: "Sleeper" on rows this script owns; manual rows are left alone.
var SOURCE = 'Sleeper';

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

  var games = gamesFromSchedule(fetchJson_(SLEEPER + '/schedule/nfl/post/' + season), week);
  writeGames_(ss, round, games);

  // Skip the stats download when nothing can have changed (no live games, same finished games).
  var props = PropertiesService.getDocumentProperties();
  var sig = round + '|' + games.map(function (g) { return g.id + ':' + g.state; }).join(',');
  var anyLive = games.some(function (g) { return g.state === 'in'; });
  if (!force && !anyLive && props.getProperty('lastSig') === sig) {
    return { summary: 'No live games; nothing new.' };
  }

  var started = games.filter(function (g) { return g.state !== 'pre'; }).length;
  var stats = started ? fetchJson_(SLEEPER + '/v1/stats/nfl/post/' + season + '/' + week) : {};
  var res = writeStats_(ss, round, statsFromSleeper(stats || {}));
  var notes = res.missingId.map(function (n) {
    return ['', n + ' has no Sleeper ID on the Players tab, so he can\'t be scored. Run Playoff Hub > Load player pool.'];
  });
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

/** Replaces this round's Sleeper rows on the Stats tab. Manual rows (Source blank) are kept. */
function writeStats_(ss, round, statsById) {
  var pl = ss.getSheetByName('Players').getRange(2, 1, PLAYER_LAST - 1, ID_COL).getValues();
  var st = ss.getSheetByName('Stats');
  var n = STATS_LAST - 1;
  var keys = st.getRange(2, 1, n, 2).getValues();
  var stats = st.getRange(2, 5, n, STAT_FIELDS.length).getValues();
  var src = st.getRange(2, SOURCE_COL, n, 1).getValues();
  var keepK = [], keepS = [], keepSrc = [];
  for (var i = 0; i < n; i++) {
    if (keys[i][1] === '') continue;
    if (src[i][0] === SOURCE && Number(keys[i][0]) === round) continue;
    keepK.push(keys[i]); keepS.push(stats[i]); keepSrc.push(src[i]);
  }
  var written = 0, missingId = [];
  pl.forEach(function (r) {
    var name = String(r[0]).trim();
    if (!name) return;
    var id = String(r[ID_COL - 1] === null ? '' : r[ID_COL - 1]).trim();
    if (!id) { missingId.push(name); return; }
    var t = statsById[id];
    if (!t || !STAT_FIELDS.some(function (f) { return t[f] !== 0; })) return;
    keepK.push([round, name]);
    keepS.push(STAT_FIELDS.map(function (f) { return t[f]; }));
    keepSrc.push([SOURCE]);
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
  return { written: written, missingId: missingId };
}

/** Writes the Games tab (team -> game state) that the Live leaderboard uses for "yet to play". */
function writeGames_(ss, round, games) {
  var sh = ss.getSheetByName('Games');
  sh.getRange('A4:F40').clearContent();
  var rows = [];
  games.forEach(function (g) {
    rows.push([g.away, g.state, g.detail, g.home, '', g.away + ' @ ' + g.home]);
    rows.push([g.home, g.state, g.detail, g.away, '', g.away + ' @ ' + g.home]);
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

/**
 * Adds QB/RB/WR/TE/K from the playoff teams to the Players tab and fills in Sleeper IDs for
 * players already there (matched by name and team). Sleeper asks that this big download
 * (about 15 MB) run no more than once a day, so use it before the draft and after any trade.
 */
function loadPlayerPool() {
  var ss = SpreadsheetApp.getActive();
  var teams = ss.getSheetByName('NFL Teams').getRange('A4:A17').getValues()
    .map(function (r) { return String(r[0]).trim().toUpperCase(); }).filter(String);
  if (!teams.length) throw new Error('Enter the playoff teams on the NFL Teams tab first.');

  var pool = poolFromSleeper(fetchJson_(SLEEPER + '/v1/players/nfl'), teams);
  var sh = ss.getSheetByName('Players');
  var rows = sh.getRange(2, 1, PLAYER_LAST - 1, ID_COL).getValues();
  var byKey = {}, byName = {};
  pool.forEach(function (p) {
    byKey[normName(p.name) + '|' + p.team] = p;
    (byName[normName(p.name)] = byName[normName(p.name)] || []).push(p);
  });

  var used = {}, idsFilled = 0, last = 1;
  rows.forEach(function (r, i) {
    var name = String(r[0]).trim();
    if (!name) return;
    last = i + 2;
    var id = String(r[ID_COL - 1] || '').trim();
    if (id) { used[id] = true; return; }
    var p = byKey[normName(name) + '|' + String(r[2]).trim().toUpperCase()] ||
            (byName[normName(name)] && byName[normName(name)].length === 1 ? byName[normName(name)][0] : null);
    if (p && !used[p.id]) {
      sh.getRange(i + 2, ID_COL).setValue(p.id);
      used[p.id] = true;
      idsFilled++;
    }
  });

  var add = pool.filter(function (p) { return !used[p.id]; });
  if (last + add.length > PLAYER_LAST) throw new Error('Players tab is full (600 rows).');
  if (add.length) {
    sh.getRange(last + 1, 1, add.length, 3).setValues(add.map(function (p) { return [p.name, p.pos, p.team]; }));
    sh.getRange(last + 1, ID_COL, add.length, 1).setValues(add.map(function (p) { return [p.id]; }));
  }
  SpreadsheetApp.getUi().alert('Added ' + add.length + ' players and filled in ' + idsFilled +
    ' Sleeper IDs. Delete anyone on IR or not worth drafting.');
}

// ---------------------------------------------------------------- pure helpers (unit-tested in Node)

function fetchJson_(url) {
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('Sleeper request failed (' + res.getResponseCode() + '): ' + url);
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

/** Sleeper players JSON -> [{id, name, pos, team}] for fantasy positions on the given teams. */
function poolFromSleeper(players, teams) {
  var want = {};
  teams.forEach(function (t) { want[t] = true; });
  var out = [];
  Object.keys(players).forEach(function (id) {
    var p = players[id];
    var pos = POSITIONS[p.position || ''];
    if (!pos || !p.active || !want[p.team]) return;
    var name = p.full_name || ((p.first_name || '') + ' ' + (p.last_name || '')).trim();
    if (name) out.push({ id: String(p.player_id || id), name: name, pos: pos, team: p.team });
  });
  return out.sort(function (a, b) { return a.team < b.team ? -1 : a.team > b.team ? 1 : a.name < b.name ? -1 : 1; });
}

/** Sleeper schedule JSON -> games for one playoff week: [{id, home, away, state: pre|in|post, detail}]. */
function gamesFromSchedule(schedule, week) {
  var STATE = { pre_game: 'pre', in_game: 'in', complete: 'post' };
  return (schedule || []).filter(function (g) {
    return Number(g.week) === Number(week) && STATE[g.status] && g.home !== 'TBD' && g.away !== 'TBD';
  }).map(function (g) {
    var state = STATE[g.status];
    return { id: g.game_id, home: g.home, away: g.away, state: state,
             detail: state === 'in' ? 'Live' : state === 'post' ? 'Final' : g.date };
  });
}

/** Sleeper stats JSON {playerId: {...}} -> {playerId: {passYds, ...}} in this league's stat fields. */
function statsFromSleeper(stats) {
  var out = {};
  Object.keys(stats).forEach(function (id) {
    var s = stats[id] || {};
    var g = function (k) { return Number(s[k]) || 0; };
    out[id] = {
      passYds: g('pass_yd'), passTd: g('pass_td'), int: g('pass_int'), pick6: g('pass_int_td'),
      rushYds: g('rush_yd'), rushTd: g('rush_td'),
      rec: g('rec'), recYds: g('rec_yd'), recTd: g('rec_td'),
      fumLost: g('fum_lost'), twoPt: g('pass_2pt') + g('rush_2pt') + g('rec_2pt'),
      xpMade: g('xpm'), xpMiss: g('xpmiss'),
      fgMade: g('fgm'), fgYds: g('fgm_yds'), fgMiss: g('fgmiss')
    };
  });
  return out;
}

// Lets the pure functions be unit-tested in Node; ignored by Apps Script.
if (typeof module !== 'undefined') {
  module.exports = { poolFromSleeper: poolFromSleeper, gamesFromSchedule: gamesFromSchedule,
                     statsFromSleeper: statsFromSleeper, normName: normName, STAT_FIELDS: STAT_FIELDS };
}
