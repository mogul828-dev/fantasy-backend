# NFL Postseason Survivor Hub

A Google Sheets league for a playoff-only fantasy draft where the lowest-scoring managers are cut each round.

- **League:** 12 teams, half PPR, 6-pt passing TDs, +0.5 TE premium, no defenses
- **Lineup:** QB, RB, RB, WR, WR, TE, FLEX (RB/WR/TE), K + 4 bench (12-round snake draft)
- **Eliminations:** you choose 2-4 cuts per round on the Settings tab; the cut managers' players go to waivers

## Files
| File | What it is |
|---|---|
| `NFL_Postseason_Survivor.xlsx` | The league workbook. Import it into Google Sheets. |
| `apps-script/Code.gs` | Optional: menu to load the player pool and import box scores from ESPN. |
| `build_workbook.py` | Regenerates the workbook (`python build_workbook.py out.xlsx`). |

## Setup
1. Google Drive → **New → File upload** → pick `NFL_Postseason_Survivor.xlsx`, then **Open with Google Sheets** and **File → Save as Google Sheets**.
2. Read the **Start Here** tab. It has the full weekly workflow.
3. (Optional) **Extensions → Apps Script**, paste `apps-script/Code.gs`, save, and reload. A **Playoff Hub** menu appears. The first run asks for permission to connect to an external service (ESPN).

## About the stat import
ESPN's API is free but unofficial and undocumented. The parser has been tested against sample data in ESPN's format, but not against live ESPN responses. Before the playoffs, set **Season** on the Settings tab to `2025` and import Round 1 to test it on last season's Wild Card games. Check a few players' points by hand, then clear those rows and set the season back to `2026`. Two-point conversions are always listed on the **Import Log** tab for you to enter by hand.
