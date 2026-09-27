"""Full-roster screensaver preview for fancy_sym v5 (NOT product code).

Renders ALL 18 characters with per-pixel half-block coloring (the actual
planned screensaver renderer: 1 pixel = 1 half-row, exact per-pixel color,
same mechanism as bisqwit's original), plus full-terminal snapshots.

Run from any worktree root:

    d:/Programming/yate/.venv/Scripts/python.exe .trae/documents/fancy_sym_preview/make_roster_preview.py

Overwrites roster.svg next to this script.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.text import Text

OUT_DIR = Path(__file__).resolve().parent

BG = "#1e1e2e"
SCR_W, SCR_H = 100, 30

# --- shared palette keys ---
# R red  S skin  H hair  K pupil/blue  M mustache  B overalls/straps
# N shoes  W white  G green  Y yellow  C cream/cap  D dark feet
# O orange  P pink  I cyan  U dome  Z saucer  L light  T tongue

P = {
    "R": "#e52521", "S": "#f8b878", "H": "#6b3e12", "K": "#2b3bd6",
    "M": "#40260b", "B": "#2b53d6", "N": "#8a5a2b", "W": "#ffffff",
    "G": "#7ef07e", "Y": "#f7d51d", "C": "#f8d8a8", "D": "#5a3410",
    "O": "#ffa500", "P": "#ff9dd6", "I": "#00e5e5", "U": "#9ce7ff",
    "Z": "#8890a8", "T": "#ff5a5a", "E": "#9c5a1c", "F": "#6bd46b",
    "L": "#f0f0f0",
    "A": "#2b6bd6",  # armor blue (megaman / ice climber)
    "X": "#58d8e8",  # cyan face & boots (megaman)
    "V": "#202038",  # near-black pupils / treads
    "Q": "#a8a8b8",  # silver (tank / boots)
    "J": "#a86ee8",  # purple (jax fur)
}


def pad(rows: list[str]) -> list[str]:
    w = max(len(r) for r in rows)
    return [r.ljust(w, ".") for r in rows]


# --- 18 characters (original approximations, NOT copies of game assets) ---

MARIO_TOP = [
    "....RRRRRR....",
    "...RRRRRRRRR..",
    "...HHSSSSKS...",
    "..HSSSSSSKSS..",
    "..HHSSSSSSSS..",
    "...SMMMMMMS...",
    "....SSSSSS....",
    "...RRRBBRRR...",
    "..RRRBBBBRRR..",
    "..RRBBBBBBRR..",
    ".SSRBBBBBBRSS.",
    ".SSBBBBBBBBSS.",
    "..BBBBBBBBBB..",
]
MARIO_A = MARIO_TOP + [  # stride
    "..BBBB..BBBB..",
    "..BBB....BBB..",
    "..NNN....NNN..",
    ".NNNN....NNNN.",
]
MARIO_B = MARIO_TOP + [  # passing
    "..BBBBBBBBB...",
    "...BBBBBB.....",
    "...NNNNNN.....",
    "..NNNNNN......",
]
MARIO_C = MARIO_TOP + [  # stride (other leg)
    "..BBBB..BBBB..",
    "...BBB..BBB...",
    "...NNN..NNN...",
    "..NNNN..NNNN..",
]

GOOMBA_TOP = [
    "....EEEEEEEE....",
    "...EEEEEEEEEE...",
    "..EEEEEEEEEEEE..",
    ".EEEEEEEEEEEEEE.",
    ".EWWKEEEEEEKWWE.",
    "EEWWKEEEEEEKWWEE",
    "EEEEEEEEEEEEEEEE",
    ".ECCCCCCCCCCCCE.",
    "..CCCCCCCCCCCC..",
]
GOOMBA_A = GOOMBA_TOP + [
    "..DDD......DDD..",
    ".DDDD......DDDD.",
]
GOOMBA_B = GOOMBA_TOP + [
    "...DDD....DDD...",
    "....DDD..DDD....",
]

MUSHROOM = [
    "....RRRRRR....",
    "..RRWWRRRRWW..",
    ".RWWWWRRRWWWR.",
    ".RWWWWRRRWWWR.",
    "RRWWRRRRRRWWRR",
    "RRRRRRRRRRRRRR",
    ".CCCCCCCCCCCC.",
    ".CCKKCCCCKKCC.",
    ".CCKKCCCCKKCC.",
    "..CCCCCCCCCC..",
    "...CCCCCCCC...",
]
MUSHROOM_B = [
    "....WWWWWW....",
    "..WWRRWWWWRR..",
    ".WRRRRWWWRRRR.",
    ".WRRRRWWWRRRR.",
    "WWRRWWWWWWRRWW",
    "WWWWWWWWWWWWWW",
    ".CCCCCCCCCCCC.",
    ".CCKKCCCCKKCC.",
    ".CCKKCCCCKKCC.",
    "..CCCCCCCCCC..",
    "...CCCCCCCC...",
]

STAR_A = [
    "......YY......",
    ".....YYYY.....",
    ".....YYYY.....",
    "YYYYYYYYYYYYYY",
    "YYYYYYYYYYYYYY",
    ".YYYYYYYYYYYY.",
    "..YYKYYYYKYY..",
    "...YYYYYYYY...",
    "..YYYYYYYYYY..",
    "..YYY....YYY..",
    ".YYY......YYY.",
    "YYY........YYY",
]
STAR_B = STAR_A[:6] + [
    "..YYYYYYYYYY..",
    "...YYYYYYYY...",
    "..YYYYYYYYYY..",
    "..YYY....YYY..",
    ".YYY......YYY.",
    "YYY........YYY",
]

PAC_A = [
    "....YYYYYY....",
    "..YYYYYYYYYY..",
    ".YYYYYYYYYYYY.",
    "YYYYYYYYY.....",
    "YYYYYYYY......",
    "YYYYYY........",
    "YYYYYYYY......",
    "YYYYYYYYY.....",
    ".YYYYYYYYYYYY.",
    "..YYYYYYYYYY..",
    "....YYYYYY....",
]
PAC_B = [
    "....YYYYYY....",
    "..YYYYYYYYYY..",
    ".YYYYYYYYYYYY.",
    "YYYYYYYYYYYYY.",
    "YYYYYYYYYYYY..",
    "YYYYYYYYY.....",
    "YYYYYYYYYYYY..",
    "YYYYYYYYYYYYY.",
    ".YYYYYYYYYYYY.",
    "..YYYYYYYYYY..",
    "....YYYYYY....",
]

_GHOST = [
    "....CCCCCCCC....",
    "..CCCCCCCCCCCC..",
    ".CCWWKCCCCKWWCC.",
    ".CCWWKCCCCKWWCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CC.CC.CC.CC.CC.",
    ".CC.CC.CC.CC.CC.",
]
_GHOST_R = [
    "....CCCCCCCC....",
    "..CCCCCCCCCCCC..",
    ".CCKWWCCCCKWWCC.",
    ".CCKWWCCCCKWWCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CCCCCCCCCCCCCC.",
    ".CC.CC.CC.CC.CC.",
    "..C.CC.CC.CC.CC.",
]


def ghost(color: str, rows: list[str]) -> tuple[list[str], dict[str, str]]:
    pal = {"C": color, "W": P["W"], "K": P["K"]}
    return rows, pal


DUCK_A = [
    "......LLLL........",
    ".....LLLLLL.......",
    ".....LKLLLL.OOO...",
    ".....LLLLLL.O.....",
    ".....LLLLLL.......",
    "LL...LLLLL........",
    ".LLLLLLLLLLLLL....",
    "..LLLLLLLLLLLLL...",
    "...LLLLLLLLLL.....",
    "....LLLLLL........",
    ".....OO..OO.......",
    ".....OO..OO.......",
]
DUCK_B = [
    "......LLLL........",
    ".....LLLLLL.......",
    ".....LKLLLL.OOO...",
    ".....LLLLLL.O.....",
    ".....LLLLLL.......",
    "LL...LLLLL........",
    ".LLLLLLLLLLLLL....",
    "..LLLLLLLLLLLLL...",
    "...LLLLLLLLLL.....",
    "....LLLLLL........",
    "....OOO...OOO.....",
    "....OO....OO......",
]

SNAKE_A = [
    "....GGGGG...............",
    "...GGGGGGG..............",
    "..GG.....GG...GGGGG.....",
    ".GG.......GG.GGGGGGG....",
    "GG.........GGG.....GG...",
    "............G.......GGG.",
    "......................GT.",
]
SNAKE_B = [
    "....GGGGG...............",
    "...GGGGGGG..............",
    "..GG.....GG....GGGGG....",
    ".GG.......GG..GGGGGGG...",
    "GG.........GG.G......GG.",
    ".............GG.......GT",
]

FROG_A = [
    "...FF........FF...",
    "..FFWK......KWFF..",
    "..FFFFFFFFFFFFFF..",
    ".FFFFFFFFFFFFFFFF.",
    "FFFFFFFFFFFFFFFFFF",
    "FFFFFFFFFFFFFFFFFF",
    ".FFFCFFFFFFFFFFC..",
    "..FFFFFFFFFFFFFF..",
    ".FFF.FF....FF.FFF.",
    "FFF...F....F...FFF",
]
FROG_B = [
    "...FF........FF...",
    "..FFWK......KWFF..",
    "..FFFFFFFFFFFFFF..",
    ".FFFFFFFFFFFFFFFF.",
    "FFFFFFFFFFFFFFFFFF",
    "FFFFFFFFFFFFFFFFFF",
    ".FFFFFFFFFFFFFFFF.",
    "..FFFFFFFFFFFFFF..",
    "...FFF......FFF...",
    "...FF........FF...",
]

COIN_1 = [
    "..YYYYYY..",
    ".YYYYYYYY.",
    ".YYYWWYYY.",
    ".YYYWWYYY.",
    ".YYYWWYYY.",
    ".YYYWWYYY.",
    ".YYYYYYYY.",
    "..YYYYYY..",
]
COIN_2 = [
    "...YYYY...",
    "...YYYY...",
    "...YWYY...",
    "...YWYY...",
    "...YWYY...",
    "...YWYY...",
    "...YYYY...",
    "...YYYY...",
]
COIN_3 = ["....YY...."] * 8

FIREFLOWER_A = [
    "...RRRRRR...",
    "..RRYYYYRR..",
    "..RRYYYYRR..",
    "...RRRRRR...",
    ".....GG.....",
    ".G..GGG..G..",
    ".GG.GGG.GG..",
    "..GGGGGGG...",
    "...GGGGG....",
    "....GGG.....",
]
FIREFLOWER_B = [r.replace("R", "O") for r in FIREFLOWER_A]

GAL_TOP = [
    ".......W.......",
    "......WWW......",
    "......WRW......",
    ".....WRRRW.....",
    "..W..WRRRW..W..",
    ".WWW.WRRRW.WWW.",
    ".WWWWWRRRWWWWW.",
    ".WBWWWWRWWWWBW.",
    "..WWWWWWWWWWW..",
]
GALAGA_A = GAL_TOP + ["...W..W.W..W..."]
GALAGA_B = GAL_TOP + ["....WWWWWWW...."]

MEGAMAN_TOP = [
    "....AAAAAA....",
    "...AAAAAAAA...",
    "..AAAAAAAAAA..",
    "..AXXXXXXXA...",
    "..AXVXXVXXA...",
    "..AXXXXXXXA...",
    "...AAAAAAA....",
    "..AAAAAAAAAA..",
    ".AABBBBBBBBAA.",
    ".AABBBBBBBBAA.",
    "..BBBBBBBBBB..",
]
MEGAMAN_A = MEGAMAN_TOP + [
    "..BBB....BBB..",
    "..XXX....XXX..",
    ".XXXX....XXXX.",
]
MEGAMAN_B = MEGAMAN_TOP + [
    "..BBBBBBBBB...",
    ".BBB....BBB...",
    ".XXX.....XXX..",
    "XXXX.....XXXX.",
]

BOMBERMAN_A = [
    "......P.......",
    ".....PPP......",
    "...WWWWWWWW...",
    "..WWWWWWWWWW..",
    "..WVWWWWWWVW..",
    "..WWWWWWWWWW..",
    "...WWWWWWWW...",
    "..BBBBBBBBBB..",
    ".WWBBBBBBBBWW.",
    ".WWBBBBBBBBWW.",
    "..BBBBBBBBBB..",
    "..RRRRRRRRRR..",
    "...BB....BB...",
    "..PPP....PPP..",
]
BOMBERMAN_B = BOMBERMAN_A[:12] + [
    "...BB..BB.....",
    "..PPP...PPP...",
]

SAMUS_TOP = [
    "...OOOOOO.....",
    "..OOGGGGOO....",
    "..OOGGGGOO....",
    "..OOOOOOOO....",
    "...RRRRRR.....",
    ".OORRRRRROO...",
    ".OORROORROO...",
    "..OOOOOOOO....",
]
SAMUS_A = SAMUS_TOP + [
    "..OOO..OOO....",
    "..RRR..RRR....",
    "..RRR..RRR....",
    ".RRR....RRR...",
]
SAMUS_B = SAMUS_TOP + [
    "..OOO..OOO....",
    ".RRR....RRR...",
    ".RR......RR...",
    ".RR......RR...",
]

LINK_TOP = [
    "....GGG.....",
    "...GGGGG....",
    "...SSSSS....",
    "...SVSVS....",
    "...SSSSS....",
    "..GGGGGGG...",
    ".SGGGGGGGS..",
    ".SGGGGGGGS..",
    "..GGGGGGG...",
    "..GGGGGGG...",
]
LINK_A = LINK_TOP + [
    "...SS.SS....",
    "...NN.NN....",
]
LINK_B = LINK_TOP + [
    "..SS...SS...",
    ".NN.....NN..",
]

ICE_TOP = [
    "...AAAAAA...",
    "..AAAAAAAA..",
    "..ASSSSSSA..",
    "..ASVSSVSA..",
    "..ASSSSSSA..",
    "...AAAAAA...",
    "..AAAAAAA...",
    ".AAAAAAAAA..",
    ".AAAAAAAAA..",
]
ICE_A = ICE_TOP + [
    "..AAAAAA....",
    "..QQ..QQ....",
]
ICE_B = ICE_TOP + [
    "..AAAA......",
    "..QQ..QQ....",
]

DIG_TOP = [
    "...WWWWWW...",
    "..WWWWWWWW..",
    "..WBBWWBBW..",
    "..WWWWWWWW..",
    "..RRRRRRRR..",
    ".WRRRRRRRRW.",
    ".WRRRRRRRRW.",
    "..RRRRRRRR..",
    "..WWWWWWWW..",
]
DIG_A = DIG_TOP + [
    "...WW..WW...",
    "...BB..BB...",
    "..BBB..BBB..",
]
DIG_B = DIG_TOP + [
    "..WW....WW..",
    "..BB....BB..",
    ".BBB....BBB.",
]

SLIME_A = [
    ".....BB.....",
    "....BBBB....",
    "...BBBBBB...",
    "..BBBBBBBB..",
    "..BWVBBVWB..",
    "..BBBBBBBB..",
    ".BBBBBBBBBB.",
    ".BBBBBBBBBB.",
    ".BBBBBBBBBB.",
    "..BBBBBBBB..",
]
SLIME_B = [
    "............",
    "............",
    "....BBBB....",
    "...BBBBBB...",
    "..BWVBBVWB..",
    ".BBBBBBBBBB.",
    "BBBBBBBBBBBB",
    "BBBBBBBBBBBB",
    "BBBBBBBBBBBB",
    ".BBBBBBBBBB.",
]

# --- The Amazing Digital Circus (original approximations) ---

# pomni: harlequin hat red|blue + bells, pale face, red & blue pupils
POMNI_A = [
    "...YR......BY..",
    "..RRRR....BBBB.",
    "..RRRRR..BBBBB.",
    "...RRRRBBBBBB..",
    "...WWWWWWWWWW..",
    "..WWWWWWWWWWWW.",
    "..WWRWWWWWWBW..",
    "..WWWWWWWWWWWW.",
    "...WWWWWWWWWW..",
    "....WWWWWWWW...",
    "...RRRBBBBRR...",
    "..RRRBBBBBBRR..",
    "..RRRBBBBBBRR..",
    "..RR..BB...BB..",
    "..RR.......BB..",
    "..NN.......NN..",
]
POMNI_B = [  # blink, bells swing
    "..Y.RR....BB.Y.",
    "..RRRR....BBBB.",
    "..RRRRR..BBBBB.",
    "...RRRRBBBBBB..",
    "...WWWWWWWWWW..",
    "..WWWWWWWWWWWW.",
    "..WWWWWWWWWWWW.",
    "..WWWWWWWWWWWW.",
    "...WWWWWWWWWW..",
    "....WWWWWWWW...",
    "...RRRBBBBRR...",
    "..RRRBBBBBBRR..",
    "..RRRBBBBBBRR..",
    "..RR..BB...BB..",
    "..RR.......BB..",
    "..NN.......NN..",
]

# jax: tall purple rabbit, pink inner ears, yellow slit eyes, big front teeth
JAX_A = [
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJJJJJ..JJJJJJ.",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JYYYYYYYYYYJ..",
    "..JYVYYYYYYVYJ..",
    "..JJJJJJJJJJJJ..",
    "...JJJJJJJJJJ...",
    "...JWWWWWWWWJ...",
    "...JWJWWWWJWJ...",
    "...JWWWWWWWWJ...",
    "...JJJJJJJJJJ...",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JJJJJ..JJJJJ..",
    "..JJJJ...JJJJ...",
    "..JJJ......JJJ..",
    "..JJ........JJ..",
]
JAX_B = [  # blink, ears lean
    ".JJPPJJ...JJPPJJ",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJPPJJ..JJPPJJ.",
    ".JJJJJJ..JJJJJJ.",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "...JJJJJJJJJJ...",
    "...JWWWWWWWWJ...",
    "...JWJWWWWJWJ...",
    "...JWWWWWWWWJ...",
    "...JJJJJJJJJJ...",
    "..JJJJJJJJJJJJ..",
    "..JJJJJJJJJJJJ..",
    "..JJJJJ..JJJJJ..",
    "..JJJJ...JJJJ...",
    "..JJJ......JJJ..",
    "..JJ........JJ..",
]

# ragatha: orange yarn hair, pale face, button eyes, rosy cheeks, blue dress
RAGATHA_A = [
    "....OOOOOO....",
    "..OOOOOOOOOO..",
    ".OOOOOOOOOOOO.",
    ".OOOLLLLLLLLOO",
    ".OOOLLVLLVLLOO",
    ".OOOLLLLLLLLOO",
    ".OOLTLTTTTLLOO",
    ".OOOLLLLLLLLOO",
    "..OOLLLLLLLOO.",
    "...OOLLLLOOO..",
    "....BBBBBB....",
    "...BBBBBBBB...",
    "..BWBBBBWBBB..",
    "..BBBBBBBBBB..",
    "..BBBBBBBBBB..",
    "...BB....BB...",
    "...LL....LL...",
]
RAGATHA_B = [  # blink
    "....OOOOOO....",
    "..OOOOOOOOOO..",
    ".OOOOOOOOOOOO.",
    ".OOOLLLLLLLLOO",
    ".OOOLLLLLLLLOO",
    ".OOOLLLLLLLLOO",
    ".OOLTLTTTTLLOO",
    ".OOOLLLLLLLLOO",
    "..OOLLLLLLLOO.",
    "...OOLLLLOOO..",
    "....BBBBBB....",
    "...BBBBBBBB...",
    "..BWBBBBWBBB..",
    "..BBBBBBBBBB..",
    "..BBBBBBBBBB..",
    "...BB....BB...",
    "...LL....LL...",
]

# caine: top hat, floating eyeballs, chattering teeth, red tailcoat + gloves
CAINE_A = [
    ".....KKKKKK.....",
    ".....KKKKKK.....",
    "..KKKKKKKKKKKK..",
    "....PPPPPPPP....",
    "...WWKWWWWKWW...",
    "...WWWWWWWWWW...",
    "...WWVWWVWWVW...",
    "...WWWWWWWWWW...",
    "..KKKKKKKKKKKK..",
    "...RRRRRRRRRR...",
    "..RRRRRRRRRRRR..",
    ".LLRRRRRRRRRRLL.",
    "..RRRRRRRRRRRR..",
    "..RRR......RRR..",
    "..RR........RR..",
    "..KK........KK..",
]
CAINE_B = [  # pupils drift, teeth chatter
    ".....KKKKKK.....",
    ".....KKKKKK.....",
    "..KKKKKKKKKKKK..",
    "....PPPPPPPP....",
    "...WKWWWWWWKW...",
    "...WWWWWWWWWW...",
    "...WWVWWVWWVW...",
    "...WWWWWWWWWW...",
    "..KKKKKKKKKKKK..",
    "...RRRRRRRRRR...",
    "..RRRRRRRRRRRR..",
    ".LLRRRRRRRRRRLL.",
    "..RRRRRRRRRRRR..",
    "..RRR......RRR..",
    "..RR........RR..",
    "..KK........KK..",
]

# gangle: theater mask (comedy smile / tragedy frown) + red ribbon body
GANGLE_A = [
    "..WWWWWWWWWW..",
    ".WWWWWWWWWWWW.",
    ".WWVWWWWWWVWW.",
    ".WWWWWWWWWWWW.",
    ".WWWWWWWWWWWW.",
    ".WWWVVVVVVWWW.",
    "..WWWWWWWWWW..",
    "...TTTTTTTT...",
    "..TTTTTTTTTT..",
    ".TTTTTTTTTTTT.",
    ".TT.TTTTTT.TT.",
    ".T..TTTTTT..T.",
    "....TTTTTT....",
]
GANGLE_B = [  # tragedy frown
    "..WWWWWWWWWW..",
    ".WWWWWWWWWWWW.",
    ".WWWWWWWWWWWW.",
    ".WWVWWWWWWVWW.",
    ".WWWWWWWWWWWW.",
    ".WWWVVVVVVWWW.",
    "..WWWWWWWWWW..",
    "...TTTTTTTT...",
    "..TTTTTTTTTT..",
    ".TTTTTTTTTTTT.",
    ".TT.TTTTTT.TT.",
    ".T..TTTTTT..T.",
    "....TTTTTT....",
]

#: name -> (frames, palette override or shared P, zoom)
ROSTER: list[tuple[str, list[list[str]], dict[str, str] | None, int]] = [
    ("mario", [MARIO_A, MARIO_B, MARIO_C], None, 9),
    ("goomba", [pad(GOOMBA_A), pad(GOOMBA_B)], None, 9),
    ("mushroom", [MUSHROOM, MUSHROOM_B], None, 10),
    ("star", [STAR_A, STAR_B], None, 10),
    ("coin", [COIN_1, COIN_2, COIN_3, COIN_2], None, 12),
    ("fire flower", [FIREFLOWER_A, FIREFLOWER_B], None, 11),
    ("pacman", [PAC_A, PAC_B], None, 10),
    ("ghost blinky", [pad(_GHOST), pad(_GHOST_R)], ghost("#ff2b2b", [])[1] | {}, 10),
    ("ghost pinky", [pad(_GHOST), pad(_GHOST_R)], ghost("#ff9dd6", [])[1], 10),
    ("ghost inky", [pad(_GHOST), pad(_GHOST_R)], ghost("#00e5e5", [])[1], 10),
    ("ghost clyde", [pad(_GHOST), pad(_GHOST_R)], ghost("#ffa500", [])[1], 10),
    ("galaga ship", [GALAGA_A, GALAGA_B], None, 10),
    ("megaman", [MEGAMAN_A, MEGAMAN_B], None, 9),
    ("bomberman", [BOMBERMAN_A, BOMBERMAN_B], None, 9),
    ("samus", [SAMUS_A, SAMUS_B], None, 9),
    ("link", [LINK_A, LINK_B], None, 11),
    ("ice climber", [ICE_A, ICE_B], None, 11),
    ("dig dug", [DIG_A, DIG_B], None, 11),
    ("pomni", [pad(POMNI_A), pad(POMNI_B)], None, 9),
    ("jax", [pad(JAX_A), pad(JAX_B)], None, 9),
    ("ragatha", [pad(RAGATHA_A), pad(RAGATHA_B)], None, 10),
    ("caine", [pad(CAINE_A), pad(CAINE_B)], None, 9),
    ("gangle", [pad(GANGLE_A), pad(GANGLE_B)], None, 11),
    ("duck", [DUCK_A, DUCK_B], None, 10),
    ("snake", [SNAKE_A, SNAKE_B], None, 9),
    ("frog", [FROG_A, FROG_B], None, 10),
    ("slime", [SLIME_A, SLIME_B], None, 11),
]


def sprite_rects(rows: list[str], pal: dict[str, str], ox: float, oy: float,
                 z: int) -> list[str]:
    parts: list[str] = []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            fill = pal.get(ch)
            if fill is None:  # transparent
                fill = "#2a2a3c" if (x + y) % 2 == 0 else "#222232"
            parts.append(
                f'<rect x="{ox + x * z:g}" y="{oy + y * z:g}" '
                f'width="{z}" height="{z}" fill="{fill}"/>'
            )
    return parts


def label(x: float, y: float, s: str, size: int = 22,
          fill: str = "#a6adc8") -> str:
    return (f'<text x="{x:g}" y="{y:g}" fill="{fill}" font-family="monospace" '
            f'font-size="{size}">{s}</text>')


def halfblock_lines(rows: list[str], pal: dict[str, str], tr: int, tc: int
                    ) -> list[Text]:
    """Sprite pixel rows -> Text lines via half blocks (planned renderer)."""
    h = len(rows)
    w = max(len(r) for r in rows)
    out: list[Text] = []
    for r in range(SCR_H):
        t = Text()
        pr = (r - tr) * 2  # pixel row covered by upper half of text row r
        placed = False
        for c in range(SCR_W):
            px = c - tc
            up = rows[pr][px] if 0 <= pr < h and 0 <= px < w else "."
            low = (rows[pr + 1][px]
                   if 0 <= pr + 1 < h and 0 <= px < w else ".")
            fu = pal.get(up)
            fl = pal.get(low)
            if fu and fl:
                if fu == fl:
                    t.append("█", style=fu)
                else:
                    t.append("▀", style=f"{fu} on {fl}")
            elif fu:
                t.append("▀", style=fu)
            elif fl:
                t.append("▄", style=fl)
            else:
                t.append(" ", style=f"on {BG}")
            placed = True
        if not placed:
            t.append(" " * SCR_W, style=f"on {BG}")
        out.append(t)
    return out


def main() -> None:
    sections: list[str] = []
    y = 40.0
    sections.append(label(24, y, "fancy_sym v6 — screensaver roster, all 27 "
                          "characters (per-pixel half-block rendering)",
                          28, "#cdd6f4"))
    y += 56

    for name, frames, pal, z in ROSTER:
        p = pal if pal is not None else P
        widths = [max(len(r) for r in f) for f in frames]
        cell_w = sum(w * z + 30 for w in widths)
        sections.append(label(24, y, f"{name}  ({widths[0]}x{len(frames[0])} px,"
                              f" {len(frames)} frame{'s' if len(frames) > 1 else ''})",
                              22, "#cdd6f4"))
        y += 30
        x = 40.0
        for fid, frame in enumerate(frames):
            sections.append(label(x, y + 16, f"f{fid + 1}", 18))
            sections.extend(sprite_rects(frame, p, x, y + 24, z))
            x += widths[fid] * z + 46
        y += max(len(f) for f in frames) * z + 44

    # one actual-size full-terminal snapshot (mario, half-block renderer)
    mario_pal = P
    console = Console(width=SCR_W, height=SCR_H, record=True)
    console.print(Text("screensaver — mario  (actual size, one sprite at a "
                       "time; any key exits)", style="#585b70"))
    for line in halfblock_lines(MARIO_A, mario_pal, 8, 30)[1:]:
        console.print(line)
    svg_doc = console.export_svg()
    import re

    style = re.search(r"<style>.*?</style>", svg_doc, re.S)
    body = re.search(r'<g id="[^"]+">.*?</g>', svg_doc, re.S)
    if style and body:
        sections.append(label(24, y, "full-terminal snapshot (actual size):",
                              22, "#cdd6f4"))
        y += 34
        sections.append(
            f'<g transform="translate(24,{y:g}) scale(0.62)">'
            + style.group(0) + body.group(0) + "</g>"
        )
        y += SCR_H * 24.4 * 0.62 + 40

    width, height = 760, y
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height:g}" viewBox="0 0 {width} {height:g}">\n'
        f'<rect width="100%" height="100%" fill="{BG}"/>\n'
        + "\n".join(sections)
        + "\n</svg>\n"
    )
    out = OUT_DIR / "roster.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({width}x{height:g}), characters={len(ROSTER)}")


if __name__ == "__main__":
    main()
