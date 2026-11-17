# NFL Postseason Survivor Hub

A Google Sheets league for a playoff-only fantasy draft where the lowest-scoring managers are cut each round. Scoring updates live during games.

- **League:** 12 teams, half PPR, 6-pt passing TDs, +0.5 TE premium, no defenses
- **Turnovers and kicking:** INT -4 (a pick-6 is an extra -2, so -6 total), field goals 0.1 pt per yard (a 45-yarder = 4.5), missed FG -1, XP +1
- **Lineup:** QB, RB, RB, WR, WR, TE, FLEX (RB/WR/TE), K + 4 bench (12-round snake draft)
- **Eliminations:** you choose 2-4 cuts per round on the Settings tab; the cut managers' players go to waivers

## Files
| File | What it is |
|---|---|
| `NFL_Postseason_Survivor.xlsx` | The league workbook. Import it into Google Sheets. |
| `apps-script/Code.gs` | Live scoring: pulls Sleeper stats every 5 minutes and loads the player pool. |
| `build_workbook.py` | Regenerates the workbook (`python build_workbook.py out.xlsx`). |

## Setup
1. Google Drive → **New → File upload** → `NFL_Postseason_Survivor.xlsx` → **Open with Google Sheets** → **File → Save as Google Sheets**.
2. **Extensions → Apps Script**, delete the sample code, paste in all of `apps-script/Code.gs`, save, and reload the sheet. A **Playoff Hub** menu appears. The first time you use it, Google asks you to allow the script to edit the sheet and connect to an external service (Sleeper).
3. Follow the **Start Here** tab.

## Data source: Sleeper
The script uses Sleeper's free public API (api.sleeper.app). ESPN's API refuses requests that come from Google Apps Script (HTTP 403), so ESPN can't be used from a Google Sheet. Sleeper's playoff stats were checked against ESPN box scores for all 13 games of the 2025-26 playoffs; every stat matched.
- **Player IDs:** live stats are matched to players by **Sleeper ID** (Players tab, column M). **Playoff Hub → Load player pool** fills these in, including for players you typed in yourself.
- **Team abbreviations:** use Sleeper's on the NFL Teams tab (for example `WAS`, not `WSH`).

## Live scoring
- **Playoff Hub → Turn ON auto-refresh** refreshes every 5 minutes. When no games are live, each check is a single small request.
- It scores the round set in **Settings → Current round**, so update that when each round starts.
- **Stats** tab: rows marked `Sleeper` are rewritten on every refresh. To correct a stat, add your own row with Source left blank. Your row is added on top and is never overwritten.
- **Live** tab: the leaderboard, with a red cut line, each manager's starters yet to play and playing now, and the margin above or below the cut. Share it with **File → Share → Publish to web → Live → Web page**. That link updates as scores change and doesn't require a Google login.
- **Import Log** tab: lists anything the script couldn't match, such as a player with stats who isn't on your Players tab.

## Waivers and manual moves
Run the waiver draft offline, then log each pick on the **Transactions** tab: `Add` + player + manager. Releases are `Drop`. An Add always puts the player on that manager's team, even if another team had him, so it also works for corrections and trades. The newest row for a player wins, so deleting a row undoes it. The **Check** column flags mistakes such as a missing manager or adding to an eliminated team. **Rosters** shows a red count when a team is over the roster limit.

## How it was tested
- **Script accuracy:** the parser was run on all 13 games of the 2025-26 playoffs and compared with Sleeper's stats. Every stat matched for all 281 players who had stats, including 2-point conversions, field-goal yards and all 3 pick-sixes.
- **Full Wild Card replay:** the real script loaded the player pool from Sleeper and scored last season's Wild Card games. All 12 managers' scores matched ESPN's box scores exactly. Mid-round (2 games final, 2 live, 2 not started), the yet-to-play and playing-now counts, ranks, cut line and margins were all correct.
- **Live check:** during a Monday night game in progress, Sleeper's stats matched ESPN's box score.
- **What wasn't tested:** this was run in LibreOffice with a mock of Google Sheets, not in Google Sheets itself. Do a quick check after importing: set Season to `2025`, choose **Refresh live scores now**, and confirm the Live tab fills in. Then set Season back to `2026` and delete the test rows on the Stats tab.
