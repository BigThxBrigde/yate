--[[
yate bundled extension: sokoban (sokoban.lua)

A classic sokoban drawn on a yate extension canvas: a 21 x 12 level area
inside a rounded 23 x 16 frame, a HUD row (level / moves / pushes / done)
and a help row above the bottom border.  Walls are blue blocks, crates
brown, crates on goals green, goals grey and the player yellow.

Start it with ``:game sokoban``.

Controls:
  arrows / hjkl / wasd   walk (pushing a crate when the way is clear)
  u                      undo one step (player and pushed crate)
  r                      restart the current level (level 1 once cleared)
  n                      next level (only after solving)
  p                      pause / resume (only p / r / escape while paused)
  escape                 exit the canvas (consumed by the canvas itself)

Rules: walking into a wall or an immovable crate is a no-op and does not
count as a move.  A level is solved when every goal holds a crate; solving
records the level and saves progress, ``n`` then advances.  After the last
level the board reports "all levels cleared" and ``r`` restarts at level 1.

Persistence goes through the shared engine: ``games/sokoban.json`` keeps
the resumed level, the completed list and the accumulated move / push
totals, so the pack resumes where it left off.

Entry form: module-table style -- this file returns ``mod`` and yate calls
``mod.setup(api)`` at load and ``mod.teardown(api)`` on unload.
]]

local engine = require("game_engine")

-- Canvas geometry: 23 x 16, inner width 21, level area 21 x 12.
local COLS, ROWS = 23, 16
local INNER = 21
local AREA_W, AREA_H = 21, 12

-- Undo history cap; the oldest entry is dropped beyond it.
local MAX_UNDO = 200

-- The level area row carrying overlay text (paused / cleared).
local OVERLAY_ROW = 6

-- Help row between the HUD and the bottom border (fits 21 columns).
local HELP_TEXT = "u undo r rst n next p"

--: Built-in levels: 1-5 from the public Microban set, 6 a teaching level.
local LEVELS = {
  { -- 1
    "####",
    "# .#",
    "#  ###",
    "#*@  #",
    "#  $ #",
    "#  ###",
    "####",
  },
  { -- 2
    "######",
    "#    #",
    "# #@ #",
    "# $* #",
    "# .* #",
    "#    #",
    "######",
  },
  { -- 3
    "  ####",
    "###  ####",
    "#     $ #",
    "# #  #$ #",
    "# . .#@ #",
    "#########",
  },
  { -- 4
    "########",
    "#      #",
    "# .**$@#",
    "#      #",
    "#####  #",
    "    ####",
  },
  { -- 5
    " #######",
    " #     #",
    " # .$. #",
    "## $@$ #",
    "#  .$. #",
    "#      #",
    "########",
  },
  { -- 6 (teaching level: push right twice)
    "#######",
    "#     #",
    "#     #",
    "# @$. #",
    "#     #",
    "#######",
  },
}

-- Cell glyphs (single width, from the shared engine vocabulary).
local G = engine.glyph

-- Palette handed to the canvas: glyph -> color.
local PALETTE = {
  [G.block] = "#4a90d9",
  [G.box] = "#8d5524",
  [G.box_on_goal] = "#7bd88f",
  [G.goal] = "#bdbdbd",
  [G.player] = "#ffd54f",
}

-- Game state (built by load_level); nil until first use.
local state = nil

-- The open canvas session; nil while no canvas is open.
local session = nil

-- Shared persistence handle.
local store = engine.store("sokoban")

local mod = {}

-- ---------------------------------------------------------------- level data

-- Parse one level's rows into cells / crates / goals / player start.
local function parse_level(rows)
  local cells = {}
  local boxes = {}
  local player = { x = 1, y = 1 }
  for y, row in ipairs(rows) do
    cells[y] = {}
    for x = 1, #row do
      local char = row:sub(x, x)
      local cell = " "
      if char == "#" then
        cell = "#"
      elseif char == "." or char == "*" or char == "+" then
        cell = "."
      end
      cells[y][x] = cell
      if char == "$" or char == "*" then
        boxes[#boxes + 1] = { x = x, y = y }
      elseif char == "@" or char == "+" then
        player.x, player.y = x, y
      end
    end
  end
  return cells, boxes, player
end

-- Load level *n* (clamped to 1..#LEVELS); totals and completed survive.
local function load_level(number)
  local index = math.floor(tonumber(number) or 1)
  if index < 1 then
    index = 1
  end
  if index > #LEVELS then
    index = #LEVELS
  end
  local cells, boxes, player = parse_level(LEVELS[index])
  state.level = index
  state.cells = cells
  state.boxes = boxes
  state.player = player
  state.moves = 0
  state.pushes = 0
  state.solved = false
  state.paused = false
  state.cleared = false
  state.undo = {}
end

-- A state shell for direct module-level calls before the first launch.
local function ensure_state()
  if state ~= nil then
    return
  end
  state = {
    level = 1,
    cells = {},
    boxes = {},
    player = { x = 1, y = 1 },
    moves = 0,
    pushes = 0,
    solved = false,
    paused = false,
    cleared = false,
    undo = {},
    total_moves = 0,
    total_pushes = 0,
    completed = {},
  }
end

-- ------------------------------------------------------------------ queries

-- True when (x, y) is a wall (outside the level data counts as wall too).
local function is_wall(x, y)
  local row = state.cells[y]
  if row == nil then
    return true
  end
  if x < 1 or x > #row then
    return true
  end
  return row[x] == "#"
end

-- True when (x, y) is a goal cell.
local function is_goal(x, y)
  local row = state.cells[y]
  return row ~= nil and row[x] == "."
end

-- The crate at (x, y), or nil.
local function box_at(x, y)
  for index, box in ipairs(state.boxes) do
    if box.x == x and box.y == y then
      return index, box
    end
  end
  return nil
end

-- Add *level* to the completed list (kept unique and ascending).
local function mark_completed(level)
  for _, done in ipairs(state.completed) do
    if done == level then
      return
    end
  end
  state.completed[#state.completed + 1] = level
  table.sort(state.completed)
end

-- -------------------------------------------------------------- persistence

--: Saved fields: version, level, completed, moves, pushes (accumulated).
local function save_progress(resume_level)
  local level = resume_level
  if level == nil then
    level = state.level
    if state.cleared then
      level = 1
    elseif state.solved then
      level = math.min(state.level + 1, #LEVELS)
    end
  end
  store.save({
    version = engine.VERSION,
    level = level,
    completed = state.completed,
    moves = state.total_moves + state.moves,
    pushes = state.total_pushes + state.pushes,
  })
end

-- Restore progress from games/sokoban.json (silently fresh when missing).
local function load_progress()
  local document = store.load()
  if type(document) ~= "table" then
    -- Distinguish a corrupt file from a missing one: only the corrupt
    -- case is reported (the store swallows the decode error itself).
    local ok, raw = pcall(yate.data.read, store.path)
    if ok and raw ~= nil then
      yate.message("sokoban: save file is corrupted, starting fresh")
    end
    document = {}
  end
  ensure_state()
  local completed = {}
  if type(document.completed) == "table" then
    for _, level in ipairs(document.completed) do
      if type(level) == "number" and level >= 1 and level <= #LEVELS then
        local known = false
        for _, done in ipairs(completed) do
          if done == math.floor(level) then
            known = true
          end
        end
        if not known then
          completed[#completed + 1] = math.floor(level)
        end
      end
    end
    table.sort(completed)
  end
  state.completed = completed
  state.total_moves = tonumber(document.moves) or 0
  state.total_pushes = tonumber(document.pushes) or 0
  load_level(tonumber(document.level) or 1)
end

-- ------------------------------------------------------------------- rules

-- Remember one undo record (player cell plus the pushed crate's old cell).
local function push_undo(record)
  state.undo[#state.undo + 1] = record
  if #state.undo > MAX_UNDO then
    table.remove(state.undo, 1)
  end
end

-- Walk one step; pushing a crate costs a move and a push, blocking costs
-- nothing at all (no move counter, no undo record).
local function move(dx, dy)
  local px, py = state.player.x, state.player.y
  local nx, ny = px + dx, py + dy
  if is_wall(nx, ny) then
    return
  end
  local index = box_at(nx, ny)
  if index ~= nil then
    local bx, by = nx + dx, ny + dy
    if is_wall(bx, by) or box_at(bx, by) ~= nil then
      return
    end
    push_undo({ px = px, py = py, index = index, bx = nx, by = ny })
    state.boxes[index].x, state.boxes[index].y = bx, by
    state.pushes = state.pushes + 1
  else
    push_undo({ px = px, py = py })
  end
  state.player.x, state.player.y = nx, ny
  state.moves = state.moves + 1
  -- Solved when every goal holds a crate.
  local solved = true
  for y, row in ipairs(state.cells) do
    for x, cell in ipairs(row) do
      if cell == "." and box_at(x, y) == nil then
        solved = false
      end
    end
  end
  if solved and not state.solved then
    state.solved = true
    mark_completed(state.level)
    save_progress()
  end
end

-- Undo one step: the player and the pushed crate return to their cells.
local function undo()
  local record = table.remove(state.undo)
  if record == nil then
    return
  end
  state.player.x, state.player.y = record.px, record.py
  if record.index ~= nil then
    local box = state.boxes[record.index]
    box.x, box.y = record.bx, record.by
    state.pushes = state.pushes - 1
  end
  state.moves = state.moves - 1
end

-- Restart the current level (back to level 1 once everything is cleared).
local function restart()
  if state.cleared then
    load_level(1)
  else
    load_level(state.level)
  end
end

-- Advance to the next level (only valid on a solved level).
local function advance()
  if not state.solved then
    return
  end
  if state.level >= #LEVELS then
    state.cleared = true
    save_progress(1)
    return
  end
  state.total_moves = state.total_moves + state.moves
  state.total_pushes = state.total_pushes + state.pushes
  load_level(state.level + 1)
  save_progress()
end

-- ---------------------------------------------------------------- rendering

-- One level-area row as 21 single-width glyph cells (never byte-spliced).
local function area_row(ly)
  local cells = {}
  for lx = 1, AREA_W do
    local row = state.cells[ly]
    local glyph = " "
    if row ~= nil and lx <= #row then
      if row[lx] == "#" then
        glyph = G.block
      elseif row[lx] == "." then
        glyph = G.goal
      end
    end
    cells[lx] = glyph
  end
  for _, box in ipairs(state.boxes) do
    if box.y == ly and box.x >= 1 and box.x <= AREA_W then
      cells[box.x] = is_goal(box.x, box.y) and G.box_on_goal or G.box
    end
  end
  if state.player.y == ly then
    cells[state.player.x] = G.player
  end
  return table.concat(cells)
end

-- HUD row: resumed level, per-level counters, completed count.
local function hud_text()
  return "level " .. state.level .. "/" .. #LEVELS
    .. "  m" .. state.moves
    .. " p" .. state.pushes
    .. " d" .. #state.completed
end

-- Render the whole canvas as one newline-joined string.
local function render()
  local rows = { engine.box_top("sokoban", INNER) }
  for ly = 1, AREA_H do
    if ly == OVERLAY_ROW and (state.paused or state.cleared) then
      local text = state.cleared and "all levels cleared" or "paused"
      rows[#rows + 1] = G.v .. engine.center(text, INNER) .. G.v
    else
      rows[#rows + 1] = G.v .. area_row(ly) .. G.v
    end
  end
  rows[#rows + 1] = G.v .. engine.pad(hud_text(), INNER) .. G.v
  rows[#rows + 1] = G.v .. engine.pad(HELP_TEXT, INNER) .. G.v
  rows[#rows + 1] = engine.box_bottom(INNER)
  return table.concat(rows, "\n")
end

-- Push the current frame and status line to the canvas.
local function paint()
  if session == nil then
    return
  end
  local text = "u undo  r restart  n next  p pause"
  if state.cleared then
    text = "all levels cleared  r restart"
  elseif state.paused then
    text = "paused  p resume"
  elseif state.solved then
    text = "solved!  n next"
  end
  session.status(text)
  session.paint()
end

-- ---------------------------------------------------------------- callbacks

local function on_key(key)
  if state == nil or session == nil then
    return
  end
  if key == "p" then
    state.paused = not state.paused
    paint()
    return
  end
  if key == "r" then
    restart()
    paint()
    return
  end
  if state.paused then
    return -- while paused only p / r / escape are honoured
  end
  if key == "u" then
    undo()
    paint()
    return
  end
  if key == "n" then
    advance()
    paint()
    return
  end
  local dx, dy = engine.direction(key)
  if dx == nil then
    return
  end
  move(dx, dy)
  paint()
end

-- Closing the canvas: persist the run (silent on failure).
local function on_close(_closed_session)
  session = nil
  if state ~= nil then
    save_progress()
  end
end

-- ----------------------------------------------------------------- module API

-- Start (or resume) the game on a new canvas (the engine guards doubles).
local function start()
  load_progress()
  session = engine.open({
    name = "sokoban",
    cols = COLS,
    rows = ROWS,
    draw = function()
      return render(), PALETTE
    end,
    on_key = on_key,
    on_close = on_close,
  })
  if session ~= nil then
    paint()
  end
end

-- Jump to level *n* (clamped); keeps the completed list and totals.
function mod.load_level(n)
  ensure_state()
  load_level(n)
end

-- The test seam: everything a test needs without reading the canvas.
function mod.snapshot()
  if state == nil then
    return {}
  end
  local boxes = {}
  local goal_count = 0
  for _, row in ipairs(state.cells) do
    for _, cell in ipairs(row) do
      if cell == "." then
        goal_count = goal_count + 1
      end
    end
  end
  for _, box in ipairs(state.boxes) do
    boxes[#boxes + 1] = {
      x = box.x,
      y = box.y,
      on_goal = is_goal(box.x, box.y),
    }
  end
  return {
    level = state.level,
    total = #LEVELS,
    moves = state.moves,
    pushes = state.pushes,
    solved = state.solved,
    paused = state.paused,
    player_x = state.player.x,
    player_y = state.player.y,
    boxes = boxes,
    goals = goal_count,
    completed = state.completed,
    undo_depth = #state.undo,
  }
end

function mod.setup(_api)
  -- Reset leftovers from a previous load of this file in the same runtime.
  session = nil
  state = nil
  engine.register("sokoban", start)
end

function mod.teardown(_api)
  if state ~= nil then
    save_progress()
  end
  local open = session
  session = nil
  if open ~= nil then
    open.close()
  end
end

return mod
