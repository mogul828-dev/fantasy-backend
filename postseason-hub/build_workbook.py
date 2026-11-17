"""Builds the NFL Postseason Survivor league workbook (import into Google Sheets).

Usage:
    python build_workbook.py OUTPUT.xlsx           # blank league template
    python build_workbook.py OUTPUT.xlsx --demo    # filled with fake test data
"""
import sys
import random

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

N_MGR = 12
N_ROUNDS = 4
DRAFT_ROUNDS = 12
PLAYER_ROWS = 600          # Players!A2:A601
STAT_ROWS = 1000           # Stats!A2:A1001
TXN_ROWS = 500             # Transactions!A2:A501
ROSTER_SLOTS = 16
WAIVER_ROWS = 80

P_LAST = PLAYER_ROWS + 1
S_LAST = STAT_ROWS + 1
T_LAST = TXN_ROWS + 1
D_LAST = DRAFT_ROUNDS * N_MGR + 1
M_LAST = N_MGR + 1

FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_HDR = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=16, bold=True, color="1F3864")
F_SUB = Font(name=FONT, size=10, italic=True, color="595959")
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_LINK = Font(name=FONT, size=10, color="008000")
FILL_HDR = PatternFill("solid", fgColor="1F3864")
FILL_SEC = PatternFill("solid", fgColor="D9E1F2")
FILL_INPUT = PatternFill("solid", fgColor="FFF2CC")
FILL_CALC = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
WRAP = Alignment(wrap_text=True, vertical="top")

RED_FILL = PatternFill("solid", fgColor="F8CBAD")
GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
GREY_FILL = PatternFill("solid", fgColor="D9D9D9")
AMBER_FILL = PatternFill("solid", fgColor="FFE699")


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_SUB


def header(ws, row, labels, col=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=lab)
        c.font = F_HDR
        c.fill = FILL_HDR
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX


def style_range(ws, rng, font=None, fill=None, fmt=None, align=None, border=True):
    for row in ws[rng]:
        for c in row:
            if font:
                c.font = font
            if fill:
                c.fill = fill
            if fmt:
                c.number_format = fmt
            if align:
                c.alignment = align
            if border:
                c.border = BOX


def widths(ws, mapping):
    for col, w in mapping.items():
        ws.column_dimensions[col].width = w


def add_list_validation(ws, rng, formula, prompt=None):
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.error = "Pick a value from the list."
    dv.errorTitle = "Invalid entry"
    dv.showErrorMessage = True
    if prompt:
        dv.prompt = prompt
        dv.showInputMessage = True
    ws.add_data_validation(dv)
    dv.add(rng)


def col(n):
    from openpyxl.utils import get_column_letter
    return get_column_letter(n)


# --------------------------------------------------------------------------
# Settings cell map (referenced by formulas everywhere)
# --------------------------------------------------------------------------
SCORING = [
    # key, label, value, note
    ("pass_yd", "Passing yard", 0.04, "1 point per 25 passing yards"),
    ("pass_td", "Passing TD", 6, "League rule: 6-pt passing TDs"),
    ("int", "Interception thrown", -4, "League rule"),
    ("pick6", "Pick-6 thrown (extra, on top of the INT)", -2, "League rule: a pick-6 costs -4 + -2 = -6"),
    ("rush_yd", "Rushing yard", 0.1, "1 point per 10 rushing yards"),
    ("rush_td", "Rushing TD", 6, ""),
    ("rec", "Reception", 0.5, "League rule: half PPR"),
    ("tep", "TE premium (extra per TE reception)", 0.5, "League rule: TE gets 0.5 + 0.5 = 1.0 per catch"),
    ("rec_yd", "Receiving yard", 0.1, "1 point per 10 receiving yards"),
    ("rec_td", "Receiving TD", 6, ""),
    ("fum", "Fumble lost", -2, "Assumed standard"),
    ("two_pt", "2-pt conversion (pass, rush or catch)", 2, "Assumed standard"),
    ("xp", "Extra point made", 1, "Assumed standard"),
    ("xp_miss", "Extra point missed", -1, "Assumed standard"),
    ("fg_made", "FG made (base points per FG)", 0, "Set to 3 if you want 3 + distance bonus instead"),
    ("fg_yd", "FG made: per yard of distance", 0.1, "League rule: a 45-yd FG = 4.5 pts"),
    ("fg_miss", "FG missed", -1, "Assumed standard"),
]
SCORE_START = 5
S = {k: f"Settings!$B${SCORE_START + i}" for i, (k, *_ ) in enumerate(SCORING)}

LEAGUE_START = SCORE_START + len(SCORING) + 2       # header row
CUR_ROUND = f"Settings!$B${LEAGUE_START + 1}"
BASIS = f"Settings!$B${LEAGUE_START + 2}"
SEASON = f"Settings!$B${LEAGUE_START + 3}"
ROUNDS_HDR = LEAGUE_START + 6
ROUND_FIRST = ROUNDS_HDR + 1
ROUND_LAST = ROUND_FIRST + N_ROUNDS - 1
CUTS_RANGE = f"Settings!$C${ROUND_FIRST}:$C${ROUND_LAST}"
RNAME_RANGE = f"Settings!$B${ROUND_FIRST}:$B${ROUND_LAST}"
ROSTER_MAX = f"Settings!$B${ROUND_LAST + 3 + 8}"     # "Total / draft rounds" row in the Roster table

ROUNDS = [
    (1, "Wild Card", 3, 1),
    (2, "Divisional", 3, 2),
    (3, "Conference Championships", 3, 3),
    (4, "Super Bowl", 0, 5),
]

STAT_COLS = [
    # header, scoring key
    ("Pass Yds", "pass_yd"), ("Pass TD", "pass_td"), ("INT", "int"), ("Pick 6", "pick6"),
    ("Rush Yds", "rush_yd"), ("Rush TD", "rush_td"),
    ("Rec", "rec"), ("Rec Yds", "rec_yd"), ("Rec TD", "rec_td"),
    ("Fum Lost", "fum"), ("2-Pt", "two_pt"),
    ("XP Made", "xp"), ("XP Miss", "xp_miss"),
    ("FG Made", "fg_made"), ("FG Yds", "fg_yd"), ("FG Miss", "fg_miss"),
]
STAT_FIRST_COL = 5   # E
PTS_COL = col(STAT_FIRST_COL + len(STAT_COLS))       # U
CHK_COL = col(STAT_FIRST_COL + len(STAT_COLS) + 1)   # V

SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "K"]
SLOT_POS = {"QB": ["QB"], "RB1": ["RB"], "RB2": ["RB"], "WR1": ["WR"], "WR2": ["WR"],
            "TE": ["TE"], "FLEX": ["RB", "WR", "TE"], "K": ["K"]}

PL = f"Players!$A$2:$A${P_LAST}"


def ppos(ref):
    return f'IFERROR(INDEX(Players!$B$2:$B${P_LAST},MATCH({ref},{PL},0)),"?")'


# --------------------------------------------------------------------------
def build(path, demo=False):
    wb = Workbook()
    start = wb.active
    start.title = "Start Here"
    ws_live = wb.create_sheet("Live")
    ws_set = wb.create_sheet("Settings")
    ws_mgr = wb.create_sheet("Managers")
    ws_tm = wb.create_sheet("NFL Teams")
    ws_pl = wb.create_sheet("Players")
    ws_dr = wb.create_sheet("Draft Board")
    ws_ro = wb.create_sheet("Rosters")
    ws_tx = wb.create_sheet("Transactions")
    ws_ww = wb.create_sheet("Waiver Wire")
    ws_st = wb.create_sheet("Stats")
    ws_lu = wb.create_sheet("Lineups")
    ws_sb = wb.create_sheet("Scoreboard")
    ws_gm = wb.create_sheet("Games")

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False

    # ------------------------------------------------------------ Settings
    ws = ws_set
    title(ws, "League Settings", "Yellow cells with blue text are inputs. Everything else is calculated.")
    ws.cell(row=SCORE_START - 1, column=1, value="Scoring").font = F_BOLD
    header(ws, SCORE_START - 1, ["Scoring", "Points", "Note"])
    for i, (k, lab, val, note) in enumerate(SCORING):
        r = SCORE_START + i
        ws.cell(row=r, column=1, value=lab)
        ws.cell(row=r, column=2, value=val)
        ws.cell(row=r, column=3, value=note)
    style_range(ws, f"A{SCORE_START}:C{SCORE_START + len(SCORING) - 1}", font=F_BASE)
    style_range(ws, f"B{SCORE_START}:B{SCORE_START + len(SCORING) - 1}", font=F_INPUT, fill=FILL_INPUT,
                fmt="0.00;-0.00;0")

    header(ws, LEAGUE_START, ["League", "Value", "Note"])
    league_rows = [
        ("Current round (1-4)", 1, "Change this when a new playoff round starts. Drives the Scoreboard cut line and lineup roster checks."),
        ("Elimination basis", "Cumulative", "Cumulative = total points across all rounds. Weekly = points in the current round only. Ties go to the other number."),
        ("Season (stat import)", 2026, "The NFL season year (the 2026 season's playoffs are played Jan-Feb 2027). Used only by the optional stat-import script."),
    ]
    for i, (lab, val, note) in enumerate(league_rows):
        r = LEAGUE_START + 1 + i
        ws.cell(row=r, column=1, value=lab)
        ws.cell(row=r, column=2, value=val)
        ws.cell(row=r, column=3, value=note)
    style_range(ws, f"A{LEAGUE_START + 1}:C{LEAGUE_START + 3}", font=F_BASE, align=Alignment(vertical="top", wrap_text=True))
    style_range(ws, f"B{LEAGUE_START + 1}:B{LEAGUE_START + 3}", font=F_INPUT, fill=FILL_INPUT, align=CENTER)
    add_list_validation(ws, f"B{LEAGUE_START + 1}", '"1,2,3,4"')
    add_list_validation(ws, f"B{LEAGUE_START + 2}", '"Cumulative,Weekly"')

    header(ws, ROUNDS_HDR, ["Round #", "Round", "Managers cut after round", "ESPN postseason week"])
    for i, (n, name, cuts, wk) in enumerate(ROUNDS):
        r = ROUND_FIRST + i
        for j, v in enumerate((n, name, cuts, wk)):
            ws.cell(row=r, column=1 + j, value=v)
    style_range(ws, f"A{ROUND_FIRST}:D{ROUND_LAST}", font=F_BASE, align=CENTER)
    style_range(ws, f"C{ROUND_FIRST}:C{ROUND_LAST - 1}", font=F_INPUT, fill=FILL_INPUT, align=CENTER)
    ws.cell(row=ROUND_LAST + 1, column=1,
            value="Cuts are your call each week (2-4). The Scoreboard draws the cut line from these numbers. "
                  "ESPN week 4 is the Pro Bowl, so the Super Bowl is week 5.").font = F_SUB

    rr = ROUND_LAST + 3
    header(ws, rr, ["Roster", "Slots", "Note"])
    roster = [("QB", 1, ""), ("RB", 2, ""), ("WR", 2, ""), ("TE", 1, ""),
              ("FLEX", 1, "RB, WR or TE"), ("K", 1, ""), ("Bench", 4, "Assumed. Change by adding draft rounds"),
              ("Total / draft rounds", "=SUM(B{0}:B{1})".format(rr + 1, rr + 7), "No team defenses")]
    for i, (a, b, c) in enumerate(roster):
        ws.cell(row=rr + 1 + i, column=1, value=a)
        ws.cell(row=rr + 1 + i, column=2, value=b)
        ws.cell(row=rr + 1 + i, column=3, value=c)
    style_range(ws, f"A{rr + 1}:C{rr + 8}", font=F_BASE)
    style_range(ws, f"B{rr + 1}:B{rr + 8}", align=CENTER)
    ws.cell(row=rr + 8, column=1).font = F_BOLD
    widths(ws, {"A": 36, "B": 14, "C": 70, "D": 22})

    # ------------------------------------------------------------ Managers
    ws = ws_mgr
    title(ws, "Managers", "Enter names and draft order. When you eliminate someone, type the round they were cut after.")
    header(ws, 3, ["Draft Slot", "Manager", "Team Name", "Eliminated After Round", "Status"])
    for i in range(N_MGR):
        r = 4 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=f"Manager {i + 1}")
        ws.cell(row=r, column=3, value=None)
        ws.cell(row=r, column=5, value=f'=IF(B{r}="","",IF(D{r}="","Alive","Out (R"&D{r}&")"))')
    M_FIRST, M_END = 4, 3 + N_MGR
    style_range(ws, f"A{M_FIRST}:E{M_END}", font=F_BASE)
    style_range(ws, f"A{M_FIRST}:D{M_END}", font=F_INPUT, fill=FILL_INPUT)
    style_range(ws, f"A{M_FIRST}:A{M_END}", align=CENTER)
    style_range(ws, f"D{M_FIRST}:E{M_END}", align=CENTER)
    add_list_validation(ws, f"D{M_FIRST}:D{M_END}", '"1,2,3"')
    ws.conditional_formatting.add(f"E{M_FIRST}:E{M_END}",
                                  FormulaRule(formula=[f'LEFT(E{M_FIRST},3)="Out"'], fill=GREY_FILL))
    ws.conditional_formatting.add(f"E{M_FIRST}:E{M_END}",
                                  FormulaRule(formula=[f'E{M_FIRST}="Alive"'], fill=GREEN_FILL))
    widths(ws, {"A": 11, "B": 22, "C": 26, "D": 22, "E": 14})
    ws.freeze_panes = "A4"
    MGR_NAMES = f"Managers!$B${M_FIRST}:$B${M_END}"
    MGR_SLOT = f"Managers!$A${M_FIRST}:$A${M_END}"
    MGR_ELIM = f"Managers!$D${M_FIRST}:$D${M_END}"
    MGR_STAT = f"Managers!$E${M_FIRST}:$E${M_END}"

    # ------------------------------------------------------------ NFL Teams
    ws = ws_tm
    title(ws, "NFL Playoff Teams", "Enter the 14 playoff teams once the field is set. Mark the round each team loses in.")
    header(ws, 3, ["Abbr", "Team", "Conference", "Seed", "Eliminated in Round", "Status"])
    T_FIRST, T_END = 4, 17
    for r in range(T_FIRST, T_END + 1):
        ws.cell(row=r, column=6, value=f'=IF(A{r}="","",IF(E{r}="","Alive","Out (R"&E{r}&")"))')
    style_range(ws, f"A{T_FIRST}:F{T_END}", font=F_BASE, align=CENTER)
    style_range(ws, f"A{T_FIRST}:E{T_END}", font=F_INPUT, fill=FILL_INPUT, align=CENTER)
    add_list_validation(ws, f"C{T_FIRST}:C{T_END}", '"AFC,NFC"')
    add_list_validation(ws, f"E{T_FIRST}:E{T_END}", '"1,2,3,4"')
    ws.conditional_formatting.add(f"F{T_FIRST}:F{T_END}",
                                  FormulaRule(formula=[f'LEFT(F{T_FIRST},3)="Out"'], fill=GREY_FILL))
    ws.cell(row=T_END + 2, column=1,
            value="Abbreviations must match the NFL Team column on the Players tab (use ESPN's: KC, BUF, PHI, SF, ...). "
                  "The 1 seeds have a Wild Card bye; their players score 0 in Round 1.").font = F_SUB
    widths(ws, {"A": 8, "B": 24, "C": 12, "D": 8, "E": 20, "F": 12})
    ws.freeze_panes = "A4"
    TEAM_ABBR = f"'NFL Teams'!$A${T_FIRST}:$A${T_END}"
    TEAM_ELIM = f"'NFL Teams'!$E${T_FIRST}:$E${T_END}"

    # ------------------------------------------------------------ Players
    ws = ws_pl
    hdr = ["Player", "Pos", "NFL Team", "NFL Status", "Drafted By", "Last Txn Row",
           "Owner (raw)", "Owner", "Status", "Roster Key", "Waiver Key", "Total Pts", "ESPN ID", "Game"]
    header(ws, 1, hdr)
    for r in range(2, P_LAST + 1):
        ws[f"D{r}"] = (f'=IF(OR($A{r}="",$C{r}=""),"",IFERROR(IF(INDEX({TEAM_ELIM},MATCH($C{r},{TEAM_ABBR},0))="",'
                       f'"Alive","Out"),"Not in playoffs"))')
        ws[f"E{r}"] = (f"=IF($A{r}=\"\",\"\",IFERROR(INDEX('Draft Board'!$E$2:$E${D_LAST},"
                       f"MATCH($A{r},'Draft Board'!$F$2:$F${D_LAST},0)),\"\"))")
        ws[f"F{r}"] = (f'=IF($A{r}="","",SUMPRODUCT(MAX((Transactions!$C$2:$C${T_LAST}=$A{r})'
                       f'*ROW(Transactions!$C$2:$C${T_LAST}))))')
        ws[f"G{r}"] = (f'=IF($A{r}="","",IF(F{r}=0,E{r},IF(INDEX(Transactions!$B:$B,F{r})="Add",'
                       f'INDEX(Transactions!$D:$D,F{r}),"")))')
        ws[f"H{r}"] = (f'=IF(G{r}="","",IF(IFERROR(INDEX({MGR_STAT},MATCH(G{r},{MGR_NAMES},0)),"Alive")="Alive",G{r},""))')
        ws[f"I{r}"] = f'=IF($A{r}="","",IF(D{r}="Out","NFL Out",IF(H{r}="","Available",H{r})))'
        ws[f"J{r}"] = f'=IF(H{r}="","",H{r}&"#"&COUNTIF($H$2:H{r},H{r}))'
        ws[f"K{r}"] = f'=IF(I{r}="Available",B{r}&"#"&COUNTIFS($I$2:I{r},"Available",$B$2:B{r},B{r}),"")'
        ws[f"L{r}"] = f'=IF($A{r}="","",SUMIFS(Stats!${PTS_COL}$2:${PTS_COL}${S_LAST},Stats!$B$2:$B${S_LAST},$A{r}))'
        ws[f"N{r}"] = (f'=IF(OR($A{r}="",Games!$B$1<>{CUR_ROUND}),"",IFERROR(INDEX(Games!$B$4:$B$40,'
                       f'MATCH($C{r},Games!$A$4:$A$40,0)),""))')
    style_range(ws, f"A2:L{P_LAST}", font=F_BASE, border=False)
    style_range(ws, f"A2:C{P_LAST}", font=F_INPUT, fill=FILL_INPUT, border=False)
    style_range(ws, f"D2:L{P_LAST}", fill=FILL_CALC, border=False)
    style_range(ws, f"L2:L{P_LAST}", fmt="0.00", fill=FILL_CALC, border=False)
    style_range(ws, f"M2:M{P_LAST}", font=F_INPUT, fill=FILL_INPUT, border=False)
    style_range(ws, f"N2:N{P_LAST}", fill=FILL_CALC, border=False, align=CENTER)
    add_list_validation(ws, f"B2:B{P_LAST}", '"QB,RB,WR,TE,K"')
    ws.conditional_formatting.add(f"I2:I{P_LAST}", FormulaRule(formula=['$I2="Available"'], fill=GREEN_FILL))
    ws.conditional_formatting.add(f"I2:I{P_LAST}", FormulaRule(formula=['$I2="NFL Out"'], fill=GREY_FILL))
    ws.conditional_formatting.add(f"D2:D{P_LAST}", FormulaRule(formula=['$D2="Not in playoffs"'], fill=RED_FILL))
    for c_ in ("F", "G", "J", "K"):
        ws.column_dimensions[c_].hidden = True
    ws["A1"].comment = Comment("Type players here (or load them with the Apps Script menu). "
                               "Names must be spelled the same everywhere they are used.", "Commissioner")
    widths(ws, {"A": 26, "B": 7, "C": 10, "D": 15, "E": 18, "H": 18, "I": 18, "L": 10, "M": 11, "N": 8})
    ws["M1"].comment = Comment("Filled by 'Load player pool'. Lets live stats match players even if you "
                               "change how a name is spelled. Optional.", "Commissioner")
    ws["N1"].comment = Comment("pre = game not started, in = playing now, post = final. Blank = no game "
                               "this round (bye or eliminated). From the Games tab.", "Commissioner")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:N{P_LAST}"

    # ------------------------------------------------------------ Draft Board
    ws = ws_dr
    header(ws, 1, ["Pick", "Round", "Pick in Round", "Draft Slot", "Manager", "Player", "Pos", "NFL Team", "Check"])
    for p in range(1, DRAFT_ROUNDS * N_MGR + 1):
        r = p + 1
        rd = (p - 1) // N_MGR + 1
        pir = (p - 1) % N_MGR + 1
        slot = pir if rd % 2 == 1 else N_MGR + 1 - pir
        ws.cell(row=r, column=1, value=p)
        ws.cell(row=r, column=2, value=rd)
        ws.cell(row=r, column=3, value=pir)
        ws.cell(row=r, column=4, value=slot)
        ws[f"E{r}"] = f'=IFERROR(INDEX({MGR_NAMES},MATCH(D{r},{MGR_SLOT},0)),"")'
        ws[f"G{r}"] = f'=IF(F{r}="","",{ppos(f"F{r}")})'
        ws[f"H{r}"] = f'=IF(F{r}="","",IFERROR(INDEX(Players!$C$2:$C${P_LAST},MATCH(F{r},{PL},0)),"?"))'
        ws[f"I{r}"] = (f'=IF(F{r}="","",IF(COUNTIF($F$2:$F${D_LAST},F{r})>1,"DUPLICATE",'
                       f'IF(G{r}="?","Not in Players tab","OK")))')
    style_range(ws, f"A2:I{D_LAST}", font=F_BASE, align=CENTER)
    style_range(ws, f"F2:F{D_LAST}", font=F_INPUT, fill=FILL_INPUT, align=Alignment(horizontal="left"))
    style_range(ws, f"E2:E{D_LAST}", align=Alignment(horizontal="left"))
    add_list_validation(ws, f"F2:F{D_LAST}", f"={PL}", "Pick a player (type to search)")
    ws.conditional_formatting.add(f"A2:I{D_LAST}", FormulaRule(formula=['MOD($B2,2)=0'], fill=FILL_CALC))
    ws.conditional_formatting.add(f"I2:I{D_LAST}", FormulaRule(formula=['AND($I2<>"",$I2<>"OK")'], fill=RED_FILL))
    widths(ws, {"A": 7, "B": 8, "C": 9, "D": 9, "E": 20, "F": 26, "G": 7, "H": 10, "I": 18})
    ws.freeze_panes = "A2"

    # ------------------------------------------------------------ Rosters
    ws = ws_ro
    title(ws, "Current Rosters", "Updates automatically from the Draft Board, Transactions and eliminations. ✖ = NFL team eliminated.")
    ws.cell(row=3, column=1, value="Manager").font = F_BOLD
    ws.cell(row=4, column=1, value="Status").font = F_BOLD
    for i in range(N_MGR):
        c = col(2 + i)
        ws[f"{c}3"] = f"=Managers!$B${M_FIRST + i}"
        ws[f"{c}4"] = f"=Managers!$E${M_FIRST + i}"
        for s in range(1, ROSTER_SLOTS + 1):
            r = 4 + s
            m = f'MATCH({c}$3&"#"&$A{r},Players!$J$2:$J${P_LAST},0)'
            ws[f"{c}{r}"] = (f'=IFERROR(INDEX({PL},{m})&" · "&INDEX(Players!$B$2:$B${P_LAST},{m})&" · "'
                             f'&INDEX(Players!$C$2:$C${P_LAST},{m})&IF(INDEX(Players!$D$2:$D${P_LAST},{m})="Out","  ✖",""),"")')
        cnt_r = 5 + ROSTER_SLOTS
        ws[f"{c}{cnt_r}"] = f'=IF({c}$3="","",COUNTIF(Players!$H$2:$H${P_LAST},{c}$3))'
        ws[f"{c}{cnt_r + 1}"] = f'=IF({c}$3="","",COUNTIFS(Players!$H$2:$H${P_LAST},{c}$3,Players!$D$2:$D${P_LAST},"Alive"))'
    for s in range(1, ROSTER_SLOTS + 1):
        ws.cell(row=4 + s, column=1, value=s)
    cnt_r = 5 + ROSTER_SLOTS
    ws.cell(row=cnt_r, column=1, value="Players rostered")
    ws.cell(row=cnt_r + 1, column=1, value="Still alive in NFL")
    last_c = col(1 + N_MGR)
    style_range(ws, f"A3:{last_c}{cnt_r + 1}", font=F_BASE)
    style_range(ws, f"B3:{last_c}3", font=F_HDR, fill=FILL_HDR, align=CENTER)
    style_range(ws, f"B4:{last_c}4", font=F_BASE, fill=FILL_SEC, align=CENTER)
    style_range(ws, f"A{cnt_r}:{last_c}{cnt_r + 1}", font=F_BOLD, fill=FILL_SEC)
    style_range(ws, f"B{cnt_r}:{last_c}{cnt_r + 1}", align=CENTER)
    style_range(ws, f"A5:A{4 + ROSTER_SLOTS}", align=CENTER)
    ws.conditional_formatting.add(f"B5:{last_c}{4 + ROSTER_SLOTS}",
                                  FormulaRule(formula=['RIGHT(B5,1)="✖"'], font=Font(name=FONT, color="A6A6A6", strike=True)))
    ws.conditional_formatting.add(f"B3:{last_c}4", FormulaRule(formula=['LEFT(B$4,3)="Out"'], fill=GREY_FILL))
    ws.conditional_formatting.add(f"B{cnt_r}:{last_c}{cnt_r}",
                                  FormulaRule(formula=[f'N(B{cnt_r})>$A${cnt_r + 3}'], fill=RED_FILL))
    ws[f"A{cnt_r + 3}"] = f"={ROSTER_MAX}"     # same-sheet copy for the conditional format
    ws[f"A{cnt_r + 3}"].font = Font(name=FONT, size=8, color="FFFFFF")
    ws.cell(row=cnt_r + 2, column=1, value="Red count = over the roster limit on Settings: log a Drop on Transactions.").font = F_SUB
    widths(ws, {"A": 18, **{col(2 + i): 30 for i in range(N_MGR)}})
    ws.freeze_panes = "B5"

    # ------------------------------------------------------------ Transactions
    ws = ws_tx
    header(ws, 1, ["After Round", "Type", "Player", "Manager", "Notes", "Player Status Now", "Check"])
    for r in range(2, T_LAST + 1):
        ws[f"F{r}"] = f'=IF(C{r}="","",IFERROR(INDEX(Players!$I$2:$I${P_LAST},MATCH(C{r},{PL},0)),"Not in Players tab"))'
        last_row_for_player = f'SUMPRODUCT(MAX(($C$2:$C${T_LAST}=C{r})*ROW($C$2:$C${T_LAST})))'
        ws[f"G{r}"] = (f'=IF(AND(B{r}="",C{r}=""),"",IF(OR(B{r}="",C{r}="",D{r}=""),"Fill in Type, Player and Manager",'
                       f'IF(F{r}="Not in Players tab","Add the player to the Players tab first",'
                       f'IF(COUNTIF({MGR_NAMES},D{r})=0,"Unknown manager",'
                       f'IF(AND(B{r}="Add",IFERROR(INDEX({MGR_STAT},MATCH(D{r},{MGR_NAMES},0)),"")<>"Alive"),"Manager is eliminated",'
                       f'IF({last_row_for_player}>ROW(),"OK (a later row overrides this one)",'
                       f'IF(AND(B{r}="Add",F{r}="NFL Out"),"OK, but NFL team is eliminated","OK")))))))')
    style_range(ws, f"A2:G{T_LAST}", font=F_BASE, border=False)
    style_range(ws, f"A2:E{T_LAST}", font=F_INPUT, fill=FILL_INPUT, border=False)
    style_range(ws, f"F2:G{T_LAST}", fill=FILL_CALC, border=False)
    ws.conditional_formatting.add(f"G2:G{T_LAST}", FormulaRule(formula=['AND($G2<>"",LEFT($G2,2)<>"OK")'], fill=RED_FILL))
    add_list_validation(ws, f"A2:A{T_LAST}", '"1,2,3"')
    add_list_validation(ws, f"B2:B{T_LAST}", '"Add,Drop"')
    add_list_validation(ws, f"C2:C{T_LAST}", f"={PL}")
    add_list_validation(ws, f"D2:D{T_LAST}", f"={MGR_NAMES}")
    ws["B1"].comment = Comment("Add = waiver claim (player joins that manager). Drop = manager releases player to the pool. "
                               "Players of eliminated managers return to the pool automatically, no Drop needed. "
                               "Adding a player who is on another team moves him (works for trades too). "
                               "Log rows in the order they happen: the newest row for a player wins.", "Commissioner")
    widths(ws, {"A": 12, "B": 8, "C": 26, "D": 20, "E": 30, "F": 18, "G": 34})
    ws.freeze_panes = "A2"

    # ------------------------------------------------------------ Waiver Wire
    ws = ws_ww
    title(ws, "Waiver Wire: Available Players",
          "Players with no active owner whose NFL team is still alive. Pts = total fantasy points so far this postseason.")
    positions = ["QB", "RB", "WR", "TE", "K"]
    for i, pos in enumerate(positions):
        c1 = 2 + i * 3
        ws.cell(row=3, column=c1, value=pos)
        ws.merge_cells(start_row=3, start_column=c1, end_row=3, end_column=c1 + 1)
        header(ws, 4, ["Player · Team", "Pts"], col=c1)
        L1, L2 = col(c1), col(c1 + 1)
        for k in range(1, WAIVER_ROWS + 1):
            r = 4 + k
            m = f'MATCH("{pos}#"&$A{r},Players!$K$2:$K${P_LAST},0)'
            ws[f"{L1}{r}"] = f'=IFERROR(INDEX({PL},{m})&" · "&INDEX(Players!$C$2:$C${P_LAST},{m}),"")'
            ws[f"{L2}{r}"] = f'=IFERROR(INDEX(Players!$L$2:$L${P_LAST},{m}),"")'
        style_range(ws, f"{L1}5:{L2}{4 + WAIVER_ROWS}", font=F_BASE)
        style_range(ws, f"{L2}5:{L2}{4 + WAIVER_ROWS}", fmt="0.00", align=CENTER)
        style_range(ws, f"{L1}3:{L1}3", font=F_HDR, fill=PatternFill("solid", fgColor="2F5597"), align=CENTER)
        ws.column_dimensions[L1].width = 28
        ws.column_dimensions[L2].width = 8
        ws.column_dimensions[col(c1 + 2)].width = 2
    for k in range(1, WAIVER_ROWS + 1):
        ws.cell(row=4 + k, column=1, value=k).font = Font(name=FONT, size=8, color="A6A6A6")
    ws.column_dimensions["A"].width = 4
    ws.freeze_panes = "A5"

    # ------------------------------------------------------------ Stats
    ws = ws_st
    hdr = ["Round", "Player", "Pos", "NFL Team"] + [h for h, _ in STAT_COLS] + ["Fantasy Pts", "Check", "Source"]
    header(ws, 1, hdr)
    for r in range(2, S_LAST + 1):
        ws[f"C{r}"] = f'=IF(B{r}="","",{ppos(f"B{r}")})'
        ws[f"D{r}"] = f'=IF(B{r}="","",IFERROR(INDEX(Players!$C$2:$C${P_LAST},MATCH(B{r},{PL},0)),"?"))'
        terms = []
        for j, (_, key) in enumerate(STAT_COLS):
            c = col(STAT_FIRST_COL + j)
            if key == "rec":
                terms.append(f'N({c}{r})*({S["rec"]}+IF(C{r}="TE",{S["tep"]},0))')
            else:
                terms.append(f"N({c}{r})*{S[key]}")
        ws[f"{PTS_COL}{r}"] = f'=IF(B{r}="","",ROUND({"+".join(terms)},2))'
        ws[f"{CHK_COL}{r}"] = (f'=IF(B{r}="","",IF(C{r}="?","Not in Players tab",'
                               f'IF(COUNTIFS($A$2:$A${S_LAST},A{r},$B$2:$B${S_LAST},B{r},$W$2:$W${S_LAST},W{r}&"")>1,"Duplicate row","")))')
    last_stat = col(STAT_FIRST_COL + len(STAT_COLS) - 1)
    style_range(ws, f"A2:W{S_LAST}", font=F_BASE, border=False)
    style_range(ws, f"W2:W{S_LAST}", fill=FILL_CALC, border=False, align=CENTER)
    ws["W1"].comment = Comment("ESPN = written by the live-scoring script (replaced on every refresh). "
                               "Leave blank for your own rows, e.g. a stat correction: those are kept and "
                               "added on top.", "Commissioner")
    style_range(ws, f"A2:B{S_LAST}", font=F_INPUT, fill=FILL_INPUT, border=False)
    style_range(ws, f"{col(STAT_FIRST_COL)}2:{last_stat}{S_LAST}", font=F_INPUT, fill=FILL_INPUT, border=False, align=CENTER)
    style_range(ws, f"C2:D{S_LAST}", fill=FILL_CALC, border=False, align=CENTER)
    style_range(ws, f"{PTS_COL}2:{PTS_COL}{S_LAST}", font=F_BOLD, fill=FILL_CALC, fmt="0.00", border=False, align=CENTER)
    add_list_validation(ws, f"A2:A{S_LAST}", '"1,2,3,4"')
    add_list_validation(ws, f"B2:B{S_LAST}", f"={PL}")
    ws.conditional_formatting.add(f"{CHK_COL}2:{CHK_COL}{S_LAST}", FormulaRule(formula=[f'${CHK_COL}2<>""'], fill=RED_FILL))
    widths(ws, {"A": 7, "B": 24, "C": 6, "D": 9, PTS_COL: 11, CHK_COL: 18,
                **{col(STAT_FIRST_COL + j): 8 for j in range(len(STAT_COLS))}})
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{CHK_COL}{S_LAST}"
    ws[f"{PTS_COL}1"].comment = Comment("Calculated from the Settings scoring table. TE premium applies when the "
                                        "player's position on the Players tab is TE.", "Commissioner")

    # ------------------------------------------------------------ Lineups
    ws = ws_lu
    pt_cols = [col(4 + len(SLOTS) + j) for j in range(len(SLOTS))]
    hdr = ["Round", "Manager", "Alive?"] + SLOTS + [f"{s} Pts" for s in SLOTS] + ["Total", "Yet to Play", "Playing Now", "Check"]
    header(ws, 1, hdr)
    total_col = col(4 + 2 * len(SLOTS))
    ytp_col = col(5 + 2 * len(SLOTS))
    play_col = col(6 + 2 * len(SLOTS))
    check_col = col(7 + 2 * len(SLOTS))
    slot_cols = [col(4 + j) for j in range(len(SLOTS))]
    L_LAST = 1 + N_ROUNDS * N_MGR
    for rd in range(1, N_ROUNDS + 1):
        for k in range(N_MGR):
            r = 2 + (rd - 1) * N_MGR + k
            ws.cell(row=r, column=1, value=rd)
            ws[f"B{r}"] = f"=Managers!$B${M_FIRST + k}"
            ws[f"C{r}"] = f'=IF(B{r}="","",IF(OR(Managers!$D${M_FIRST + k}="",Managers!$D${M_FIRST + k}>=A{r}),"Yes","No"))'
            for sc, pc in zip(slot_cols, pt_cols):
                ws[f"{pc}{r}"] = (f'=IF({sc}{r}="",0,SUMIFS(Stats!${PTS_COL}$2:${PTS_COL}${S_LAST},'
                                  f'Stats!$B$2:$B${S_LAST},{sc}{r},Stats!$A$2:$A${S_LAST},$A{r}))')
            ws[f"{total_col}{r}"] = f'=IF(C{r}="Yes",SUM({pt_cols[0]}{r}:{pt_cols[-1]}{r}),"")'
            srng = f"{slot_cols[0]}{r}:{slot_cols[-1]}{r}"
            for cc, state in ((ytp_col, "pre"), (play_col, "in")):
                ws[f"{cc}{r}"] = (f'=IF(C{r}<>"Yes","",SUMPRODUCT(({srng}<>"")*COUNTIFS({PL},{srng},'
                                  f'Players!$N$2:$N${P_LAST},"{state}")))')
            flags = []
            for s, sc in zip(SLOTS, slot_cols):
                allowed = SLOT_POS[s]
                p = ppos(f"{sc}{r}")
                if len(allowed) == 1:
                    cond = f'{p}<>"{allowed[0]}"'
                else:
                    cond = "AND(" + ",".join(f'{p}<>"{a}"' for a in allowed) + ")"
                flags.append(f'IF(AND({sc}{r}<>"",{cond}),"{s}? ","")')
            rng = f"{slot_cols[0]}{r}:{slot_cols[-1]}{r}"
            flags.append(f'IF(SUMPRODUCT(({rng}<>"")*(COUNTIF({rng},{rng})>1))>0,"Duplicate ","")')
            flags.append(f'IF($A{r}={CUR_ROUND},IF(SUMPRODUCT(({rng}<>"")*(COUNTIFS({PL},{rng},'
                         f'Players!$H$2:$H${P_LAST},$B{r})=0))>0,"Not on roster ",""),"")')
            ws[f"{check_col}{r}"] = (f'=IF(C{r}<>"Yes","",IF(COUNTA({rng})=0,"Empty",'
                                     f'IF(TRIM({"&".join(flags)})="","OK",TRIM({"&".join(flags)}))))')
    style_range(ws, f"A2:{check_col}{L_LAST}", font=F_BASE)
    style_range(ws, f"{slot_cols[0]}2:{slot_cols[-1]}{L_LAST}", font=F_INPUT, fill=FILL_INPUT)
    style_range(ws, f"{pt_cols[0]}2:{pt_cols[-1]}{L_LAST}", fmt="0.00", fill=FILL_CALC, align=CENTER)
    style_range(ws, f"{total_col}2:{total_col}{L_LAST}", font=F_BOLD, fmt="0.00", fill=FILL_SEC, align=CENTER)
    style_range(ws, f"A2:A{L_LAST}", align=CENTER)
    style_range(ws, f"C2:C{L_LAST}", align=CENTER)
    style_range(ws, f"{ytp_col}2:{play_col}{L_LAST}", align=CENTER, fill=FILL_CALC)
    for sc in slot_cols:
        add_list_validation(ws, f"{sc}2:{sc}{L_LAST}", f"={PL}")
    ws.conditional_formatting.add(f"A2:{check_col}{L_LAST}", FormulaRule(formula=['$C2="No"'], fill=GREY_FILL,
                                                                          font=Font(name=FONT, color="A6A6A6")))
    ws.conditional_formatting.add(f"{check_col}2:{check_col}{L_LAST}",
                                  FormulaRule(formula=[f'AND(${check_col}2<>"",${check_col}2<>"OK")'], fill=RED_FILL))
    ws.conditional_formatting.add(f"{check_col}2:{check_col}{L_LAST}",
                                  FormulaRule(formula=[f'${check_col}2="OK"'], fill=GREEN_FILL))
    # thick-ish separators between rounds via alternating band
    ws.conditional_formatting.add(f"A2:B{L_LAST}", FormulaRule(formula=['MOD($A2,2)=0'], fill=FILL_SEC))
    widths(ws, {"A": 7, "B": 18, "C": 7, **{c: 20 for c in slot_cols}, **{c: 8 for c in pt_cols},
                total_col: 9, ytp_col: 9, play_col: 9, check_col: 22})
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:{check_col}{L_LAST}"
    ws["D1"].comment = Comment("Enter each manager's starters for the round. FLEX = RB, WR or TE. "
                               "Leave a slot empty if a manager has no eligible player (scores 0).", "Commissioner")

    # ------------------------------------------------------------ Scoreboard
    ws = ws_sb
    title(ws, "Scoreboard", None)
    ws["A2"] = (f'="Current round: "&INDEX({RNAME_RANGE},{CUR_ROUND})&"   |   Ranked by: "&{BASIS}'
                f'&"   |   Cuts this round: "&INDEX({CUTS_RANGE},{CUR_ROUND})')
    ws["A2"].font = Font(name=FONT, size=11, bold=True, color="C00000")
    hdr = ["Manager", "Team Name", "Status", "Wild Card", "Divisional", "Conference", "Super Bowl",
           "Total", "This Round", "Rank Score", "Alive This Round", "Rank", "Cut Line", "Waiver Priority",
           "Yet to Play", "Playing Now", "Ranked On", "Margin"]
    header(ws, 4, hdr)
    SB_FIRST, SB_END = 5, 4 + N_MGR
    LT = f"Lineups!${total_col}$2:${total_col}${L_LAST}"
    for k in range(N_MGR):
        r = SB_FIRST + k
        m = M_FIRST + k
        ws[f"A{r}"] = f"=Managers!$B${m}"
        ws[f"B{r}"] = f'=IF(Managers!$C${m}="","",Managers!$C${m})'
        ws[f"C{r}"] = f"=Managers!$E${m}"
        for j, c in enumerate("DEFG"):
            ws[f"{c}{r}"] = f'=SUMIFS({LT},Lineups!$B$2:$B${L_LAST},$A{r},Lineups!$A$2:$A${L_LAST},{j + 1})'
        ws[f"H{r}"] = f"=SUM(D{r}:G{r})"
        ws[f"I{r}"] = f"=INDEX(D{r}:G{r},{CUR_ROUND})"
        ws[f"J{r}"] = f'=IF({BASIS}="Weekly",I{r}+H{r}/100000,H{r}+I{r}/100000)'
        ws[f"K{r}"] = f'=IF(A{r}="","",IF(OR(Managers!$D${m}="",Managers!$D${m}>={CUR_ROUND}),"Yes","No"))'
        ws[f"L{r}"] = f'=IF(K{r}<>"Yes","",COUNTIFS($K${SB_FIRST}:$K${SB_END},"Yes",$J${SB_FIRST}:$J${SB_END},">"&J{r})+1)'
        alive_n = f'COUNTIF($K${SB_FIRST}:$K${SB_END},"Yes")'
        cuts = f"INDEX({CUTS_RANGE},{CUR_ROUND})"
        ws[f"M{r}"] = f'=IF(L{r}="","",IF(L{r}>{alive_n}-{cuts},"CUT","Safe"))'
        ws[f"N{r}"] = f'=IF(M{r}<>"Safe","",{alive_n}-{cuts}-L{r}+1)'
        LU = f"Lineups!$B$2:$B${L_LAST},$A{r},Lineups!$A$2:$A${L_LAST},{CUR_ROUND}"
        ws[f"O{r}"] = f'=IF(K{r}<>"Yes","",SUMIFS(Lineups!${ytp_col}$2:${ytp_col}${L_LAST},{LU}))'
        ws[f"P{r}"] = f'=IF(K{r}<>"Yes","",SUMIFS(Lineups!${play_col}$2:${play_col}${L_LAST},{LU}))'
        ws[f"Q{r}"] = f'=IF({BASIS}="Weekly",I{r},H{r})'
        safe_n = f"({alive_n}-{cuts})"
        at = lambda k: f"INDEX($Q${SB_FIRST}:$Q${SB_END},MATCH({k},$L${SB_FIRST}:$L${SB_END},0))"
        ws[f"R{r}"] = (f'=IF(OR(L{r}="",{cuts}=0),"",IFERROR(IF(L{r}<={safe_n},Q{r}-{at(safe_n + "+1")},'
                       f'Q{r}-{at(safe_n)}),""))')
    style_range(ws, f"A{SB_FIRST}:N{SB_END}", font=F_BASE)
    style_range(ws, f"D{SB_FIRST}:J{SB_END}", fmt="0.00", align=CENTER)
    style_range(ws, f"H{SB_FIRST}:H{SB_END}", font=F_BOLD, fmt="0.00", align=CENTER)
    style_range(ws, f"C{SB_FIRST}:C{SB_END}", align=CENTER)
    style_range(ws, f"K{SB_FIRST}:R{SB_END}", align=CENTER)
    style_range(ws, f"Q{SB_FIRST}:R{SB_END}", fmt="+0.00;-0.00;0.00", align=CENTER)
    style_range(ws, f"Q{SB_FIRST}:Q{SB_END}", fmt="0.00", align=CENTER)
    ws.column_dimensions["J"].hidden = True
    ws.conditional_formatting.add(f"A{SB_FIRST}:R{SB_END}", FormulaRule(formula=[f'$M{SB_FIRST}="CUT"'], fill=RED_FILL))
    ws.conditional_formatting.add(f"A{SB_FIRST}:R{SB_END}", FormulaRule(formula=[f'$K{SB_FIRST}="No"'], fill=GREY_FILL,
                                                                          font=Font(name=FONT, color="808080")))
    ws[f"M4"].comment = Comment("CUT = below the cut line for the current round based on Settings. "
                                "Ties are broken by the other score (weekly vs cumulative). "
                                "To make it official, enter the round on the Managers tab.", "Commissioner")
    ws[f"N4"].comment = Comment("Suggested waiver order after cuts: worst surviving team picks first.", "Commissioner")

    # Leaderboard (sorted by rank)
    LB = SB_END + 3
    ws.cell(row=LB - 1, column=1, value="Leaderboard (current round, alive managers)").font = F_BOLD
    header(ws, LB, ["Rank", "Manager", "Total", "This Round", "Cut Line"])
    for k in range(1, N_MGR + 1):
        r = LB + k
        m = f"MATCH({k},$L${SB_FIRST}:$L${SB_END},0)"
        ws[f"A{r}"] = k
        ws[f"B{r}"] = f'=IFERROR(INDEX($A${SB_FIRST}:$A${SB_END},{m}),"")'
        ws[f"C{r}"] = f'=IFERROR(INDEX($H${SB_FIRST}:$H${SB_END},{m}),"")'
        ws[f"D{r}"] = f'=IFERROR(INDEX($I${SB_FIRST}:$I${SB_END},{m}),"")'
        ws[f"E{r}"] = f'=IFERROR(INDEX($M${SB_FIRST}:$M${SB_END},{m}),"")'
    style_range(ws, f"A{LB + 1}:E{LB + N_MGR}", font=F_BASE, align=CENTER)
    style_range(ws, f"C{LB + 1}:D{LB + N_MGR}", fmt="0.00", align=CENTER)
    ws.conditional_formatting.add(f"A{LB + 1}:E{LB + N_MGR}", FormulaRule(formula=[f'$E{LB + 1}="CUT"'], fill=RED_FILL))
    ws.conditional_formatting.add(f"A{LB + 1}:E{LB + N_MGR}", FormulaRule(formula=[f'$B{LB + 1}=""'],
                                                                          font=Font(name=FONT, color="FFFFFF")))
    widths(ws, {"A": 20, "B": 22, "C": 13, "D": 11, "E": 11, "F": 11, "G": 11, "H": 10, "I": 11,
                "K": 10, "L": 7, "M": 9, "N": 10, "O": 9, "P": 9, "Q": 10, "R": 10})
    ws["R4"].comment = Comment("Safe teams: points ahead of the first team below the cut line. "
                               "CUT teams: points behind the last safe team.", "Commissioner")
    ws.freeze_panes = "B5"

    # ------------------------------------------------------------ Games (written by the script)
    ws = ws_gm
    ws["A1"] = "Round"
    ws["C1"] = "Updated"
    ws["D1"].number_format = "ddd h:mm AM/PM"
    for c_ in ("A1", "C1"):
        ws[c_].font = F_BOLD
    ws["F1"] = "Filled in by Playoff Hub > Refresh live scores. Don't edit."
    ws["F1"].font = F_SUB
    header(ws, 3, ["Team", "State", "Detail", "Opponent", "Score", "Game"])
    style_range(ws, "A4:F40", font=F_BASE, fill=FILL_CALC, border=False, align=CENTER)
    ws.conditional_formatting.add("A4:F40", FormulaRule(formula=['$B4="in"'], fill=GREEN_FILL))
    widths(ws, {"A": 8, "B": 8, "C": 22, "D": 10, "E": 9, "F": 14})

    # ------------------------------------------------------------ Live leaderboard
    ws = ws_live
    alive_n = f'COUNTIF(Scoreboard!$K${SB_FIRST}:$K${SB_END},"Yes")'
    cuts = f"INDEX({CUTS_RANGE},{CUR_ROUND})"
    ws["A1"] = f'="LIVE  ·  "&UPPER(INDEX({RNAME_RANGE},{CUR_ROUND}))'
    ws["A1"].font = Font(name=FONT, size=18, bold=True, color="1F3864")
    ws["A2"] = (f'="Ranked on "&LOWER({BASIS})&" points  ·  "&{alive_n}&" alive  ·  bottom "&{cuts}'
                f'&" get cut  ·  Games: "&COUNTIF(Games!$B$4:$B$40,"in")/2&" live, "'
                f'&COUNTIF(Games!$B$4:$B$40,"post")/2&" final, "&COUNTIF(Games!$B$4:$B$40,"pre")/2&" to go"')
    ws["A2"].font = Font(name=FONT, size=10, bold=True, color="595959")
    ws["A3"] = ('=IF(Games!$D$1="","Scores not loaded yet: run Playoff Hub > Refresh live scores",'
                '"Last updated "&TEXT(Games!$D$1,"ddd h:mm AM/PM"))')
    ws["A3"].font = F_SUB
    header(ws, 5, ["Rank", "Manager", "Team Name", "This Round", "Total", "Yet to Play", "Playing Now", "Status", "Margin"])
    for c_ in "ABCDEFGHI":
        ws[f"{c_}5"].font = Font(name=FONT, size=11, bold=True, color="FFFFFF")
    LV_FIRST = 6
    LV_ROWS = N_MGR + 1                    # one extra row for the cut-line banner
    safe_n = f"({alive_n}-{cuts})"
    ws["K5"] = "Safe spots"
    ws["K6"] = f"={safe_n}"
    ws["K5"].font = F_SUB
    ws["K7"] = "Cuts"            # same-sheet copy: Google Sheets conditional formats can't read other tabs
    ws["K8"] = f"={cuts}"
    ws["K7"].font = F_SUB
    SAFE = "$K$6"
    SBA = lambda c_: f"Scoreboard!${c_}${SB_FIRST}:${c_}${SB_END}"
    for i in range(1, LV_ROWS + 1):
        r = LV_FIRST + i - 1
        # J = which rank this row shows (0 = the cut-line banner)
        ws[f"J{r}"] = f"=IF({i}<={SAFE},{i},IF({i}={SAFE}+1,0,{i}-1))"
        m = f"MATCH($J{r},{SBA('L')},0)"
        # Banner row text is split across cells: formula cells don't let text overflow in Google Sheets.
        banner = {"A": "▼  ▼  ▼", "B": "CUT LINE", "C": "Everyone below is out"}
        ws[f"A{r}"] = f'=IF($J{r}=0,IF({cuts}>0,"{banner["A"]}",""),IF($J{r}>{alive_n},"",$J{r}))'
        for c_, src in (("B", "A"), ("C", "B"), ("D", "I"), ("E", "H"), ("F", "O"), ("G", "P"), ("H", "M"), ("I", "R")):
            bt = f'IF({cuts}>0,"{banner[c_]}","")' if c_ in banner else '""'
            ws[f"{c_}{r}"] = (f'=IF($J{r}=0,{bt},IF($J{r}>{alive_n},"",'
                              f'IFERROR(INDEX({SBA(src)},{m}),"")))')
    LV_END = LV_FIRST + LV_ROWS - 1
    style_range(ws, f"A{LV_FIRST}:I{LV_END}", font=Font(name=FONT, size=12), align=CENTER)
    style_range(ws, f"B{LV_FIRST}:C{LV_END}", font=Font(name=FONT, size=12), align=Alignment(horizontal="left", vertical="center"))
    style_range(ws, f"D{LV_FIRST}:E{LV_END}", font=Font(name=FONT, size=12, bold=True), fmt="0.00", align=CENTER)
    style_range(ws, f"I{LV_FIRST}:I{LV_END}", font=Font(name=FONT, size=12), fmt="+0.00;-0.00;0.00", align=CENTER)
    for r in range(LV_FIRST, LV_END + 1):
        ws.row_dimensions[r].height = 24
    ws.column_dimensions["J"].hidden = True
    ws.conditional_formatting.add(f"A{LV_FIRST}:I{LV_END}", FormulaRule(
        formula=[f'AND($J{LV_FIRST}=0,$K$8>0)'], fill=PatternFill("solid", fgColor="C00000"),
        font=Font(name=FONT, bold=True, color="FFFFFF"), stopIfTrue=True))
    ws.conditional_formatting.add(f"A{LV_FIRST}:I{LV_END}", FormulaRule(
        formula=[f'$H{LV_FIRST}="CUT"'], fill=RED_FILL, stopIfTrue=True))
    ws.conditional_formatting.add(f"A{LV_FIRST}:I{LV_END}", FormulaRule(
        formula=[f'$H{LV_FIRST}="Safe"'], fill=PatternFill("solid", fgColor="EAF4E4")))
    ws.conditional_formatting.add(f"G{LV_FIRST}:G{LV_END}", FormulaRule(
        formula=[f'N($G{LV_FIRST})>0'], fill=GREEN_FILL, font=Font(name=FONT, size=12, bold=True, color="006100")))
    ws.cell(row=LV_END + 2, column=1,
            value="Yet to Play / Playing Now = starters whose games haven't kicked off / are in progress. "
                  "Margin = points ahead of the cut line (safe) or behind it (cut). "
                  "Share this tab with File > Share > Publish to web.").font = F_SUB
    widths(ws, {"A": 12, "B": 22, "C": 24, "D": 13, "E": 11, "F": 12, "G": 13, "H": 10, "I": 11, "K": 10})
    ws.column_dimensions["K"].hidden = True
    ws.freeze_panes = "A6"

    # ------------------------------------------------------------ Start Here
    ws = start
    title(ws, "NFL Postseason Survivor League", "12 teams · half PPR · 6-pt passing TDs · TE premium · INT -4 (pick-6 -6) · FG 0.1/yd · managers cut each round")
    lines = [
        ("HOW IT WORKS", None),
        ("", "Draft only players on the 14 NFL playoff teams. After each playoff round the lowest-scoring managers are "
             "eliminated and their players go back into the pool for waivers."),
        ("", "Lineup: QB, RB, RB, WR, WR, TE, FLEX (RB/WR/TE), K, plus 4 bench. 12-round snake draft."),
        ("COLOR KEY", None),
        ("", "Yellow cell, blue text = you type here.   Grey = calculated, don't edit.   "
             "Red row = needs attention / below the cut line.   Green = OK / available."),
        ("BEFORE THE DRAFT (after NFL Week 18)", None),
        ("1.", "Settings: check scoring, set elimination basis (Cumulative or Weekly) and cuts per round."),
        ("2.", "Managers: enter the 12 names, team names and draft slots 1-12."),
        ("3.", "NFL Teams: enter the 14 playoff teams (abbreviation, name, conference, seed)."),
        ("4.", "Players: list every draftable QB/RB/WR/TE/K on those teams (name, position, team abbreviation). "
               "Easiest: 'Playoff Hub > Load player pool' fills this from ESPN (with ESPN IDs), then delete anyone not worth drafting."),
        ("DRAFT", None),
        ("5.", "Draft Board: pick each player from the dropdown. Snake order fills in from draft slots. "
               "The Check column flags duplicates and typos."),
        ("EACH PLAYOFF ROUND", None),
        ("6.", "Settings: set Current round."),
        ("7.", "Lineups: enter each manager's 8 starters for that round. Check column flags wrong positions, "
               "duplicates and players not on the roster."),
        ("8.", "Scoring is live: with the Apps Script installed, choose 'Playoff Hub > Turn ON auto-refresh'. "
               "Every 5 minutes it pulls ESPN box scores for the current round into Stats and game clocks into Games. "
               "The Live tab is the leaderboard with the cut line. Fix a stat by adding your own row on Stats "
               "(Source blank): it is added on top and never overwritten."),
        ("9.", "NFL Teams: enter the round each losing team was eliminated in."),
        ("10.", "Scoreboard: managers marked CUT are below the line. Make it official by typing the round on "
                "the Managers tab (Eliminated After Round). Their players drop to the Waiver Wire automatically."),
        ("11.", "Waiver draft (offline): run it in Waiver Priority order from the Scoreboard (worst survivor first). "
                "For each pick, add a row on Transactions: Type = Add, the player, the manager. To release a player, "
                "Type = Drop. Rosters, the Waiver Wire and lineup checks update right away. The Check column flags "
                "mistakes, and a red roster count on Rosters means someone is over the limit and needs a Drop."),
        ("", "Manual moves: an Add always puts the player on that manager's team, even if another team had him, "
             "so you can also use it to fix mistakes or record trades. The newest row for a player wins, so to undo "
             "a move just delete the row. Players not on the Players tab must be added there first."),
        ("SHARING", None),
        ("", "In Google Sheets: Share > anyone with the link > Viewer. Use Data > Protect sheets and ranges if you "
             "give managers edit access to their own lineup cells."),
        ("", "Live leaderboard for the group chat: File > Share > Publish to web > pick the 'Live' tab > Web page. "
             "That link refreshes on its own as scores update, no Google login needed."),
        ("EXAMPLE ROWS", None),
        ("Players", "Patrick Mahomes | QB | KC"),
        ("NFL Teams", "KC | Kansas City Chiefs | AFC | 1 | (blank until they lose, then 2 if they lose in the Divisional round)"),
        ("Stats", "1 | Josh Allen | (auto) | (auto) | 265 pass yds | 2 pass TD | 1 INT | 0 pick-6 | 41 rush yds | 1 rush TD → 28.70 pts. "
                  "Kicker: FG Made 2, FG Yds 87 (a 42 and a 45) → 8.7 pts from field goals."),
        ("Transactions", "1 | Add | Josh Allen | Manager 4 | waiver claim #1"),
        ("TIEBREAKS", None),
        ("", "Cumulative basis: ties broken by current-round points. Weekly basis: ties broken by cumulative points."),
    ]
    r = 4
    for a, b in lines:
        if b is None:
            r += 1
            ws.cell(row=r, column=1, value=a).font = Font(name=FONT, size=11, bold=True, color="1F3864")
            ws.cell(row=r, column=1).fill = FILL_SEC
            ws.cell(row=r, column=2).fill = FILL_SEC
        else:
            ws.cell(row=r, column=1, value=a).font = F_BOLD
            c = ws.cell(row=r, column=2, value=b)
            c.font = F_BASE
            c.alignment = WRAP
        r += 1
    widths(ws, {"A": 16, "B": 120})

    if demo:
        fill_demo(wb, S, total_col)

    wb.save(path)


# --------------------------------------------------------------------------
def fill_demo(wb, S, total_col):
    """Fake league data used only to verify formulas."""
    random.seed(7)
    teams = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK", "LLL", "MMM", "NNN"]
    ws = wb["NFL Teams"]
    for i, t in enumerate(teams):
        ws.cell(row=4 + i, column=1, value=t)
        ws.cell(row=4 + i, column=2, value=f"Team {t}")
        ws.cell(row=4 + i, column=3, value="AFC" if i < 7 else "NFC")
        ws.cell(row=4 + i, column=4, value=i % 7 + 1)
    # 6 teams lose in R1, 4 in R2 (the 2 byes survive R1)
    for i in [3, 4, 5, 10, 11, 12]:
        ws.cell(row=4 + i, column=5, value=1)
    for i in [1, 2, 8, 9]:
        ws.cell(row=4 + i, column=5, value=2)
    players = []
    for t in teams:
        for pos, n in (("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("K", 1)):
            for j in range(n):
                players.append((f"{t} {pos}{j + 1}", pos, t))
    ws = wb["Players"]
    for i, p in enumerate(players):
        for j, v in enumerate(p):
            ws.cell(row=2 + i, column=1 + j, value=v)
    # draft: first 144 players in a shuffled order
    order = players[:]
    random.shuffle(order)
    ws = wb["Draft Board"]
    for i in range(144):
        ws.cell(row=2 + i, column=6, value=order[i][0])
    # stats rounds 1 & 2
    ws = wb["Stats"]
    r = 2
    STATS = {}
    for rd in (1, 2):
        for name, pos, t in players:
            ti = teams.index(t)
            if rd == 1 and ti in (0, 7):
                continue   # byes
            if rd == 2 and ti in (3, 4, 5, 10, 11, 12):
                continue
            v = {}
            if pos == "QB":
                v["pass_yd"], v["pass_td"] = random.randint(150, 350), random.randint(0, 4)
                v["int"] = random.randint(0, 2)
                v["pick6"] = 1 if v["int"] and random.random() < 0.3 else 0
                v["rush_yd"] = random.randint(0, 40)
            elif pos in ("RB", "WR", "TE"):
                if pos == "RB":
                    v["rush_yd"], v["rush_td"] = random.randint(0, 90), random.randint(0, 1)
                v["rec"], v["rec_yd"], v["rec_td"] = random.randint(0, 8), random.randint(0, 110), random.randint(0, 1)
                v["fum"] = 1 if random.random() < 0.05 else 0
                v["two_pt"] = 1 if random.random() < 0.05 else 0
            else:
                v["xp"], v["xp_miss"] = random.randint(1, 4), random.randint(0, 1)
                made = random.randint(0, 3)
                v["fg_made"], v["fg_yd"] = made, sum(random.randint(20, 58) for _ in range(made))
                v["fg_miss"] = random.randint(0, 1)
            vals = [v.get(k, 0) for _, k in STAT_COLS]
            ws.cell(row=r, column=1, value=rd)
            ws.cell(row=r, column=2, value=name)
            for j, v in enumerate(vals):
                ws.cell(row=r, column=5 + j, value=v)
            STATS[(rd, name)] = (pos, vals)
            r += 1
    wb._demo_stats = STATS
    wb._demo_players = players
    wb._demo_order = order


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "NFL_Postseason_Survivor.xlsx"
    build(out, demo="--demo" in sys.argv)
    print("wrote", out)
