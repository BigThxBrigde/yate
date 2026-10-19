--[[
yate bundled extension: tetris (tetris.lua)

A complete Tetris that lives entirely in Lua, drawn on a yate extension
canvas: a 10 x 20 board of solid two-column blocks in a titled box, flanked
by a stats box (score / level) on the left and next-piece preview + help
boxes on the right.  Nothing about the game is implemented on the Python
side: the canvas only paints the grid it is handed, forwards keys and runs a
fixed 15 Hz clock.

Start it with ``:game tetris``.

Controls:
  left / right   move the falling piece
  down           soft drop (one row, resets the gravity counter)
  up / x         rotate clockwise (wall kicks: 0, -1, +1, -2, +2)
  space          hard drop (lands and locks immediately)
  enter          commit the piece: it falls one row per tick (full speed)
                 and can no longer move or rotate; the next piece is free
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

-- Board size in cells.  The canvas composes three bordered boxes around the
-- board: a stats box (score / level) on the left, the board in the middle and
-- a next-piece preview plus a help box on the right.  Every board cell renders
-- as a solid two-column block.
local W, H = 10, 20

local STAT_INNER = 15              -- stats box inner width
local NEXT_INNER = 16              -- next / help box inner width
local LEFT_W = STAT_INNER + 2      -- full stats box width
local BOARD_W = 2 * W              -- doubled board width
local RIGHT_W = NEXT_INNER + 2     -- full right box width
local CANVAS_COLS = LEFT_W + 1 + (BOARD_W + 2) + 1 + RIGHT_W
local CANVAS_ROWS = H + 2          -- the board box carries its own borders

-- Tick rate of the canvas clock (kept in sync with CanvasScreen): gravity is
-- expressed in ticks, never in seconds.
local TICKS_PER_SECOND = 15

-- Ticks between gravity steps: one level faster per level, two ticks floor.
local GRAVITY_MIN = 2

-- Points per cleared line count: index 1 = one line, index 4 = four lines.
local LINE_SCORES = { 100, 300, 500, 800 }

-- One palette entry per tetromino; the canvas maps a drawn character to a
-- color, so the board is stored as the piece letter itself.  The "*" entry
-- is the glyph painted for every colored cell: the letters stay grid data,
-- the screen shows solid blocks.
local COLORS = {
  I = "#00e5ff",
  O = "#ffd54f",
  T = "#ba68c8",
  S = "#81c784",
  Z = "#e57373",
  J = "#64b5f6",
  L = "#ffb74d",
  ["*"] = "█",
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
  state.committed = false  -- a fresh piece is always controllable again
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
    committed = false,
    paused = false,
    game_over = false,
  }
  spawn_piece()
end

-- Ticks between two gravity steps for the current level; a committed piece
-- always falls at full speed (one row per tick).
local function gravity_every()
  if state.committed then
    return 1
  end
  return math.max(GRAVITY_MIN, TICKS_PER_SECOND - state.level)
end

-- Center *text* in a *width*-wide field (right side gets the odd space).
local function center(text, width)
  local left = math.floor((width - #text) / 2)
  return string.rep(" ", left) .. text .. string.rep(" ", width - #text - left)
end

-- Box-drawing helpers: a titled top border, a plain bottom border.  Borders
-- use the same Unicode line glyphs as the surrounding frame.  Lua strings are
-- byte strings, so the borders are only ever concatenated, never sliced: all
-- splicing in this file happens on the pure-ASCII board cell strings where
-- one byte still equals one display column.
local function box_top(title, inner)
  local label_width = #title + 3  -- "─ " .. title .. " " in display columns
  return "┌─ " .. title .. " " .. string.rep("─", inner - label_width) .. "┐"
end

local function box_bottom(inner)
  return "└" .. string.rep("─", inner) .. "┘"
end

-- Left column: the stats box on the top rows, blank below it.  Labels are
-- lowercase on purpose: piece letters (I O T S Z J L) are the only colored
-- characters, and lowercase text never collides with them.
local function stats_lines()
  local lines = {}
  lines[1] = box_top("stats", STAT_INNER)
  lines[2] = "│" .. string.format(" score%9d", state.score) .. "│"
  lines[3] = "│" .. string.format(" level%9d", state.level) .. "│"
  lines[4] = box_bottom(STAT_INNER)
  for row = 5, CANVAS_ROWS do
    lines[row] = string.rep(" ", LEFT_W)
  end
  return lines
end

-- Right column: the next-piece preview box on top, the help box below it.
-- Preview cells are doubled like board cells, so they render as solid blocks.
local function right_lines()
  local lines = {}
  lines[1] = box_top("next", NEXT_INNER)
  local preview = {}
  for row = 1, 4 do
    preview[row] = { "  ", "  ", "  ", "  " }
  end
  if state.next_kind ~= nil then
    for _, cell in ipairs(cells_of(state.next_kind, 1)) do
      preview[cell[2] + 1][cell[1] + 1] = state.next_kind .. state.next_kind
    end
  end
  for row = 1, 4 do
    lines[1 + row] = "│" .. center(table.concat(preview[row]), NEXT_INNER) .. "│"
  end
  lines[6] = box_bottom(NEXT_INNER)
  lines[7] = string.rep(" ", RIGHT_W)
  lines[8] = box_top("help", NEXT_INNER)
  -- Key glyphs are UTF-8 (multi-byte in Lua), so the right-align padding is
  -- computed from the explicit display width instead of string.format.
  local keys = {
    { "left", "←", 1 },
    { "right", "→", 1 },
    { "down", "↓", 1 },
    { "rotate", "↑/x", 3 },
    { "drop", "space", 5 },
    { "enter", "fall", 4 },
    { "pause", "p", 1 },
    { "restart", "r", 1 },
    { "quit", "esc", 3 },
  }
  for index, binding in ipairs(keys) do
    local field = string.rep(" ", 7 - binding[3]) .. binding[2]
    lines[8 + index] = "│" .. string.format(" %-7s", binding[1]) .. field .. " │"
  end
  local bottom = 8 + #keys + 1
  lines[bottom] = box_bottom(NEXT_INNER)
  for row = bottom + 1, CANVAS_ROWS do
    lines[row] = string.rep(" ", RIGHT_W)
  end
  return lines
end

-- One board row's inner cells: every cell doubled into a solid block pair.
-- Pure ASCII on purpose: byte offsets equal display columns here, which is
-- what the piece stamping and the overlay text rely on.
local function cells_line(row)
  local line = {}
  for col = 1, W do
    local cell = state.board[row][col] or " "
    line[#line + 1] = cell
    line[#line + 1] = cell
  end
  return table.concat(line)
end

-- Overwrite *text* centered on the cell string of board row *board_row*
-- (1-based, pure ASCII, so plain Lua substring math is exact).  Lowercase
-- keeps it clear of the palette colors.
local function overlay(cells, text, board_row)
  local start = 1 + math.floor((BOARD_W - #text) / 2)
  local line = cells[board_row]
  cells[board_row] = line:sub(1, start - 1) .. text .. line:sub(start + #text)
end

-- Render the whole canvas as one newline-joined string: stats box | board box
-- | next + help boxes, one blank gap between the boxes.  The falling piece is
-- stamped onto the pure-ASCII cell strings and overlay texts are written
-- before the bordered rows are assembled.
local function render()
  local stats = stats_lines()
  local right = right_lines()
  local cells = {}
  for row = 1, H do
    cells[row] = cells_line(row)
  end
  if not state.game_over and state.kind ~= nil then
    for _, cell in ipairs(cells_of(state.kind, state.rot)) do
      local col = state.x + cell[1] + 1
      local row = state.y + cell[2] + 1
      if row >= 1 and row <= H and col >= 1 and col <= W then
        local at = 2 * (col - 1) + 1  -- first block column (byte == column)
        local line = cells[row]
        cells[row] = line:sub(1, at - 1)
          .. state.kind .. state.kind
          .. line:sub(at + 2)
      end
    end
  end
  if state.game_over then
    overlay(cells, "game over", 9)
    overlay(cells, "press r", 11)
  elseif state.paused then
    overlay(cells, "paused", 10)
  end
  local rows = {}
  for row = 1, CANVAS_ROWS do
    local middle
    if row == 1 then
      middle = box_top("tetris", BOARD_W)
    elseif row == H + 2 then
      middle = box_bottom(BOARD_W)
    else
      middle = "│" .. cells[row - 1] .. "│"
    end
    rows[row] = stats[row] .. " " .. middle .. " " .. right[row]
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
  handle.set_status("escape quits")
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
  if name == "enter" then
    -- commit: the piece rushes down at full speed and loses its controls
    state.committed = true
    paint()
    return
  end
  if state.committed
    and (name == "left" or name == "right" or name == "up" or name == "x") then
    return  -- a committed piece can no longer move or rotate
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
  handle = yate.ui.open_canvas(CANVAS_COLS, CANVAS_ROWS, on_key, on_tick, on_close)
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
