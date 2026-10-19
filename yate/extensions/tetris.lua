--[[
yate bundled extension: tetris (tetris.lua)

A complete Tetris that lives entirely in Lua, drawn on a yate extension
canvas (10 x 20 board, one character per cell).  Nothing about the game is
implemented on the Python side: the canvas only paints the grid it is
handed, forwards keys and runs a fixed 15 Hz clock.

Start it with ``:game tetris``.

Controls:
  left / right   move the falling piece
  down           soft drop (one row, resets the gravity counter)
  up / x         rotate clockwise (wall kicks: 0, -1, +1, -2, +2)
  space          hard drop (lands and locks immediately)
  p              pause / resume
  r              restart (also from game over and from pause)
  escape         exit the canvas (consumed by the canvas itself)

Scoring follows the classic NES table: 100 / 300 / 500 / 800 points per
cleared line count, multiplied by the current level.  The level is
``1 + lines // 10``; gravity runs every ``max(2, 15 - level)`` ticks, so the
piece falls faster as the level rises (the clock itself never changes).

Entry form: module-table style -- this file returns ``mod`` and yate calls
``mod.setup(api)`` at load and ``mod.teardown(api)`` on unload.
]]

-- Board size in characters.  The canvas is opened at exactly this size.
local W, H = 10, 20

-- Tick rate of the canvas clock (kept in sync with CanvasScreen): gravity is
-- expressed in ticks, never in seconds.
local TICKS_PER_SECOND = 15

-- Ticks between gravity steps: one level faster per level, two ticks floor.
local GRAVITY_MIN = 2

-- Points per cleared line count: index 1 = one line, index 4 = four lines.
local LINE_SCORES = { 100, 300, 500, 800 }

-- One palette entry per tetromino; the canvas maps a drawn character to a
-- color, so the board is stored as the piece letter itself.
local COLORS = {
  I = "#00e5ff",
  O = "#ffd54f",
  T = "#ba68c8",
  S = "#81c784",
  Z = "#e57373",
  J = "#64b5f6",
  L = "#ffb74d",
}

-- Rotation states per tetromino: cells are {x, y} offsets inside the shape's
-- bounding box (0-based, y grows downwards).  Every piece is defined with
-- square cells, so a rotation is just the next entry (wrapping around).
local SHAPES = {
  I = {
    { { 0, 1 }, { 1, 1 }, { 2, 1 }, { 3, 1 } },
    { { 2, 0 }, { 2, 1 }, { 2, 2 }, { 2, 3 } },
  },
  O = {
    { { 0, 0 }, { 1, 0 }, { 0, 1 }, { 1, 1 } },
  },
  T = {
    { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 2, 1 } },
    { { 0, 0 }, { 0, 1 }, { 1, 1 }, { 0, 2 } },
    { { 0, 0 }, { 1, 0 }, { 2, 0 }, { 1, 1 } },
    { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 1, 2 } },
  },
  S = {
    { { 1, 0 }, { 2, 0 }, { 0, 1 }, { 1, 1 } },
    { { 0, 0 }, { 0, 1 }, { 1, 1 }, { 1, 2 } },
  },
  Z = {
    { { 0, 0 }, { 1, 0 }, { 1, 1 }, { 2, 1 } },
    { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 0, 2 } },
  },
  J = {
    { { 0, 0 }, { 0, 1 }, { 1, 1 }, { 2, 1 } },
    { { 0, 0 }, { 1, 0 }, { 0, 1 }, { 0, 2 } },
    { { 0, 0 }, { 1, 0 }, { 2, 0 }, { 2, 1 } },
    { { 1, 0 }, { 1, 1 }, { 0, 2 }, { 1, 2 } },
  },
  L = {
    { { 2, 0 }, { 0, 1 }, { 1, 1 }, { 2, 1 } },
    { { 0, 0 }, { 0, 1 }, { 0, 2 }, { 1, 2 } },
    { { 0, 0 }, { 1, 0 }, { 2, 0 }, { 0, 1 } },
    { { 0, 0 }, { 1, 0 }, { 1, 1 }, { 1, 2 } },
  },
}

-- Horizontal offsets tried in order when a rotation collides at x (wall kick).
local KICKS = { 0, -1, 1, -2, 2 }

-- Bag-7 order the bag is refilled from before shuffling.
local BAG_KINDS = { "I", "O", "T", "S", "Z", "J", "L" }

-- Game state (rebuilt by reset()); nil until the first start.
local state = nil

-- Canvas handle returned by yate.ui.open_canvas; nil while no canvas is open.
local handle = nil

-- Remaining pieces of the current Bag-7 batch and an optional injected piece
-- source.  The source is the deterministic seam tests (and scripted demos)
-- use instead of math.random: a function returning the next piece letter.
local bag = {}
local piece_source = nil

-- Forward declaration: lock_piece() spawns the following piece, spawn_piece()
-- is defined below (a plain local declaration keeps it out of _G).
local spawn_piece

local mod = {}

-- --------------------------------------------------------------------- pieces

-- Return the cell list of the given rotation (1-based, wrapping around).
local function cells_of(kind, rot)
  local rotations = SHAPES[kind]
  return rotations[(rot - 1) % #rotations + 1]
end

-- True when the piece at (px, py) overlaps a wall, the floor or the stack.
local function collides(kind, rot, px, py)
  for _, cell in ipairs(cells_of(kind, rot)) do
    local col = px + cell[1] + 1
    local row = py + cell[2] + 1
    if col < 1 or col > W or row > H then
      return true
    end
    if row >= 1 and state.board[row][col] ~= nil then
      return true
    end
  end
  return false
end

-- Next piece letter: the injected source when present, otherwise Bag-7.
local function next_kind()
  if piece_source ~= nil then
    return piece_source()
  end
  if #bag == 0 then
    bag = {}
    for index, kind in ipairs(BAG_KINDS) do
      bag[index] = kind
    end
    -- Fisher-Yates: every batch holds all seven pieces, in random order.
    for index = #bag, 2, -1 do
      local other = math.random(index)
      bag[index], bag[other] = bag[other], bag[index]
    end
  end
  return table.remove(bag)
end

-- Move the current piece onto the board and lock it there.
local function lock_piece()
  local above_top = false
  for _, cell in ipairs(cells_of(state.kind, state.rot)) do
    local col = state.x + cell[1] + 1
    local row = state.y + cell[2] + 1
    if row < 1 then
      above_top = true
    elseif row <= H and col >= 1 and col <= W then
      state.board[row][col] = state.kind
    end
  end
  state.gravity_ticks = 0
  if above_top then
    state.game_over = true
    return
  end
  -- Full rows collapse: keep the incomplete ones, then pad empty rows on top.
  local kept = {}
  for row = 1, H do
    local full = true
    for col = 1, W do
      if state.board[row][col] == nil then
        full = false
        break
      end
    end
    if not full then
      kept[#kept + 1] = state.board[row]
    end
  end
  local cleared = H - #kept
  if cleared > 0 then
    local board = {}
    for row = 1, cleared do
      board[row] = {}
    end
    for index, row_cells in ipairs(kept) do
      board[cleared + index] = row_cells
    end
    state.board = board
    state.score = state.score + LINE_SCORES[cleared] * state.level
    state.lines = state.lines + cleared
    state.level = 1 + math.floor(state.lines / 10)
  end
  spawn_piece()
end

-- Put the next piece at the top center; a blocked spawn ends the game.
spawn_piece = function()
  state.kind = state.next_kind or next_kind()
  state.next_kind = next_kind()
  state.rot = 1
  state.x = 3
  state.y = 0
  if collides(state.kind, state.rot, state.x, state.y) then
    state.game_over = true
  end
end

-- ------------------------------------------------------------------- movement

-- Shift the piece one column; blocked moves are a no-op.
local function move(dx)
  if not collides(state.kind, state.rot, state.x + dx, state.y) then
    state.x = state.x + dx
  end
end

-- Drop one row; lock when the piece has landed.  Returns true when it moved.
local function step_down()
  if not collides(state.kind, state.rot, state.x, state.y + 1) then
    state.y = state.y + 1
    return true
  end
  lock_piece()
  return false
end

-- Rotate clockwise, trying the wall-kick offsets until the piece fits.
local function rotate()
  local rotations = #SHAPES[state.kind]
  local next_rot = state.rot % rotations + 1
  for _, kick in ipairs(KICKS) do
    if not collides(state.kind, next_rot, state.x + kick, state.y) then
      state.rot = next_rot
      state.x = state.x + kick
      return
    end
  end
end

-- -------------------------------------------------------------- state and view

local function new_board()
  local board = {}
  for row = 1, H do
    board[row] = {}
  end
  return board
end

local function reset()
  state = {
    board = new_board(),
    kind = nil,
    next_kind = nil,
    rot = 1,
    x = 3,
    y = 0,
    score = 0,
    lines = 0,
    level = 1,
    gravity_ticks = 0,
    paused = false,
    game_over = false,
  }
  spawn_piece()
end

-- Ticks between two gravity steps for the current level.
local function gravity_every()
  return math.max(GRAVITY_MIN, TICKS_PER_SECOND - state.level)
end

-- Center *text* on board row *row* (characters outside the board are clipped).
local function overlay(grid, text, row)
  local start = math.floor((W - #text) / 2) + 1
  for index = 1, #text do
    local col = start + index - 1
    if col >= 1 and col <= W then
      grid[row][col] = text:sub(index, index)
    end
  end
end

-- Render the whole canvas as one newline-joined string.
local function render()
  local grid = {}
  for row = 1, H do
    grid[row] = {}
    for col = 1, W do
      grid[row][col] = state.board[row][col] or " "
    end
  end
  if not state.game_over and state.kind ~= nil then
    for _, cell in ipairs(cells_of(state.kind, state.rot)) do
      local col = state.x + cell[1] + 1
      local row = state.y + cell[2] + 1
      if row >= 1 and row <= H and col >= 1 and col <= W then
        grid[row][col] = state.kind
      end
    end
  end
  if state.game_over then
    overlay(grid, "GAME OVER", 9)
    overlay(grid, "press r", 11)
  elseif state.paused then
    overlay(grid, "PAUSED", 10)
  end
  local rows = {}
  for row = 1, H do
    rows[row] = table.concat(grid[row])
  end
  return table.concat(rows, "\n")
end

-- Push the current frame and status line to the canvas.
local function paint()
  if handle == nil then
    return
  end
  -- dot call: handle is a Python object, a colon would pass the handle itself
  handle.draw(render(), COLORS)
  handle.set_status(string.format(
    "score %d  lines %d  level %d  next: %s",
    state.score, state.lines, state.level, tostring(state.next_kind)
  ))
end

-- ------------------------------------------------------------------- callbacks

local function on_tick()
  if state == nil or handle == nil then
    return
  end
  if not state.game_over and not state.paused then
    state.gravity_ticks = state.gravity_ticks + 1
    if state.gravity_ticks >= gravity_every() then
      state.gravity_ticks = 0
      step_down()
    end
  end
  paint()
end

local function on_key(name)
  if state == nil or handle == nil then
    return
  end
  if name == "r" then
    reset()
    paint()
    return
  end
  if state.game_over then
    return
  end
  if name == "p" then
    state.paused = not state.paused
    paint()
    return
  end
  if state.paused then
    return
  end
  if name == "left" then
    move(-1)
  elseif name == "right" then
    move(1)
  elseif name == "down" then
    step_down()
    state.gravity_ticks = 0
  elseif name == "up" or name == "x" then
    rotate()
  elseif name == "space" then
    while not collides(state.kind, state.rot, state.x, state.y + 1) do
      state.y = state.y + 1
    end
    lock_piece()
  else
    return
  end
  paint()
end

local function on_close()
  handle = nil
end

-- ----------------------------------------------------------------- extension API

-- Start a fresh game on a new canvas.
local function start_game()
  reset()
  handle = yate.ui.open_canvas(W, H, on_key, on_tick, on_close)
  paint()
end

-- ``:game`` handler: ``:game tetris`` launches, anything else is reported.
local function launch(args)
  local raw = args or ""
  local name = raw:match("^%s*(.-)%s*$")
  if name == "" then
    yate.message("usage: :game tetris")
    return
  end
  if name ~= "tetris" then
    yate.message("unknown game: " .. name .. " (available: tetris)")
    return
  end
  if handle ~= nil then
    yate.message("tetris is already running")
    return
  end
  start_game()
end

-- Replace the random piece source with fn (returning a piece letter), which
-- makes a run fully reproducible; passing nil restores Bag-7 randomness.
function mod.set_piece_source(fn)
  piece_source = fn
  bag = {}
end

function mod.setup(_api)
  -- Reset leftovers from a previous load of this file in the same runtime.
  handle = nil
  state = nil
  bag = {}
  yate.register_command("game", launch, "launch a game (tetris)")
end

function mod.teardown(_api)
  local open = handle
  handle = nil
  if open ~= nil then
    open.close()
  end
end

return mod
