# The game pack / 随身游戏包

> Out-of-tree authority: this guide documents the games shipped with yate.
> The extension API itself lives in [extensions.en.md](extensions.en.md);
> the in-app manual (`:help`) is the authority for editing, not for games.

yate ships a small pack of games written entirely as Lua extensions: they run
inside the editor, draw into a modal character canvas and keep their progress
in `~/.yate/data/games/`. Nothing about them lives on the Python side beyond
the generic extension API, so they are also the best sample of what a Lua
extension can do.

## 1. Quick start

```text
:game                 list the available games
:game snake           start snake
:game player alice    sign your high scores as "alice"
escape                leave the running game
```

The games are modal: while one runs, every key belongs to it (including
`escape`, which closes the canvas). The clock is the canvas' own fixed 15 Hz
tick, so game speed is expressed in ticks and never depends on machine load.

| Game | Command | One-liner |
|---|---|---|
| Snake | `:game snake` | eat, grow, don't bite yourself |
| Pacman | `:game pacman` | clear the maze, dodge the ghosts |
| Sokoban | `:game sokoban` | push every crate onto a goal |
| NetHack | `:game nethack` | descend a procedural dungeon |
| Tetris | `:game tetris` | clear lines before the stack tops out |

## 2. The `:game` command

| Form | Effect |
|---|---|
| `:game` | prints `usage: :game <name> (games: nethack pacman snake sokoban tetris)` |
| `:game <name>` | launches that game; an unknown name prints `unknown game: chess (available: ...)` |
| `:game player` | prints `player: <name>` |
| `:game player <name>` | changes the name stored in `games/profile.json` |

Only one canvas can be open at a time: asking for a game that is already
running prints `<name> is already running` and keeps the current one.

## 3. The games

Every game uses the same frame style (rounded corners, a title, a HUD row and
a help row), Unicode box drawing and block glyphs, and the same three keys:
`p` pause where the game has a clock, `r` restart, `escape` quit.

### 3.1 Snake

```text
╭─ snake ──────────────────────────────────────────────────────╮
│ score 28   best 40 (alice)   length 7                        │
│                                                              │
│                    ██████                                    │
│                         ██                                   │
│              ●●          ██                                  │
│                                                              │
│ help: arrows/hjkl/wasd turn   p pause   r restart             │
╰──────────────────────────────────────────────────────────────╯
```

| Key | Action |
|---|---|
| `←` `→` `↑` `↓`, `hjkl`, `wasd` | turn (a 180-degree reversal is ignored, the turn applies on the next step) |
| `p` | pause / resume |
| `r` | restart (fresh board, score 0) |

Rules: the snake starts three cells long; food is worth 10 points and grows
it by one cell; hitting a wall or its own body ends the run. The step
interval is `max(3, 10 - score // 50)` ticks, so eating makes it faster.
The board is 39 x 20 cells (each drawn two columns wide) on an 80 x 24 canvas.

Saved: top-5 scores, games played, best length.

### 3.2 Pacman

```text
╭───────────────────╮
│███████████████████│
│█········█········█│
│█·██·███·█·███·██·█│
│█●···············●█│
│████·███·█·███·████│
│     █  ▲△▴▵  █     │
│████·███·█·███·████│
│█········◉········█│
│███████████████████│
╰───────────────────╯
```

| Key | Action |
|---|---|
| arrows / `hjkl` / `wasd` | request a direction (buffered until the next tile) |
| `p` | pause / resume |
| `r` | restart at level 1 |

Scoring: dot 10, power pellet 50, ghost 200 / 400 / 800 / 1600 within one
fright, level clear 500. Three lives; a ghost that touches you outside fright
costs one. The ghost AI is deterministic (no randomness at all), so a run is
reproducible. The maze is 39 x 27 tiles with 769 pellets on a 41 x 29 canvas.

Saved: top-5 scores, games played, levels cleared.

### 3.3 Sokoban

```text
╭─ sokoban ───────────╮
│     ██████          │
│     █ ▣  █          │
│     █ ☻ ◎█          │
│     ██████          │
│                     │
│ level 1/6  m0 p0 d0 │
│ u undo  r restart   │
│ n next  p pause     │
╰─────────────────────╯
```

| Key | Action |
|---|---|
| arrows / `hjkl` / `wasd` | walk; push a crate when the tile behind it is free |
| `u` | undo one step (player and the crate it pushed), up to 200 steps |
| `r` | restart the current level |
| `n` | next level (only once the current one is solved) |
| `p` | pause |

Rules: walking into a wall or an immovable crate is not a move. A level is
solved when every goal holds a crate; after the last level the board reports
`all levels cleared` and `r` restarts at level 1. There are **120 levels**:
the first six are handcrafted (five from the public Microban set plus one
teaching level) and the rest are generated by pulling crates away from their
goals, so every generated level is solvable by construction. The level area
is 37 x 17 tiles on a 41 x 22 canvas.

Saved: current level, completed levels, accumulated moves and pushes — so the
next session resumes on the level you reached, with the level itself starting
fresh.

### 3.4 NetHack

```text
╭─ nethack ───────────────────────────────────────────────────────╮
│                                                                │
│                 (72 x 20 dungeon tiles)                        │
│                                                                │
│ depth 3   hp 8/12   gold 30   turn 210                         │
│ move/attack  g grab  enter stairs  space wait  r new  v glyphs │
╰────────────────────────────────────────────────────────────────╯
```

| Key | Action |
|---|---|
| arrows / `hjkl` / `wasd` | move one step; bumping a monster attacks it |
| `space` | wait one turn |
| `g` | grab everything under the player (gold, potion, weapon, food) |
| `enter` | descend, when standing on the stairs (`>`), deeper and stronger |
| `r` | new run, after death (clears the save) |
| `v` | toggle nerd icons / ASCII fallback (remembered in the save) |

The floor is generated from `depth` and a seed, so the same run is
reproducible. Every turn is saved, which means quitting the editor mid-run
resumes exactly where you stopped; dying clears the save. The map is stored
as semantic characters (`#` wall, `.` floor, `,` corridor, `>` stairs), so
switching glyph sets never touches the save.

### 3.5 Tetris

```text
╭─ stats ───────╮ ╭─ tetris ────────────╮ ╭─ next ─────────╮
│ score        0│ │                      │ │                │
│ level        1│ │        ████          │ │      ████      │
│ best      1500│ │        ████          │ │      ████      │
╰───────────────╯ │                      │ ╰────────────────╯
                  ╰──────────────────────╯ ╭─ help ─────────╮
                                           │ left     ←     │
                                           │ drop  space    │
                                           ╰────────────────╯
```

| Key | Action |
|---|---|
| `←` `→`, `↓` | move, soft drop |
| `↑` / `x` | rotate clockwise (with wall kicks) |
| `space` | hard drop |
| `enter` | commit the piece: it falls at full speed and can no longer move |
| `p` / `r` | pause, restart |

Scoring uses the NES table (100 / 300 / 500 / 800 per line count, multiplied
by the level); `level = 1 + lines // 10`. Saved: top-5 scores, games played,
lines cleared.

## 4. Saved data

Everything lives under `~/.yate/data/games/`, one JSON document per game.
Writing is atomic (temporary file plus rename) and a corrupt document simply
reads as "no data yet", with a single notice on the message line — it never
breaks a running game.

| File | Fields |
|---|---|
| `profile.json` | `version`, `player` |
| `snake.json` | `version`, `player`, `high_scores[{score, player, at}]`, `stats{games, best_length}` |
| `pacman.json` | `version`, `player`, `high_scores[...]`, `stats{games, levels}` |
| `tetris.json` | `version`, `player`, `high_scores[...]`, `stats{games, lines}` |
| `sokoban.json` | `version`, `level`, `completed[...]`, `moves`, `pushes` |
| `nethack.json` | `version`, `player`, `glyphs`, `save{depth, turn, seed, hp, max_hp, gold, weapon, rng, player_pos, floor[], monsters[], items[]}` |

`high_scores` keeps at most five entries, best first, each with the score, the
player name and the local time (`at`, ISO-like `YYYY-MM-DDTHH:MM:SS`).

Deleting a file resets that game's progress; deleting `profile.json` falls
back to the OS user name. From an extension the same channel is `api.data`
(see [extensions.en.md](extensions.en.md) §4.15).

## 5. Player name and score authors

The high score board records *who* set the score. The name comes from
`profile.json` when present, otherwise from `USERNAME` / `USER`, otherwise
`player`. Change it with:

```text
:game player alice
```

The name is stored immediately and applies to the next recorded score.

## 6. Glyphs (NetHack)

NetHack separates structure from entities. The dungeon itself -- walls,
floors, corridors and stairs -- always renders as block and shade characters
(`█ · ▒ ▼`) so the map stays readable in any font. Entities use Nerd Font
icons by default: the player, both monster kinds, gold, potions, weapons and
food are Font Awesome 4 codepoints rendered through `utf8.char`. Install any
Nerd Font patched family for the intended look.

Without such a font the entity codepoints render as empty boxes. Press `v` to
switch them to the ASCII fallback (`@ r Z $ ! ) %`); the choice is saved with
the run and restored on the next launch. Every other game uses standard
Unicode box drawing and geometric shapes, which any monospace font provides.

## 7. Writing your own game

A game is one Lua file that returns a module table and calls
`engine.register(name, launch)` in `setup`. Put it in `yate/extensions/` when
you bundle it with yate, or in `~/.yate/extensions/` (or a trusted
`./extensions/`) for local use — the `:game` dispatcher picks it up
automatically because it enumerates the registered `game-*` actions.

`require("game_engine")` gives you the shared half. The engine itself is split
over three requirable modules — `lib/game_engine.lua` (store, scores, player,
dispatch, canvas session), `lib/engine_json.lua` (the codec) and
`lib/engine_layout.lua` (glyph vocabulary and box layout) — but a game only
ever requires `game_engine`, which re-exports the other two:

| Member | Purpose |
|---|---|
| `engine.json.encode(v)` / `.decode(text)` | minimal JSON codec for saved state |
| `engine.store(name)` → `{load, save, clear}` | one document at `games/<name>.json` |
| `engine.scores(name)` → `{entries, best, add}` | top-5 board with player and time |
| `engine.player()` / `engine.set_player(name)` | the name shown as score author |
| `engine.register(name, launch)` | register the `game-<name>` action |
| `engine.open(spec)` → session | the canvas session (single-instance guard, `paint` / `status` / `close`) |
| `engine.box_top` / `box_bottom` / `center` / `pad` / `frame` / `panel` | rounded-box layout |
| `engine.direction(key)` → `dx, dy` | arrows / `hjkl` / `wasd` mapping |
| `engine.rng(seed)` → `{int, pick, state, set}` | deterministic random numbers |
| `engine.utf8_char(code)` | codepoint to UTF-8 glyph, for icon sets |
| `engine.glyph` | the shared glyph vocabulary (`block`, `shade`, `box`, `dot`, …) |

A complete minimal game (a dot you move up and down, with a high score):

```lua
local engine = require("game_engine")

local G = engine.glyph
local mod = {}
local state = nil
local session = nil

local function reset()
  state = { row = 4, score = 0, best = engine.scores("mygame").best() }
end

local function frame(_session)
  local rows = { engine.box_top("mygame", 20) }
  for row = 1, 8 do
    local cell = row == state.row and G.big_dot or G.dot
    rows[#rows + 1] = G.v .. engine.center(cell, 20) .. G.v
  end
  rows[#rows + 1] = engine.box_bottom(20)
  return table.concat(rows, "\n"), { [G.big_dot] = "#e53935", [G.dot] = "#616161" }
end

local function paint()
  if session == nil then
    return
  end
  session.paint()
  session.status("score " .. state.score .. "  best " .. state.best)
end

local function on_key(key)
  local _dx, dy = engine.direction(key)
  if dy == nil then
    return
  end
  state.row = math.max(1, math.min(8, state.row + dy))
  state.score = state.score + 1
  -- `best` is a value the game owns: refresh it so the HUD never shows a
  -- stale record while the current run is ahead of it.
  state.best = math.max(state.best, state.score)
  paint()
end

local function start()
  reset()
  session = engine.open({
    name = "mygame",
    cols = 22,
    rows = 10,
    draw = frame,
    on_key = on_key,
    on_close = function()
      session = nil
    end,
  })
  paint()
end

function mod.setup(_api)
  engine.register("mygame", start)
end

function mod.teardown(_api)
  if session ~= nil then
    session.close()
  end
end

return mod
```

Notes:

- `draw(session)` returns the whole canvas as one newline-joined string plus a
  palette (`glyph -> "#rrggbb"`); the special `"*"` palette entry means "paint
  this glyph for every coloured cell" (solid blocks).
- Session methods are Lua functions stored in the session table, so call them
  with a dot: `session.paint()`, `session.status(text)`, `session.close()`.
- Keep game rules in your file; the engine deliberately knows no rules.
- Expose a `snapshot()` returning plain scalars if you want deterministic
  tests, and a `set_seed(n)` when you use `engine.rng`.
- `engine.json` encodes an empty Lua table as `[]`; JSON `{}` and `[]` both
  decode to an empty Lua table, so an "empty object" does not round-trip.
  Store a key (for example `"version"`) instead of an optional empty object.
- `state.best` is game-owned: the engine's score board only answers "what was
  the best saved score", so refresh your own copy when a run overtakes it.

## 8. Lua lint

The bundled scripts pass a repository lint that you can run yourself:

```text
python tools/lint_lua.py              # every bundled .lua file
python tools/lint_lua.py path/to/x.lua
```

Exit codes: `0` clean, `1` findings, `2` the `lupa` package is missing. The
rules are a real Lua parse through the same bridge the runtime uses, plus:
no tabs, no trailing whitespace, lines of at most 100 characters, LF endings,
one final newline, no `print` / `io.` / `os.execute` / `os.exit` / `dofile` /
`loadfile`, no bare global assignment (only `yate`, `api`, `mod`, `setup`,
`teardown` may be global), and `require` limited to `yate` plus the bundled
`lib/*.lua` modules.
