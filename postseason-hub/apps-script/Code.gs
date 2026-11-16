/**
 * NFL Postseason Survivor — optional Google Apps Script helpers.
 *
 * Adds a "Playoff Hub" menu with:
 *   - Load player pool: pulls QB/RB/WR/TE/K rosters for the teams on the "NFL Teams" tab.
 *   - Import stats for a round: pulls box scores for that playoff round and writes them to "Stats".
 *
 * Data source: ESPN's public (unofficial, undocumented) site API. It can change without notice,
 * so always eyeball the imported numbers. Anything the script can't score automatically
 * (two-point conversions, field-goal distances it couldn't read) is listed on the "Import Log" tab.
 *
 * Install: Extensions > Apps Script, paste this file, save, reload the spreadsheet.
 */

var ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl';
var POSITIONS = { QB: 'QB', RB: 'RB', FB: 'RB', WR: 'WR', TE: 'TE', K: 'K', PK: 'K' };
// Stats tab columns E..T, in order (must match the workbook).
var STAT_FIELDS = ['passYds', 'passTd', 'int', 'rushYds', 'rushTd', 'rec', 'recYds', 'recTd',
                   'fumLost', 'twoPt', 'xpMade', 'xpMiss', 'fg039', 'fg4049', 'fg50', 'fgMiss'];

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Playoff Hub')
    .addItem('Load player pool from NFL Teams tab', 'loadPlayerPool')
    .addItem('Import stats for a round…', 'importStatsPrompt')
    .addToUi();
}

// ---------------------------------------------------------------- helpers

function fetchJson_(url) {
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    throw new Error('ESPN request failed (' + res.getResponseCode() + '): ' + url);
  }
  return JSON.parse(res.getContentText());
}

function findRowByLabel_(sheet, label) {
  var vals = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues();
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][0]).trim() === label) return i + 1;
  }
  throw new Error('Could not find "' + label + '" in column A of ' + sheet.getName());
}

function num_(s) {
  var n = parseFloat(String(s).replace(/,/g, ''));
  return isNaN(n) ? 0 : n;
}

function madeAtt_(s) {             // "3/4" -> [3, 4]
  var p = String(s).split('/');
  return [num_(p[0]), num_(p[1])];
}

// ---------------------------------------------------------------- player pool

function loadPlayerPool() {
  var ss = SpreadsheetApp.getActive();
  var teams = ss.getSheetByName('NFL Teams').getRange('A4:A17').getValues()
    .map(function (r) { return String(r[0]).trim(); }).filter(String);
  if (!teams.length) throw new Error('Enter the playoff teams on the NFL Teams tab first.');

  var pl = ss.getSheetByName('Players');
  var existing = pl.getRange('A2:A601').getValues().map(function (r) { return String(r[0]).trim(); });
  var have = {};
  existing.forEach(function (n) { if (n) have[n] = true; });
  var next = existing.filter(String).length + 2;

  var rows = [];
  teams.forEach(function (abbr) {
    rosterFromJson(fetchJson_(ESPN + '/teams/' + abbr.toLowerCase() + '/roster'), abbr)
      .forEach(function (p) {
        if (!have[p[0]]) { have[p[0]] = true; rows.push(p); }
      });
  });
  if (next + rows.length - 1 > 601) throw new Error('Players tab is full (600 rows).');
  if (rows.length) pl.getRange(next, 1, rows.length, 3).setValues(rows);
  SpreadsheetApp.getUi().alert('Added ' + rows.length + ' players. Remove anyone on IR or not worth drafting.');
}

/** ESPN roster JSON -> [[name, pos, teamAbbr], ...] (pure; unit-tested). */
function rosterFromJson(json, abbr) {
  var out = [];
  (json.athletes || []).forEach(function (group) {
    (group.items || []).forEach(function (a) {
      var pos = POSITIONS[(a.position && a.position.abbreviation) || ''];
      if (pos) out.push([a.displayName || a.fullName, pos, abbr.toUpperCase()]);
    });
  });
  return out;
}

// ---------------------------------------------------------------- stats import

function importStatsPrompt() {
  var ui = SpreadsheetApp.getUi();
  var resp = ui.prompt('Import stats', 'Which round? (1 = Wild Card, 2 = Divisional, 3 = Conference, 4 = Super Bowl)',
                       ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  var round = parseInt(resp.getResponseText(), 10);
  if (!(round >= 1 && round <= 4)) throw new Error('Round must be 1-4.');
  importStats(round);
}

function importStats(round) {
  var ss = SpreadsheetApp.getActive();
  var set = ss.getSheetByName('Settings');
  var season = set.getRange(findRowByLabel_(set, 'Season (stat import)'), 2).getValue();
  var weekRow = findRowByLabel_(set, 'Round #') + round;
  var week = set.getRange(weekRow, 4).getValue();

  var sb = fetchJson_(ESPN + '/scoreboard?seasontype=3&week=' + week + '&dates=' + season);
  var totals = {};
  var log = [];
  var done = 0, pending = 0;
  (sb.events || []).forEach(function (ev) {
    var completed = ev.status && ev.status.type && ev.status.type.completed;
    if (!completed) { pending++; log.push([round, ev.name, 'Game not final — skipped']); return; }
    done++;
    var parsed = parseSummary(fetchJson_(ESPN + '/summary?event=' + ev.id));
    Object.keys(parsed.players).forEach(function (name) {
      if (!totals[name]) totals[name] = parsed.players[name];
      else STAT_FIELDS.forEach(function (f) { totals[name][f] += parsed.players[name][f]; });
    });
    parsed.notes.forEach(function (n) { log.push([round, ev.name, n]); });
  });

  writeStats_(ss, round, totals);
  writeLog_(ss, log);
  SpreadsheetApp.getUi().alert('Round ' + round + ': imported ' + Object.keys(totals).length + ' players from ' +
    done + ' final game(s)' + (pending ? ' (' + pending + ' not final yet)' : '') +
    '. Check the Import Log tab for two-point conversions and anything needing a manual fix.');
}

/** Replaces this round's rows on the Stats tab, leaving formula columns alone. */
function writeStats_(ss, round, totals) {
  var st = ss.getSheetByName('Stats');
  var LAST = 1001;
  var keys = st.getRange(2, 1, LAST - 1, 2).getValues();
  var stats = st.getRange(2, 5, LAST - 1, STAT_FIELDS.length).getValues();
  var keepK = [], keepS = [];
  for (var i = 0; i < keys.length; i++) {
    if (keys[i][1] === '' || Number(keys[i][0]) === round) continue;
    keepK.push(keys[i]); keepS.push(stats[i]);
  }
  Object.keys(totals).sort().forEach(function (name) {
    var t = totals[name];
    var any = STAT_FIELDS.some(function (f) { return t[f] !== 0; });
    if (!any) return;
    keepK.push([round, name]);
    keepS.push(STAT_FIELDS.map(function (f) { return t[f]; }));
  });
  if (keepK.length > LAST - 1) throw new Error('Stats tab is full.');
  st.getRange(2, 1, LAST - 1, 2).clearContent();
  st.getRange(2, 5, LAST - 1, STAT_FIELDS.length).clearContent();
  if (keepK.length) {
    st.getRange(2, 1, keepK.length, 2).setValues(keepK);
    st.getRange(2, 5, keepS.length, STAT_FIELDS.length).setValues(keepS);
  }
}

function writeLog_(ss, rows) {
  var sh = ss.getSheetByName('Import Log') || ss.insertSheet('Import Log');
  if (sh.getLastRow() === 0) sh.appendRow(['Round', 'Game', 'Note (fix by hand on the Stats tab)', 'Logged at']);
  var now = new Date();
  rows.forEach(function (r) { sh.appendRow(r.concat([now])); });
}

// ---------------------------------------------------------------- parsing (pure; unit-tested)

function blank_() {
  var o = {};
  STAT_FIELDS.forEach(function (f) { o[f] = 0; });
  return o;
}

/** Returns the value of `key` (or a fallback label) for one athlete row in an ESPN stat group. */
function stat_(group, row, key, label) {
  var i = (group.keys || []).indexOf(key);
  if (i < 0) i = (group.labels || []).indexOf(label);
  return i < 0 ? '0' : row.stats[i];
}

/**
 * ESPN game summary JSON -> { players: {name: stats}, notes: [string] }.
 * Field goals by distance come from the scoring plays; misses and PATs from the box score.
 */
function parseSummary(json) {
  var players = {};
  var notes = [];
  var kickers = {};
  function P(name) { return players[name] || (players[name] = blank_()); }

  ((json.boxscore && json.boxscore.players) || []).forEach(function (team) {
    (team.statistics || []).forEach(function (g) {
      (g.athletes || []).forEach(function (row) {
        var name = row.athlete && row.athlete.displayName;
        if (!name || !row.stats || !row.stats.length) return;
        var p = P(name);
        switch (g.name) {
          case 'passing':
            p.passYds += num_(stat_(g, row, 'passingYards', 'YDS'));
            p.passTd += num_(stat_(g, row, 'passingTouchdowns', 'TD'));
            p.int += num_(stat_(g, row, 'interceptions', 'INT'));
            break;
          case 'rushing':
            p.rushYds += num_(stat_(g, row, 'rushingYards', 'YDS'));
            p.rushTd += num_(stat_(g, row, 'rushingTouchdowns', 'TD'));
            break;
          case 'receiving':
            p.rec += num_(stat_(g, row, 'receptions', 'REC'));
            p.recYds += num_(stat_(g, row, 'receivingYards', 'YDS'));
            p.recTd += num_(stat_(g, row, 'receivingTouchdowns', 'TD'));
            break;
          case 'fumbles':
            p.fumLost += num_(stat_(g, row, 'fumblesLost', 'LOST'));
            break;
          case 'kicking':
            var fg = madeAtt_(stat_(g, row, 'fieldGoalsMade/fieldGoalAttempts', 'FG'));
            var xp = madeAtt_(stat_(g, row, 'extraPointsMade/extraPointAttempts', 'XP'));
            p.fgMiss += fg[1] - fg[0];
            p.xpMade += xp[0];
            p.xpMiss += xp[1] - xp[0];
            kickers[name] = { made: fg[0], found: 0 };
            break;
        }
      });
    });
  });

  (json.scoringPlays || []).forEach(function (sp) {
    var text = String(sp.text || '');
    var fg = text.match(/^(.*?)\s+(\d+)\s*(?:Yd|Yard|Yds|yd)s?\.?\s+(?:Field Goal|FG)/i);
    if (fg && kickers[fg[1].trim()]) {
      var k = fg[1].trim(), d = parseInt(fg[2], 10), p = P(k);
      if (d >= 50) p.fg50++; else if (d >= 40) p.fg4049++; else p.fg039++;
      kickers[k].found++;
    } else if (fg || /field goal/i.test(text)) {
      notes.push('Field goal not matched to a kicker: "' + text + '"');
    }
    if (/two[- ]point/i.test(text) && !/fail|no good|unsuccessful/i.test(text)) {
      notes.push('Two-point conversion — credit by hand: "' + text + '"');
    }
  });

  Object.keys(kickers).forEach(function (k) {
    var gap = kickers[k].made - kickers[k].found;
    if (gap > 0) {
      players[k].fg039 += gap;
      notes.push(k + ': ' + gap + ' made FG(s) had no distance — counted as 0-39 yds, please check.');
    } else if (gap < 0) {
      notes.push(k + ': more FG scoring plays than FGs in the box score — please check.');
    }
  });

  return { players: players, notes: notes };
}

// Lets the parsing functions be unit-tested in Node; ignored by Apps Script.
if (typeof module !== 'undefined') {
  module.exports = { parseSummary: parseSummary, rosterFromJson: rosterFromJson, STAT_FIELDS: STAT_FIELDS };
}
