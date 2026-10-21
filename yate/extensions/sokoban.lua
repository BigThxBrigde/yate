--[[
yate bundled extension: sokoban (sokoban.lua)

A classic sokoban drawn on a yate extension canvas: a 37 x 17 level area
inside a rounded 41 x 22 frame, a HUD row (level / moves / pushes / done)
and two help rows above the bottom border.  Walls are blue blocks, crates
brown, crates on goals green, goals grey and the player yellow.

Start it with ``:game sokoban``.

Levels: 1-6 are the built-in handwritten set (Microban 1-5 plus a teaching
level).  Levels 7-120 are produced on demand by a reverse-pull generator
(see the "level generator" section): it starts from an already-solved board
and only performs legal pulls, so inverting the pull trace is guaranteed to
be a valid pushing solution for the resulting board.  Generated levels are
built lazily on first use and cached, never all at startup.

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

-- Canvas geometry: 41 x 22, inner width 39, level area 37 x 17.
-- Row structure: top border (1) + level area (17) + HUD (1) + help (2)
-- + bottom border (1) = 22.
local COLS, ROWS = 41, 22
local INNER = 39
local AREA_W, AREA_H = 37, 17

--: Total level count: 6 handwritten + 114 generated.
local TOTAL = 120

--: Number of handwritten levels at the front of the set.
local HANDWRITTEN = 6

-- Undo history cap; the oldest entry is dropped beyond it.
local MAX_UNDO = 200

-- The level area row carrying overlay text (paused / cleared).
local OVERLAY_ROW = 6

-- Two help rows between the HUD and the bottom border: four full words do
-- not fit on one 39-column line.
local HELP_LINES = { "u undo  r restart", "n next  p pause" }

--: Built-in levels 1-6: 1-5 from the public Microban set, 6 a teaching level.
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

-- ------------------------------------------------------------ level generator

--: Generated levels keyed by index; filled on demand (never at startup).
local LEVEL_CACHE = {}

--: The four step directions shared by walks and pulls.
local DIRS = { { -1, 0 }, { 1, 0 }, { 0, -1 }, { 0, 1 } }

--: Key used to hash a cell (x, y) into one integer.
local function cell_key(x, y)
  return y * 64 + x
end

--: The index of the crate at (x, y) inside *boxes*, or nil.
local function box_index_at(boxes, x, y)
  for index, box in ipairs(boxes) do
    if box.x == x and box.y == y then
      return index
    end
  end
  return nil
end

-- Shortest walk from (sx, sy) to (tx, ty) with crates as obstacles; returns
-- the list of {dx, dy, push = false} steps in walking order, or nil when
-- the target is unreachable.  The search stays inside the 37 x 17 area
-- (629 cells at most).
local function walk_steps(grid, boxes, sx, sy, tx, ty)
  if sx == tx and sy == ty then
    return {}
  end
  local blocked = {}
  for _, box in ipairs(boxes) do
    blocked[cell_key(box.x, box.y)] = true
  end
  local came = {}
  came[cell_key(sx, sy)] = false -- visited marker (the start has no parent)
  local queue = { { x = sx, y = sy } }
  local head = 1
  while head <= #queue do
    local cell = queue[head]
    head = head + 1
    for _, dir in ipairs(DIRS) do
      local nx, ny = cell.x + dir[1], cell.y + dir[2]
      local key = cell_key(nx, ny)
      if came[key] == nil and grid[ny] ~= nil and grid[ny][nx]
        and not blocked[key] then
        came[key] = { x = cell.x, y = cell.y, dx = dir[1], dy = dir[2] }
        if nx == tx and ny == ty then
          local reversed = {}
          local cursor = key
          while came[cursor] ~= false do
            local parent = came[cursor]
            reversed[#reversed + 1] = { dx = parent.dx, dy = parent.dy, push = false }
            cursor = cell_key(parent.x, parent.y)
          end
          local steps = {}
          for index = #reversed, 1, -1 do
            steps[#steps + 1] = reversed[index]
          end
          return steps
        end
        queue[#queue + 1] = { x = nx, y = ny }
      end
    end
  end
  return nil
end

-- Build one 37 x 17 room: solid walls, the corridor region (x 2..36,
-- y 2..16) carved out, then *pillar_count* single-cell pillars placed at
-- random interior cells that never touch each other (not even diagonally).
local function build_room(rng, pillar_count)
  local grid = {}
  for y = 1, AREA_H do
    grid[y] = {}
    for x = 1, AREA_W do
      grid[y][x] = false
    end
  end
  for y = 2, AREA_H - 1 do
    for x = 2, AREA_W - 1 do
      grid[y][x] = true
    end
  end
  local pillars = {}
  local placed = 0
  local tries = 0
  while placed < pillar_count and tries < 200 do
    tries = tries + 1
    local x = 2 + rng.int(AREA_W - 2)
    local y = 2 + rng.int(AREA_H - 2)
    if grid[y][x] then
      local clear = true
      for dy = -1, 1 do
        for dx = -1, 1 do
          if pillars[cell_key(x + dx, y + dy)] then
            clear = false
          end
        end
      end
      if clear then
        grid[y][x] = false
        pillars[cell_key(x, y)] = true
        placed = placed + 1
      end
    end
  end
  return grid
end

-- True when every walkable cell of *grid* is reachable from one of them.
local function room_connected(grid)
  local start = nil
  local total = 0
  for y = 2, AREA_H - 1 do
    for x = 2, AREA_W - 1 do
      if grid[y][x] then
        total = total + 1
        if start == nil then
          start = { x = x, y = y }
        end
      end
    end
  end
  local seen = {}
  seen[cell_key(start.x, start.y)] = true
  local queue = { start }
  local head = 1
  local reached = 0
  while head <= #queue do
    local cell = queue[head]
    head = head + 1
    reached = reached + 1
    for _, dir in ipairs(DIRS) do
      local nx, ny = cell.x + dir[1], cell.y + dir[2]
      local key = cell_key(nx, ny)
      if not seen[key] and grid[ny] ~= nil and grid[ny][nx] then
        seen[key] = true
        queue[#queue + 1] = { x = nx, y = ny }
      end
    end
  end
  return reached == total
end

-- Walkable cells whose four neighbours are walkable too (goal candidates).
local function goal_candidates(grid)
  local out = {}
  for y = 2, AREA_H - 1 do
    for x = 2, AREA_W - 1 do
      if grid[y][x] and grid[y][x - 1] and grid[y][x + 1]
        and grid[y - 1] ~= nil and grid[y - 1][x] and grid[y + 1][x] then
        out[#out + 1] = { x = x, y = y }
      end
    end
  end
  return out
end

-- Pick *count* distinct goal cells from the candidates; nil when too few.
local function pick_goals(rng, grid, count)
  local candidates = goal_candidates(grid)
  local out = {}
  while #out < count and #candidates > 0 do
    local index = rng.int(#candidates)
    out[#out + 1] = candidates[index]
    table.remove(candidates, index)
  end
  if #out < count then
    return nil
  end
  return out
end

-- A random walkable cell without a crate on it.
local function random_free_cell(rng, grid, boxes)
  local out = {}
  for y = 2, AREA_H - 1 do
    for x = 2, AREA_W - 1 do
      if grid[y][x] and box_index_at(boxes, x, y) == nil then
        out[#out + 1] = { x = x, y = y }
      end
    end
  end
  return rng.pick(out)
end

-- One reverse pull: pick a random crate and direction, walk the player
-- next to the crate (bounded BFS, crates as obstacles) and pull it one
-- cell; every step is appended to *ops* ({dx, dy, push}, the pull itself
-- with push = true).  At most 8 attempts per call; false when none worked.
local function pull_once(rng, grid, boxes, player, ops)
  for _ = 1, 8 do
    local box = boxes[rng.int(#boxes)]
    local dir = DIRS[rng.int(4)]
    local mx, my = box.x + dir[1], box.y + dir[2]
    local px, py = box.x + 2 * dir[1], box.y + 2 * dir[2]
    if grid[my] ~= nil and grid[my][mx] and grid[py] ~= nil and grid[py][px]
      and box_index_at(boxes, mx, my) == nil
      and box_index_at(boxes, px, py) == nil then
      local steps = walk_steps(grid, boxes, player.x, player.y, mx, my)
      if steps ~= nil then
        for _, step in ipairs(steps) do
          ops[#ops + 1] = step
          player.x, player.y = player.x + step.dx, player.y + step.dy
        end
        box.x, box.y = mx, my
        player.x, player.y = px, py
        ops[#ops + 1] = { dx = dir[1], dy = dir[2], push = true }
        return true
      end
    end
  end
  return false
end

-- Render the generated room as ASCII rows (`# . $ * @ +`), one string per
-- row, exactly AREA_H rows of AREA_W cells.
local function room_rows(grid, goals, boxes, player)
  local chars = {}
  for y = 1, AREA_H do
    chars[y] = {}
    for x = 1, AREA_W do
      chars[y][x] = grid[y][x] and " " or "#"
    end
  end
  for _, goal in ipairs(goals) do
    chars[goal.y][goal.x] = "."
  end
  for _, box in ipairs(boxes) do
    chars[box.y][box.x] = chars[box.y][box.x] == "." and "*" or "$"
  end
  chars[player.y][player.x] = chars[player.y][player.x] == "." and "+" or "@"
  local rows = {}
  for y = 1, AREA_H do
    rows[y] = table.concat(chars[y])
  end
  return rows
end

-- True when every crate still sits on a goal (nothing was ever pulled off,
-- or the pulls happened to permute the crates between the goals).
local function all_boxes_on_goals(boxes, goals)
  for _, goal in ipairs(goals) do
    if box_index_at(boxes, goal.x, goal.y) == nil then
      return false
    end
  end
  return true
end

-- One generation attempt for *index*; nil when the attempt degenerated
-- (disconnected room, or every crate still on a goal after pulling).
local function attempt_generation(rng, index)
  local grid = build_room(rng, 4 + rng.int(7))
  if not room_connected(grid) then
    return nil
  end
  local goals = pick_goals(rng, grid, 2 + index % 4)
  if goals == nil then
    return nil
  end
  local boxes = {}
  for _, goal in ipairs(goals) do
    boxes[#boxes + 1] = { x = goal.x, y = goal.y }
  end
  local player = random_free_cell(rng, grid, boxes)
  if player == nil then
    return nil
  end
  local ops = {}
  for _ = 1, 30 + index % 30 do
    if not pull_once(rng, grid, boxes, player, ops) then
      break
    end
  end
  if all_boxes_on_goals(boxes, goals) then
    return nil
  end
  return { rows = room_rows(grid, goals, boxes, player), ops = ops }
end

-- Degenerate fallback: an empty room, two goals, at most three pulls.
local function simple_level(rng)
  for _ = 1, 30 do
    local grid = build_room(rng, 0)
    if room_connected(grid) then
      local goals = pick_goals(rng, grid, 2)
      if goals ~= nil then
        local boxes = {}
        for _, goal in ipairs(goals) do
          boxes[#boxes + 1] = { x = goal.x, y = goal.y }
        end
        local player = random_free_cell(rng, grid, boxes)
        if player ~= nil then
          local ops = {}
          for _ = 1, 3 do
            if not pull_once(rng, grid, boxes, player, ops) then
              break
            end
          end
          if not all_boxes_on_goals(boxes, goals) then
            return { rows = room_rows(grid, goals, boxes, player), ops = ops }
          end
        end
      end
    end
  end
  -- Static last resort: one hand-computed pull in an empty room, verified
  -- to be solvable by construction (the crate ends one cell off its goal).
  local grid = build_room(rng, 0)
  local goals = { { x = 4, y = 5 }, { x = 4, y = 8 } }
  local boxes = { { x = 4, y = 5 }, { x = 4, y = 8 } }
  local player = { x = 9, y = 5 }
  local ops = {}
  local function step(dx, dy)
    ops[#ops + 1] = { dx = dx, dy = dy, push = false }
    player.x, player.y = player.x + dx, player.y + dy
  end
  step(0, 1) -- step off the crate row
  for _ = 1, 6 do
    step(-1, 0) -- walk left below the crates
  end
  step(0, -1) -- stand left of the first crate
  boxes[1].x = 5 -- pull the crate at (4, 5) one cell to the right
  player.x, player.y = 4, 5
  ops[#ops + 1] = { dx = 1, dy = 0, push = true }
  return { rows = room_rows(grid, goals, boxes, player), ops = ops }
end

-- Generate level *index* (7..TOTAL).  Every attempt shares one seeded RNG,
-- so a level is always the same deterministic sequence of boards.
local function generate_level(index)
  local rng = engine.rng(9000 + index)
  for _ = 1, 30 do
    local level = attempt_generation(rng, index)
    if level ~= nil then
      return level
    end
  end
  return simple_level(rng)
end

-- The raw ASCII rows of level *index*; generated levels are built (and
-- cached) on first access, never at startup.
local function rows_for_level(index)
  if index <= HANDWRITTEN then
    return LEVELS[index]
  end
  local cached = LEVEL_CACHE[index]
  if cached == nil then
    cached = generate_level(index)
    LEVEL_CACHE[index] = cached
  end
  return cached.rows
end

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

-- Load level *n* (clamped to 1..TOTAL); totals and completed survive.
local function load_level(number)
  local index = math.floor(tonumber(number) or 1)
  if index < 1 then
    index = 1
  end
  if index > TOTAL then
    index = TOTAL
  end
  local cells, boxes, player = parse_level(rows_for_level(index))
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

-- Drop *level* from the completed list again (an undo left the solved state).
local function unmark_completed(level)
  for index, done in ipairs(state.completed) do
    if done == level then
      table.remove(state.completed, index)
      return
    end
  end
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
      level = math.min(state.level + 1, TOTAL)
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
      if type(level) == "number" and level >= 1 and level <= TOTAL then
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

-- True while every goal holds a crate (the current board state).
local function board_solved()
  for y, row in ipairs(state.cells) do
    for x, cell in ipairs(row) do
      if cell == "." and box_at(x, y) == nil then
        return false
      end
    end
  end
  return true
end

-- Keep state.solved in sync with the board: a push can both solve the level
-- and pull a crate off a goal again, and the completed list must follow.
local function sync_solved()
  local solved = board_solved()
  if solved == state.solved then
    return
  end
  state.solved = solved
  if solved then
    mark_completed(state.level)
  else
    unmark_completed(state.level)
  end
  save_progress()
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
  sync_solved()
end

-- Undo one step: the player and the pushed crate return to their cells.
-- A solve undone this way is rolled back too, so `n` cannot skip a level.
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
  sync_solved()
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
  if state.level >= TOTAL then
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

-- One level-area row as AREA_W single-width glyph cells (never byte-spliced).
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
  return "level " .. state.level .. "/" .. TOTAL
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
      -- one blank gutter column between the frame and the 37-wide area
      rows[#rows + 1] = G.v .. " " .. engine.pad(area_row(ly), AREA_W) .. " " .. G.v
    end
  end
  rows[#rows + 1] = G.v .. engine.pad(hud_text(), INNER) .. G.v
  for _, line in ipairs(HELP_LINES) do
    rows[#rows + 1] = G.v .. engine.pad(line, INNER) .. G.v
  end
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
    total = TOTAL,
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

-- The test seam: the raw ASCII rows of level *index* (handwritten or
-- generated, with generated levels built and cached on demand).
function mod.level_rows(index)
  local number = math.floor(tonumber(index) or 1)
  if number < 1 then
    number = 1
  end
  if number > TOTAL then
    number = TOTAL
  end
  return rows_for_level(number)
end

-- The test seam: the forward solution of generated level *index* as a list
-- of {dx, dy, push} steps (nil for handwritten levels).  The generator only
-- performs legal pulls starting from a solved board, so replaying this
-- trace -- the recorded pulls reversed and direction-negated, push flags
-- kept -- pushes every crate back onto its goal by construction.
function mod.solution(index)
  local number = math.floor(tonumber(index) or 0)
  if number <= HANDWRITTEN or number > TOTAL then
    return nil
  end
  rows_for_level(number) -- build and cache on demand
  local ops = LEVEL_CACHE[number].ops
  local solution = {}
  for position = #ops, 1, -1 do
    local op = ops[position]
    solution[#solution + 1] = { dx = -op.dx, dy = -op.dy, push = op.push }
  end
  return solution
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
