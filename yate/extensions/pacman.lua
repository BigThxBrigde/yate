--[[
yate bundled extension: pacman (pacman.lua)

A classic pacman maze drawn on a yate extension canvas: a 39 x 23 ASCII
maze (walls / pellets / power pellets / ghost house) drawn edge to edge on
a 39 x 23 canvas, a wrap-around tunnel on row 14, four deterministic
ghosts, power pellets that turn the ghosts frightened, and a bottom
status line (score / lives / level / best / legend).

Start it with ``:game pacman``.

Controls:
  arrows / hjkl / wasd   request a direction (buffered until the next step)
  p                      pause / resume
  r                      restart at level 1 (fresh maze, score 0, 3 lives)
  escape                 exit the canvas (consumed by the canvas itself)

Rules: pacman walks one tile every PAC_EVERY ticks, ghosts one tile every
GHOST_EVERY ticks (every FRIGHT_EVERY while frightened).  The ghost AI is
strictly deterministic: no math.random anywhere -- chase ghosts step to
the walkable neighbour (reverse forbidden unless forced) minimising the
manhattan distance to pacman, frightened ghosts maximise it, eyes walk
the BFS shortest path back to the ghost-house door; ties resolve in the
fixed order up, left, down, right.  A power pellet sets fright_ticks = 60
and every eaten ghost scores 200 * 2^n for the n-th ghost of that fright.
Losing the last life ends the run and records the score; clearing every
pellet advances the level, restores the maze and awards a bonus.

Persistence goes through the shared engine: ``games/pacman.json`` keeps
the top-5 high scores (with player names) plus the stats block.

Entry form: module-table style -- this file returns ``mod`` and yate calls
``mod.setup(api)`` at load and ``mod.teardown(api)`` on unload.
]]

local engine = require("game_engine")

-- Canvas geometry: the canvas IS the maze, 39 x 23 single-byte rows.
local COLS, ROWS = 39, 23
local MAZE_W, MAZE_H = 39, 23

-- Speed / scoring constants (ticks are canvas clock ticks).
local PAC_EVERY = 4
local GHOST_EVERY = 5
local FRIGHT_EVERY = 7
local FRIGHT_TICKS = 60
local LEVEL_BONUS = 500
local START_LIVES = 3
local CLEAR_FREEZE = 30

-- Fixed tie-break order for the ghost AI: up, left, down, right.
local DIRS = {
  { x = 0, y = -1 },
  { x = -1, y = 0 },
  { x = 0, y = 1 },
  { x = 1, y = 0 },
}

-- Glyph vocabulary (Unicode only; ASCII stays inside the maze data).
local G_WALL = "█"
local G_DOT = "·"
local G_BIG = "●"
local G_DOOR = "▒"
local G_PAC = "◉"
local G_GHOSTS = { "▲", "△", "▴", "▵" }
local G_FRIGHT = "◆"
local G_EYES = "◌"

local PALETTE = {
  [G_WALL] = "#1e3a8a",
  [G_DOT] = "#f5f5dc",
  [G_BIG] = "#f5f5dc",
  [G_DOOR] = "#f5f5dc",
  [G_PAC] = "#ffd54f",
  [G_GHOSTS[1]] = "#e53935",
  [G_GHOSTS[2]] = "#f06292",
  [G_GHOSTS[3]] = "#4dd0e1",
  [G_GHOSTS[4]] = "#ffb74d",
  [G_FRIGHT] = "#64b5f6",
  [G_EYES] = "#f5f5dc",
}

-- Ghost points for the n-th ghost eaten during one fright phase (0-based).
local GHOST_POINTS = { 200, 400, 800, 1600 }

-- BFS distance treated as "unreachable" for the eyes mode.
local UNREACHABLE = 9999

-- The built-in maze: 23 rows x 39 columns, pure ASCII, left-right symmetric.
-- '#' wall, '.' pellet, 'o' power pellet, '-' ghost door, ' ' empty,
-- 'P' pacman spawn, 'G' ghost-house interior (becomes empty at runtime).
-- Row 14 is the wrap-around tunnel: both edge cells are open pellets.
local BUILTIN_MAZE = {
  "#######################################",
  "#o...................................o#",
  "#........#...................#........#",
  "#........#...................#........#",
  "#........#...................#........#",
  "#.....................................#",
  "#........#...................#........#",
  "#..####.####...............####.####..#",
  "#........#......#######......#........#",
  "#...............#GGGGG#...............#",
  "#........#......#GGGGG#......#........#",
  "#..####.#####.###GGGGG###.#####.####..#",
  "#..............####-####..............#",
  ".......................................",
  "#..............#.......#..............#",
  "#.......#####.###.....###.#####.......#",
  "#..............#.......#..............#",
  "#.....................................#",
  "#.....................................#",
  "#.......#####.###.....###.#####.......#",
  "#.....................................#",
  "#o.................P.................o#",
  "#######################################",
}

-- Game state (rebuilt by new_game()); nil until the first start.
local state = nil

-- The open canvas session; nil while no canvas is open.
local session = nil

-- The active maze rows (built-in or injected through set_maze).
local maze_rows = BUILTIN_MAZE

-- Shared persistence handles (one document, one score board).
local store = engine.store("pacman")
local board = engine.scores("pacman")

local mod = {}

-- --------------------------------------------------------------------- maze

-- Parse maze rows into runtime cells plus spawns, door and a BFS map of
-- the distances to the door (for the eyes mode).
local function parse_maze(rows)
  local cells = {}
  local pac_start = nil
  local door = nil
  local house = {}
  for y = 1, #rows do
    local row = rows[y]
    cells[y] = {}
    for x = 1, #row do
      local char = row:sub(x, x)
      if char == "P" then
        pac_start = { x = x, y = y }
        char = " "
      elseif char == "G" then
        house[#house + 1] = { x = x, y = y }
        char = " "
      elseif char == "-" and door == nil then
        door = { x = x, y = y }
      end
      cells[y][x] = char
    end
  end
  local dist = {}
  for y = 1, #rows do
    dist[y] = {}
  end
  local width = 0
  for _, row in ipairs(rows) do
    if #row > width then
      width = #row
    end
  end
  if door ~= nil then
    dist[door.y][door.x] = 0
    local queue = { door }
    local head = 1
    while queue[head] ~= nil do
      local cell = queue[head]
      head = head + 1
      local here = dist[cell.y][cell.x]
      for _, step in ipairs(DIRS) do
        -- Horizontal neighbours wrap across the tunnel edges too.
        local nx = cell.x + step.x
        if nx < 1 then
          nx = width
        elseif nx > width then
          nx = 1
        end
        local ny = cell.y + step.y
        local row = cells[ny]
        if row ~= nil and row[nx] ~= nil and row[nx] ~= "#"
          and dist[ny][nx] == nil then
          dist[ny][nx] = here + 1
          queue[#queue + 1] = { x = nx, y = ny }
        end
      end
    end
  end
  local pellet_count = 0
  for y = 1, #rows do
    for x = 1, width do
      local char = cells[y][x]
      if char == "." or char == "o" then
        pellet_count = pellet_count + 1
      end
    end
  end
  return {
    cells = cells,
    w = width,
    h = #rows,
    pac_start = pac_start,
    door = door,
    house = house,
    dist = dist,
    pellet_count = pellet_count,
  }
end

-- True when pacman may enter (x, y).
local function walkable(x, y)
  local row = state.parsed.cells[y]
  if row == nil or row[x] == nil then
    return false
  end
  local char = row[x]
  return char ~= "#" and char ~= "-"
end

-- True when a ghost may enter (x, y); eyes may use the door.
local function ghost_walkable(x, y, eyes)
  local row = state.parsed.cells[y]
  if row == nil or row[x] == nil then
    return false
  end
  local char = row[x]
  if char == "#" then
    return false
  end
  return eyes or char ~= "-"
end

-- Deterministic ghost spawn cells: open, pellet-free cells first, then
-- any open cell; never the pacman start.  Scan order is row-major.
local function spawn_positions(parsed)
  local spare = {}
  local any = {}
  for y = 1, #parsed.cells do
    for x = 1, parsed.w do
      local char = parsed.cells[y][x]
      if char ~= "#" then
        local start = parsed.pac_start
        local is_start = start ~= nil and start.x == x and start.y == y
        if not is_start then
          local spot = { x = x, y = y }
          any[#any + 1] = spot
          if char ~= "." and char ~= "o" then
            spare[#spare + 1] = spot
          end
        end
      end
    end
  end
  local list = spare
  if #list == 0 then
    list = any
  end
  if #list == 0 then
    list = { parsed.pac_start or { x = 1, y = 1 } }
  end
  local out = {}
  for index = 1, 4 do
    local spot = list[((index - 1) % #list) + 1]
    out[index] = { x = spot.x, y = spot.y }
  end
  return out
end

-- -------------------------------------------------------------------- state

-- Add points and keep the displayed best in sync.
local function add_score(points)
  state.score = state.score + points
  if state.score > state.best then
    state.best = state.score
  end
end

-- Put pacman and the ghosts back on their spawn cells (pellets stay).
local function reset_positions()
  local start = state.parsed.pac_start or { x = 1, y = 1 }
  state.pac = { x = start.x, y = start.y, dir = { x = -1, y = 0 } }
  state.pending = nil
  state.ghosts = {}
  for index, spot in ipairs(spawn_positions(state.parsed)) do
    state.ghosts[index] = {
      x = spot.x,
      y = spot.y,
      dir = { x = 0, y = -1 },
      mode = "chase",
      count = 0,
    }
  end
  state.fright_ticks = 0
  state.fright_eaten = 0
  state.tick = 0
end

-- Fresh run: level 1, full lives, parsed maze, restored pellets.
local function new_game()
  state = {
    parsed = parse_maze(maze_rows),
    score = 0,
    lives = START_LIVES,
    level = 1,
    run_levels = 0,
    scored = false,
    alive = true,
    paused = false,
    freeze = 0,
    best = board.best(),
  }
  state.pellets = state.parsed.pellet_count
  reset_positions()
end

-- ----------------------------------------------------------------- scoring

-- Record the finished run once: score board entry plus stats.
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
  stats.levels = (stats.levels or 0) + (state.run_levels or 0)
  document.version = engine.VERSION
  document.stats = stats
  store.save(document)
end

-- Pacman and a chase ghost met: burn one life (or end the run).
local function lose_life()
  state.lives = state.lives - 1
  state.fright_ticks = 0
  state.fright_eaten = 0
  if state.lives <= 0 then
    state.alive = false
    record_run()
  else
    reset_positions()
  end
end

-- ---------------------------------------------------------------- movement

-- Wrap a horizontal coordinate across the maze edges (the tunnel row);
-- on rows whose edges are walls the wrapped cell is simply not walkable.
local function wrap_x(nx)
  local width = state.parsed.w
  if nx < 1 then
    return width
  elseif nx > width then
    return 1
  end
  return nx
end

-- Step pacman one tile; eat pellets / power pellets along the way.
local function move_pac()
  local pac = state.pac
  if state.pending ~= nil
    and walkable(wrap_x(pac.x + state.pending.x),
      pac.y + state.pending.y) then
    pac.dir = state.pending
    state.pending = nil
  end
  local target_x = wrap_x(pac.x + pac.dir.x)
  if not walkable(target_x, pac.y + pac.dir.y) then
    return
  end
  pac.x = target_x
  pac.y = pac.y + pac.dir.y
  local char = state.parsed.cells[pac.y][pac.x]
  if char == "." then
    state.parsed.cells[pac.y][pac.x] = " "
    state.pellets = state.pellets - 1
    add_score(10)
  elseif char == "o" then
    state.parsed.cells[pac.y][pac.x] = " "
    state.pellets = state.pellets - 1
    add_score(50)
    state.fright_ticks = FRIGHT_TICKS
    state.fright_eaten = 0
    for _, ghost in ipairs(state.ghosts) do
      if ghost.mode ~= "eyes" then
        ghost.mode = "fright"
      end
    end
  end
end

-- Level cleared: bonus, next level, restored maze, actors back home.
local function check_level_clear()
  if state.pellets > 0 then
    return
  end
  add_score(LEVEL_BONUS)
  state.level = state.level + 1
  state.run_levels = state.run_levels + 1
  state.parsed = parse_maze(maze_rows)
  state.pellets = state.parsed.pellet_count
  reset_positions()
  state.freeze = CLEAR_FREEZE
end

-- Pick the ghost's next step (deterministic; ties keep DIRS order).
local function choose_ghost_step(ghost)
  local eyes = ghost.mode == "eyes"
  local reverse = { x = -ghost.dir.x, y = -ghost.dir.y }
  local candidates = {}
  local fallback = nil
  for _, step in ipairs(DIRS) do
    local nx = wrap_x(ghost.x + step.x)
    local ny = ghost.y + step.y
    if ghost_walkable(nx, ny, eyes) then
      local move = { x = nx, y = ny, dx = step.x, dy = step.y }
      if step.x == reverse.x and step.y == reverse.y then
        fallback = move
      else
        candidates[#candidates + 1] = move
      end
    end
  end
  if #candidates == 0 and fallback ~= nil then
    candidates[1] = fallback
  end
  local best = nil
  local best_value = nil
  for _, move in ipairs(candidates) do
    local value = UNREACHABLE
    if eyes and state.parsed.door ~= nil then
      local row = state.parsed.dist[move.y]
      if row ~= nil and row[move.x] ~= nil then
        value = row[move.x]
      end
    else
      value = math.abs(move.x - state.pac.x)
        + math.abs(move.y - state.pac.y)
    end
    local better = best == nil
      or (ghost.mode == "fright" and value > best_value)
      or (ghost.mode ~= "fright" and value < best_value)
    if better then
      best = move
      best_value = value
    end
  end
  return best
end

-- Move one ghost and revive it once the eyes reach the house door.
local function move_ghost(ghost)
  local step = choose_ghost_step(ghost)
  if step == nil then
    return
  end
  ghost.x = step.x
  ghost.y = step.y
  ghost.dir = { x = step.dx, y = step.dy }
  local door = state.parsed.door
  if ghost.mode == "eyes" and door ~= nil
    and ghost.x == door.x and ghost.y == door.y then
    ghost.mode = "chase"
    ghost.count = 0
    local home = state.parsed.house[1]
    if home ~= nil then
      ghost.x = home.x
      ghost.y = home.y
    end
  end
end

-- Resolve pacman / ghost meetings (same cell only).
local function check_collisions()
  local pac = state.pac
  for _, ghost in ipairs(state.ghosts) do
    if ghost.x == pac.x and ghost.y == pac.y then
      if ghost.mode == "fright" then
        local points = GHOST_POINTS[state.fright_eaten + 1]
        if points == nil then
          points = GHOST_POINTS[#GHOST_POINTS]
        end
        state.fright_eaten = state.fright_eaten + 1
        add_score(points)
        ghost.mode = "eyes"
      elseif ghost.mode == "chase" then
        lose_life()
        return
      end
    end
  end
end

-- ---------------------------------------------------------------- rendering

-- The glyph of one maze cell before the actors are drawn on top.
local function cell_glyph(x, y)
  local char = state.parsed.cells[y][x]
  if char == "#" then
    return G_WALL
  elseif char == "." then
    return G_DOT
  elseif char == "o" then
    return G_BIG
  elseif char == "-" then
    return G_DOOR
  end
  return " "
end

-- One maze row as `parsed.w` single-width glyphs, ghosts then pacman on top.
local function maze_line(index)
  local cells = {}
  for x = 1, state.parsed.w do
    cells[x] = cell_glyph(x, index)
  end
  for i, ghost in ipairs(state.ghosts) do
    if ghost.y == index then
      if ghost.mode == "eyes" then
        cells[ghost.x] = G_EYES
      elseif ghost.mode == "fright" then
        cells[ghost.x] = G_FRIGHT
      else
        cells[ghost.x] = G_GHOSTS[i]
      end
    end
  end
  if state.pac.y == index then
    cells[state.pac.x] = G_PAC
  end
  return table.concat(cells)
end

-- Centered overlay text replacing one maze row (maze width in columns).
local function overlay_line(_index, text)
  return engine.center(text, state.parsed.w)
end

-- Render the whole canvas as one newline-joined string: the maze rows
-- themselves, no outer frame (the canvas is exactly the maze).  The maze
-- sizes itself from the active maze (built-in or injected), so tests can
-- inject small mazes on the same canvas.
local function render()
  local h = state.parsed.h
  local mid = math.floor(h / 2)
  local lines = {}
  for y = 1, h do
    local content
    if not state.alive and y == mid then
      content = overlay_line(y, "game over")
    elseif not state.alive and y == mid + 2 then
      content = overlay_line(y, "press r")
    elseif state.freeze > 0 and y == mid + 1 then
      content = overlay_line(y, "level cleared")
    elseif state.paused and y == mid + 1 then
      content = overlay_line(y, "paused")
    else
      content = maze_line(y)
    end
    lines[#lines + 1] = content
  end
  return table.concat(lines, "\n")
end

-- Push the current frame and status line to the canvas.
local function paint()
  if session == nil then
    return
  end
  session.status(
    "score " .. state.score
      .. "  lives " .. state.lives
      .. "  level " .. state.level
      .. "  best " .. state.best
      .. "  ◉ you ▲ ghost ◆ fear · dot"
  )
  session.paint()
end

-- ---------------------------------------------------------------- callbacks

local function on_key(key)
  if state == nil or session == nil then
    return
  end
  if key == "r" then
    new_game()
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
  if dx ~= nil then
    state.pending = { x = dx, y = dy }
    paint()
  end
end

local function on_tick()
  if state == nil or session == nil then
    return
  end
  if state.alive and not state.paused then
    if state.freeze > 0 then
      state.freeze = state.freeze - 1
    else
      state.tick = state.tick + 1
      if state.tick % PAC_EVERY == 0 then
        move_pac()
        check_collisions()
        check_level_clear()
      end
      if state.alive then
        for _, ghost in ipairs(state.ghosts) do
          local every = ghost.mode == "fright" and FRIGHT_EVERY or GHOST_EVERY
          ghost.count = ghost.count + 1
          if ghost.count >= every then
            ghost.count = 0
            move_ghost(ghost)
          end
        end
        check_collisions()
      end
      if state.fright_ticks > 0 then
        state.fright_ticks = state.fright_ticks - 1
        if state.fright_ticks == 0 then
          for _, ghost in ipairs(state.ghosts) do
            if ghost.mode == "fright" then
              ghost.mode = "chase"
            end
          end
        end
      end
    end
  end
  paint()
end

-- Closing the canvas: flush an unfinished run and ensure the document.
local function on_close()
  session = nil
  if state ~= nil and not state.scored and state.score > 0 then
    record_run()
  end
  if store.load() == nil then
    store.save({
      version = engine.VERSION,
      player = engine.player(),
      high_scores = {},
      stats = { games = 0, levels = 0 },
    })
  end
end

-- ----------------------------------------------------------------- module API

-- Start a fresh game on a new canvas (the engine guards double launches).
local function start()
  new_game()
  session = engine.open({
    name = "pacman",
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

-- Kept for the shared seam; this game's AI never randomizes.
function mod.set_seed(_value) end

-- Swap the maze (nil restores the built-in one) and re-parse it.
function mod.set_maze(rows)
  if rows == nil then
    maze_rows = BUILTIN_MAZE
  else
    maze_rows = rows
  end
  if state ~= nil then
    state.parsed = parse_maze(maze_rows)
    state.pellets = state.parsed.pellet_count
    reset_positions()
  end
end

-- Inject a test position: score / lives / level / pac / ghosts.
function mod.set_state(spec)
  if state == nil or type(spec) ~= "table" then
    return
  end
  if type(spec.score) == "number" then
    state.score = spec.score
  end
  if type(spec.lives) == "number" then
    state.lives = spec.lives
  end
  if type(spec.level) == "number" then
    state.level = spec.level
  end
  if type(spec.pac) == "table" then
    if type(spec.pac.x) == "number" then
      state.pac.x = spec.pac.x
    end
    if type(spec.pac.y) == "number" then
      state.pac.y = spec.pac.y
    end
    if type(spec.pac.dir) == "table" then
      state.pac.dir = { x = spec.pac.dir.x, y = spec.pac.dir.y }
    end
  end
  if type(spec.ghosts) == "table" then
    for index = 1, #spec.ghosts do
      local ghost = state.ghosts[index]
      local want = spec.ghosts[index]
      if ghost ~= nil and type(want) == "table" then
        if type(want.x) == "number" then
          ghost.x = want.x
        end
        if type(want.y) == "number" then
          ghost.y = want.y
        end
        ghost.mode = want.mode or "chase"
        ghost.count = 0
      end
    end
  end
  state.pending = nil
  state.tick = 0
  state.alive = state.lives > 0
end

-- The test seam: everything a test needs without reading the canvas.
function mod.snapshot()
  if state == nil then
    return {}
  end
  local ghosts = {}
  for _, ghost in ipairs(state.ghosts) do
    ghosts[#ghosts + 1] = { x = ghost.x, y = ghost.y, mode = ghost.mode }
  end
  return {
    score = state.score,
    lives = state.lives,
    level = state.level,
    pellets = state.pellets,
    pac_x = state.pac.x,
    pac_y = state.pac.y,
    pac_dir_x = state.pac.dir.x,
    pac_dir_y = state.pac.dir.y,
    fright_ticks = state.fright_ticks,
    ghosts = ghosts,
    alive = state.alive,
    paused = state.paused,
    best = state.best,
  }
end

function mod.setup(_api)
  -- Reset leftovers from a previous load of this file in the same runtime.
  session = nil
  state = nil
  maze_rows = BUILTIN_MAZE
  engine.register("pacman", start)
end

function mod.teardown(_api)
  local open = session
  session = nil
  if open ~= nil then
    open.close()
  end
end

return mod
