--[[
yate bundled extension: snake (snake.lua)

A classic snake game drawn on a yate extension canvas: a 39 x 20 board of
two-column cells inside a rounded 80 x 24 frame, with a HUD row (score /
best / length) under the title, a help separator above the bottom border
and overlay text ("paused", "game over") in the middle of the board.

Start it with ``:game snake``.

Controls:
  arrows / hjkl / wasd   turn (180-degree reversals and same-direction
                         repeats are ignored; the turn applies on the
                         next step)
  p                      pause / resume
  r                      restart at any moment (fresh board, score 0)
  escape                 exit the canvas (consumed by the canvas itself)

Rules: the snake starts 3 cells long heading right and steps once every
``step_ticks`` ticks where ``step_ticks = max(3, 10 - score // 50)``, so
the game speeds up as the score grows.  Eating food scores 10 points and
grows the snake; hitting a wall or the snake's own body ends the run and
records the score once on the high score board plus per-game stats.

Persistence goes through the shared engine: ``games/snake.json`` keeps the
top-5 high scores (with player names) and the stats block.

Entry form: module-table style -- this file returns ``mod`` and yate calls
``mod.setup(api)`` at load and ``mod.teardown(api)`` on unload.
]]

local engine = require("game_engine")

-- Canvas geometry: 80 x 24, inner width 78, board 39 x 20 cells.
local COLS, ROWS = 80, 24
local INNER = 78
local BOARD_W, BOARD_H = 39, 20

-- Cell glyphs (single width, doubled on output): body, head, food.
local BODY = engine.glyph.block .. engine.glyph.block
local HEAD = engine.glyph.shade .. engine.glyph.shade
local FOOD = engine.glyph.big_dot .. engine.glyph.big_dot
local EMPTY = "  "

-- Palette handed to the canvas: glyph -> color.
local PALETTE = {
  [engine.glyph.block] = "#4caf50",
  [engine.glyph.shade] = "#c8e6c9",
  [engine.glyph.big_dot] = "#e53935",
}

-- Speed table: one step per step_ticks ticks, floored at 3.
local BASE_TICKS = 10
local MIN_TICKS = 3
local SPEED_STEP = 50 -- score units per one-tick speedup

-- Bound on random food placement attempts before falling back to a scan.
local FOOD_TRIES = 200

-- Help separator text between the board and the bottom border.
local HELP_TEXT = "help: arrows/hjkl/wasd turn  p pause  r restart"

-- Game state (rebuilt by reset_game()); nil until the first start.
local state = nil

-- The open canvas session; nil while no canvas is open.
local session = nil

-- Deterministic rng for food placement and its pinned seed (tests inject).
local rng = nil
local seed = nil

-- Optional injected food source: fn() -> {x=,y=}; nil restores random.
local food_source = nil

-- Shared persistence handles (one document, one score board).
local store = engine.store("snake")
local board = engine.scores("snake")

local mod = {}

-- --------------------------------------------------------------------- state

-- True when (x, y) is on any snake segment.
local function on_snake(x, y)
  for _, part in ipairs(state.snake) do
    if part.x == x and part.y == y then
      return true
    end
  end
  return false
end

-- Pick the next food cell: the injected source when it returns a free
-- cell, otherwise rng.int until a free cell shows up (bounded), then the
-- first free cell of a board scan (never loops forever on a full board).
local function spawn_food()
  if food_source ~= nil then
    local ok, spot = pcall(food_source)
    if ok and type(spot) == "table" and type(spot.x) == "number"
      and type(spot.y) == "number" and spot.x >= 1 and spot.x <= BOARD_W
      and spot.y >= 1 and spot.y <= BOARD_H and not on_snake(spot.x, spot.y) then
      state.food = { x = spot.x, y = spot.y }
      return
    end
  end
  for _ = 1, FOOD_TRIES do
    local x = rng.int(BOARD_W)
    local y = rng.int(BOARD_H)
    if not on_snake(x, y) then
      state.food = { x = x, y = y }
      return
    end
  end
  for y = 1, BOARD_H do
    for x = 1, BOARD_W do
      if not on_snake(x, y) then
        state.food = { x = x, y = y }
        return
      end
    end
  end
  state.food = nil -- board completely full: nothing left to place
end

-- One step costs step_ticks ticks; the snake speeds up with the score.
local function step_ticks()
  local slower = math.floor(state.score / SPEED_STEP)
  return math.max(MIN_TICKS, BASE_TICKS - slower)
end

-- Fresh game: length 3 heading right at the start row, score 0, full speed.
local function reset_game()
  rng = engine.rng(seed)
  state = {
    snake = { { x = 3, y = 10 }, { x = 2, y = 10 }, { x = 1, y = 10 } },
    dir = { x = 1, y = 0 },
    pending = nil,
    food = nil,
    score = 0,
    ticks = 0,
    alive = true,
    paused = false,
    scored = false,
  }
  state.step_ticks = step_ticks()
  spawn_food()
end

-- Best score + its player from games/snake.json (defaults are silent).
local function load_best()
  state.best = 0
  state.best_player = engine.player()
  local document = store.load()
  if type(document) ~= "table" or type(document.high_scores) ~= "table" then
    return
  end
  local top = document.high_scores[1]
  if type(top) == "table" and type(top.score) == "number" then
    state.best = top.score
    state.best_player = tostring(top.player or state.best_player)
  end
end

-- ----------------------------------------------------------------- scoring

-- Record the finished run once: the score board entry plus stats.
local function record_run()
  if state.scored then
    return
  end
  state.scored = true
  board.add(state.score)
  local document = store.load() or {}
  local stats = document.stats
  if type(stats) ~= "table" then
    stats = {}
  end
  stats.games = (stats.games or 0) + 1
  stats.best_length = math.max(stats.best_length or 0, #state.snake)
  document.version = engine.VERSION
  document.stats = stats
  store.save(document)
end

-- Hit a wall or the snake's own body: freeze the run and record it.
local function die()
  state.alive = false
  record_run()
end

-- ------------------------------------------------------------------ stepping

-- Advance one cell; eating grows the snake and respawns the food.
local function step()
  if state.pending ~= nil then
    state.dir = state.pending
    state.pending = nil
  end
  local head = state.snake[1]
  local nx = head.x + state.dir.x
  local ny = head.y + state.dir.y
  if nx < 1 or nx > BOARD_W or ny < 1 or ny > BOARD_H then
    die()
    return
  end
  local eating = state.food ~= nil and nx == state.food.x and ny == state.food.y
  -- When not growing the tail cell frees up this step, so it is safe.
  local limit = eating and #state.snake or (#state.snake - 1)
  for index = 1, limit do
    local part = state.snake[index]
    if part.x == nx and part.y == ny then
      die()
      return
    end
  end
  table.insert(state.snake, 1, { x = nx, y = ny })
  if eating then
    state.score = state.score + 10
    -- The HUD best is "the best seen so far": a run that overtakes the saved
    -- record shows its own score immediately instead of a stale number.
    if state.score > state.best then
      state.best = state.score
    end
    state.step_ticks = step_ticks()
    spawn_food()
  else
    table.remove(state.snake)
  end
end

-- ------------------------------------------------------------------ rendering

-- Top border: rounded frame, title, then the star icon after " · ".
-- Built by hand (not box_top) so the icon fits without byte splicing; the
-- fill is measured in display columns (the star is multi-byte).
local function top_line()
  local label = " snake · " .. engine.glyph.star .. " "
  -- borders (2) + the leading ─ glyph (1) + the label
  local fill = COLS - 3 - engine.width(label)
  return engine.glyph.tl
    .. engine.glyph.h
    .. label
    .. engine.rep(engine.glyph.h, fill)
    .. engine.glyph.tr
end

-- HUD row: score / best (player) / length, 3-space separated.
local function hud_line()
  local text = "score " .. state.score
    .. "   best " .. state.best
    .. " (" .. state.best_player .. ")"
    .. "   length " .. #state.snake
  return engine.glyph.v .. engine.pad(text, INNER) .. engine.glyph.v
end

-- One board row as 30 doubled cells, head over body, food on top.
local function board_cells(by)
  local cells = {}
  for _ = 1, BOARD_W do
    cells[#cells + 1] = EMPTY
  end
  for index = #state.snake, 2, -1 do
    local part = state.snake[index]
    cells[part.x] = BODY
  end
  local head = state.snake[1]
  cells[head.x] = HEAD
  if state.food ~= nil then
    cells[state.food.x] = FOOD
  end
  return table.concat(cells)
end

-- Help separator between the board and the bottom border.
local function help_line()
  local inner = INNER - engine.width(HELP_TEXT) - 2
  return engine.glyph.h
    .. " "
    .. HELP_TEXT
    .. " "
    .. engine.rep(engine.glyph.h, inner)
    .. engine.glyph.h
end

-- ASCII overlay text centered on one board row (replaces its cells).
local function overlay_line(text)
  return engine.glyph.v .. engine.center(text, INNER) .. engine.glyph.v
end

-- Render the whole canvas as one newline-joined string.
local function render()
  local rows = { top_line(), hud_line() }
  for by = 1, BOARD_H do
    if not state.alive and by == 9 then
      rows[#rows + 1] = overlay_line("game over")
    elseif not state.alive and by == 11 then
      rows[#rows + 1] = overlay_line("press r")
    elseif state.alive and state.paused and by == 10 then
      rows[#rows + 1] = overlay_line("paused")
    else
      rows[#rows + 1] = engine.glyph.v .. board_cells(by) .. engine.glyph.v
    end
  end
  rows[#rows + 1] = help_line()
  rows[#rows + 1] = engine.box_bottom(INNER)
  return table.concat(rows, "\n")
end

-- Push the current frame and status line to the canvas.
local function paint()
  if session == nil then
    return
  end
  session.status(
    "score " .. state.score
      .. "  best " .. state.best
      .. "  length " .. #state.snake
  )
  session.paint()
end

-- ------------------------------------------------------------------ callbacks

-- Turn request: reverse and same-direction repeats are ignored, anything
-- else takes effect on the next step (compared against the queued turn).
local function on_key(key)
  if state == nil or session == nil then
    return
  end
  if key == "r" then
    reset_game()
    load_best()
    paint()
    return
  end
  if not state.alive then
    return
  end
  if key == "p" then
    state.paused = not state.paused
    paint()
    return
  end
  if state.paused then
    return
  end
  local dx, dy = engine.direction(key)
  if dx == nil then
    return
  end
  local current = state.pending or state.dir
  if (dx == current.x and dy == current.y)
    or (dx == -current.x and dy == -current.y) then
    return
  end
  state.pending = { x = dx, y = dy }
  paint()
end

local function on_tick()
  if state == nil or session == nil then
    return
  end
  if state.alive and not state.paused then
    state.ticks = state.ticks + 1
    if state.ticks >= state.step_ticks then
      state.ticks = 0
      step()
    end
  end
  paint()
end

-- Closing the canvas: make sure the save file exists (silent on failure).
local function on_close()
  session = nil
  local document = store.load()
  if type(document) ~= "table" then
    store.save({
      version = engine.VERSION,
      player = engine.player(),
      high_scores = {},
      stats = { games = 0, best_length = 0 },
    })
  end
end

-- ----------------------------------------------------------------- module API

-- Start a fresh game on a new canvas (the engine guards double launches).
local function start()
  reset_game()
  load_best()
  session = engine.open({
    name = "snake",
    cols = COLS,
    rows = ROWS,
    draw = function()
      return render(), PALETTE
    end,
    on_key = on_key,
    on_tick = on_tick,
    on_close = on_close,
  })
  if session ~= nil then
    paint()
  end
end

-- Pin the rng seed for food placement (tests inject a fixed seed).
function mod.set_seed(value)
  seed = value
  rng = engine.rng(seed)
end

-- Replace the random food source with fn (returning {x=,y=}); a fn result
-- landing on the snake falls back to random.  nil restores randomness.
function mod.set_food_source(fn)
  food_source = fn
  -- Re-place the food right away (like tetris resets its bag), so a test
  -- that pins the source after the launch still controls the next bite.
  if state ~= nil and state.snake ~= nil then
    spawn_food()
  end
end

-- The test seam: everything a test needs without reading the canvas.
function mod.snapshot()
  if state == nil then
    return {}
  end
  local head = state.snake[1]
  return {
    score = state.score,
    length = #state.snake,
    alive = state.alive,
    paused = state.paused,
    head_x = head.x,
    head_y = head.y,
    dir_x = state.dir.x,
    dir_y = state.dir.y,
    food_x = state.food ~= nil and state.food.x or 0,
    food_y = state.food ~= nil and state.food.y or 0,
    best = state.best,
    step_ticks = state.step_ticks,
  }
end

function mod.setup(_api)
  -- Reset leftovers from a previous load of this file in the same runtime.
  session = nil
  state = nil
  rng = engine.rng(seed)
  engine.register("snake", start)
end

function mod.teardown(_api)
  local open = session
  session = nil
  if open ~= nil then
    open.close()
  end
end

return mod
