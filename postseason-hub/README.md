# NFL Postseason Survivor Hub

A Google Sheets league for a playoff-only fantasy draft where the lowest-scoring managers are cut each round. Scoring updates live during games.

- **League:** 12 teams, half PPR, 6-pt passing TDs, +0.5 TE premium, no defenses
- **Lineup:** QB, RB, RB, WR, WR, TE, FLEX (RB/WR/TE), K + 4 bench (12-round snake draft)
- **Eliminations:** you choose 2-4 cuts per round on the Settings tab; the cut managers' players go to waivers

## Files
| File | What it is |
|---|---|
| `NFL_Postseason_Survivor.xlsx` | The league workbook. Import it into Google Sheets. |
| `apps-script/Code.gs` | Live scoring: pulls ESPN box scores every 5 minutes and loads the player pool. |
| `build_workbook.py` | Regenerates the workbook (`python build_workbook.py out.xlsx`). |

## Setup
1. Google Drive → **New → File upload** → `NFL_Postseason_Survivor.xlsx` → **Open with Google Sheets** → **File → Save as Google Sheets**.
2. **Extensions → Apps Script**, delete the sample code, paste in all of `apps-script/Code.gs`, save, and reload the sheet. A **Playoff Hub** menu appears. The first time you use it, Google asks you to allow the script to edit the sheet and connect to an external service (ESPN).
3. Follow the **Start Here** tab.

## Live scoring
- **Playoff Hub → Turn ON auto-refresh** refreshes every 5 minutes. When no games are live, each check is a single small request.
- It scores the round set in **Settings → Current round**, so update that when each round starts.
- **Stats** tab: rows marked `ESPN` are rewritten on every refresh. To correct a stat, add your own row with Source left blank. Your row is added on top and is never overwritten.
- **Live** tab: the leaderboard, with a red cut line, each manager's starters yet to play and playing now, and the margin above or below the cut. Share it with **File → Share → Publish to web → Live → Web page**. That link updates as scores change and doesn't require a Google login.
- **Import Log** tab: lists anything the script couldn't match, such as a player with stats who isn't on your Players tab.

## How it was tested
- **Script accuracy:** the parser was run on all 13 games of the 2025-26 playoffs and compared with Sleeper's stats. Every stat matched for all 308 players, including 2-point conversions and field-goal distances. The one difference was a 44-yard field goal that Sleeper's data is missing and ESPN has.
- **Full Wild Card replay:** the real script ran against recorded ESPN data with 2 games final, 2 live and 2 not yet started. All 12 managers' scores, yet-to-play and playing-now counts, ranks, cut line and margins came out correct.
- **What wasn't tested:** this was run in LibreOffice with a mock of Google Sheets, not in Google Sheets itself. Do a quick check after importing: set Season to `2025`, choose **Refresh live scores now**, and confirm the Live tab fills in. Then set Season back to `2026` and delete the test rows on the Stats tab.
