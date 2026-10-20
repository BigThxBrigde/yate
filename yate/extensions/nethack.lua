--[[
yate bundled extension: nethack (nethack.lua)

A turn-based roguelike drawn on a yate extension canvas: a 50 x 18 dungeon
of rooms and corridors inside a rounded 52 x 22 frame, with a HUD row
(depth / hp / gold / turn) and a help row under the map.

Start it with ``:game nethack``.

Visuals: nerd font icons by default (Font Awesome 4 codepoints through
``engine.utf8_char``), switchable to ASCII fallback with ``v``.  The map
rows are joined with ``table.concat`` -- the multi-byte glyphs never go
through byte slicing or ``engine.frame``.

Controls:
  arrows / hjkl / wasd   move one step; bumping a monster attacks it
  space                  wait one turn
  g                      grab everything under the player
  enter                  descend when standing on the stairs
  r                      new run (after death)
  v                      toggle nerd / ascii glyphs (persisted)
  escape                 exit the canvas (consumed by the canvas itself)

Determinism: ``depth`` and ``seed`` uniquely determine a floor; the world
is generated through ``engine.rng``.  Combat rolls keep their own rng
whose state travels inside the save document.

Persistence: ``games/nethack.json`` stores only semantic map characters
(``#`` wall, ``.`` floor, ``,`` corridor, ``>`` stairs) plus the player /
monster / item tables; glyphs are a pure render layer.  One save per
turn; death and ``r`` clear the store; a valid save is resumed on launch.

Entry form: module-table style -- this file returns ``mod`` and yate calls
``mod.setup(api)`` at load and ``mod.teardown(api)`` on unload.
]]

local engine = require("game_engine")

-- Canvas geometry: 52 x 22, inner width 50, map 50 x 18 tiles.
local COLS, ROWS = 52, 22
local INNER = 50
local MAP_W, MAP_H = 50, 18

-- Semantic map characters (the only characters that reach the save file).
local WALL = "#"
local FLOOR = "."
local CORRIDOR = ","
local STAIRS = ">"

-- Glyph table: nerd codepoint (Font Awesome 4 segment) plus ASCII fallback.
local GLYPHS = {
  wall = { sem = WALL, code = 0xf0c8, ascii = "#" },
  floor = { sem = FLOOR, code = 0xf111, ascii = "." },
  corr = { sem = CORRIDOR, code = 0x00b7, ascii = "#" },
  stairs = { sem = STAIRS, code = 0xf0ab, ascii = ">" },
  player = { code = 0xf007, ascii = "@" },
  paw = { code = 0xf1e4, ascii = "r" },
  fire = { code = 0xf06d, ascii = "Z" },
  gold = { code = 0xf0d6, ascii = "$" },
  potion = { code = 0xf0fc, ascii = "!" },
  weapon = { code = 0xf0e7, ascii = ")" },
  food = { code = 0xf0f5, ascii = "%" },
  tomb = { code = 0xf0f3, ascii = "+" },
}

-- Colors keyed by glyph-table name (applied to both glyph sets).
local COLORS = {
  wall = "#616161",
  corr = "#616161",
  floor = "#9e9e9e",
  stairs = "#ffffff",
  player = "#ffd54f",
  paw = "#e53935",
  fire = "#e53935",
  gold = "#ffd54f",
  potion = "#64b5f6",
  weapon = "#bdbdbd",
  food = "#7bd88f",
  tomb = "#bdbdbd",
}

-- Help row (exactly INNER wide after engine.pad).
local HELP_TEXT = "arrows move/attack  g grab  enter stairs  r new  v"

--: Bounded random seed for runs started without an injected seed.
local function random_seed()
  return math.floor(os.time()) % 1000000007
end

-- Game state (rebuilt by new_game / apply_save); nil until the first start.
local state = nil

-- Combat rng (engine.rng), separate from the per-floor generation rng.
local combat = nil

-- The open canvas session; nil while no canvas is open.
local session = nil

-- Shared persistence handle.
local store = engine.store("nethack")

local mod = {}

-- ------------------------------------------------------------------ glyphs

-- Resolve the glyph sets for *mode*: map (semantic char -> glyph) and
-- ent (glyph-table name -> glyph).  Falls back to ASCII when the runtime
-- has no utf8 library or the mode asks for it.
local function build_glyphs(mode)
  local use_nerd = mode == "nerd" and engine.utf8_char(0xf007) ~= nil
  local map, ent = {}, {}
  for name, def in pairs(GLYPHS) do
    local glyph = def.ascii
    if use_nerd then
      local nerd = engine.utf8_char(def.code)
      if nerd ~= nil then
        glyph = nerd
      end
    end
    if def.sem ~= nil then
      map[def.sem] = glyph
    end
    ent[name] = glyph
  end
  return map, ent
end

-- Palette keyed by glyph string, from the semantic color table.
local function build_palette(ent)
  local palette = {}
  for name, color in pairs(COLORS) do
    palette[ent[name]] = color
  end
  return palette
end

-- ------------------------------------------------------------------- state

-- The map character at (x, y), 1-based.
local function cell_at(x, y)
  local row = state.floor[y]
  if row == nil then
    return WALL
  end
  return row:sub(x, x) or WALL
end

-- The monster standing on (x, y), or nil.
local function monster_at(x, y)
  for _, m in ipairs(state.monsters) do
    if m.x == x and m.y == y then
      return m
    end
  end
  return nil
end

-- True when the player stands on the stairs.
local function on_stairs()
  return cell_at(state.px, state.py) == STAIRS
end

-- ------------------------------------------------------------------- world

-- One random walkable cell away from the player, or nil when the bounded
-- search runs dry.  *taken* maps "x,y" -> true for already used cells.
local function random_free_cell(gen, grid, px, py, taken, min_dist)
  for _ = 1, 200 do
    local x, y = gen.int(MAP_W), gen.int(MAP_H)
    local ch = grid[y][x]
    if (ch == FLOOR or ch == CORRIDOR) and not (x == px and y == py)
      and math.abs(x - px) + math.abs(y - py) > min_dist
      and not taken[x .. "," .. y] then
      return x, y
    end
  end
  return nil, nil
end

-- Generate the floor for the current depth and seed (deterministic):
-- non-overlapping rooms on a 12x8 grid, corridors first-horizontal then
-- vertical, stairs in the last room, player in the first room.
local function gen_floor()
  local gen = engine.rng((state.seed + state.depth * 7919) % 2147483647)
  local grid = {}
  for y = 1, MAP_H do
    grid[y] = {}
    for x = 1, MAP_W do
      grid[y][x] = WALL
    end
  end

  -- Room cells: 4 columns x 2 rows of 12x8 areas, 1 gap column/row kept.
  local cells = {}
  for gy = 0, 1 do
    for gx = 0, 3 do
      cells[#cells + 1] = { x0 = 2 + gx * 12, y0 = 2 + gy * 8 }
    end
  end
  local rooms = {}
  local want = 4 + gen.int(2)
  for _ = 1, want do
    if #cells == 0 then
      break
    end
    local index = gen.int(#cells)
    local cell = table.remove(cells, index)
    local w = 4 + gen.int(4)
    local h = 3 + gen.int(3)
    local rx = cell.x0 + gen.int(11 - w + 1)
    local ry = cell.y0 + gen.int(7 - h + 1)
    for y = ry, ry + h - 1 do
      for x = rx, rx + w - 1 do
        grid[y][x] = FLOOR
      end
    end
    rooms[#rooms + 1] = { x = rx, y = ry, w = w, h = h }
  end
  if #rooms == 0 then
    rooms[1] = { x = 2, y = 2, w = 5, h = 4 }
    for y = 2, 5 do
      for x = 2, 6 do
        grid[y][x] = FLOOR
      end
    end
  end

  -- Corridors: connect consecutive room centers, horizontal first.
  for i = 2, #rooms do
    local a, b = rooms[i - 1], rooms[i]
    local ax = a.x + math.floor(a.w / 2)
    local ay = a.y + math.floor(a.h / 2)
    local bx = b.x + math.floor(b.w / 2)
    local by = b.y + math.floor(b.h / 2)
    for x = math.min(ax, bx), math.max(ax, bx) do
      if grid[ay][x] == WALL then
        grid[ay][x] = CORRIDOR
      end
    end
    for y = math.min(ay, by), math.max(ay, by) do
      if grid[y][bx] == WALL then
        grid[y][bx] = CORRIDOR
      end
    end
  end

  -- Stairs in the last room, player in the first room.
  local last = rooms[#rooms]
  grid[last.y + gen.int(last.h) - 1][last.x + gen.int(last.w) - 1] = STAIRS
  local first = rooms[1]
  local px = first.x + math.floor(first.w / 2)
  local py = first.y + math.floor(first.h / 2)

  -- Monsters: 2 + depth, away from the player, strength rises with depth.
  local monsters = {}
  local taken = {}
  for _ = 1, 2 + state.depth do
    local mx, my = random_free_cell(gen, grid, px, py, taken, 12)
    if mx ~= nil then
      taken[mx .. "," .. my] = true
      local kind = "paw"
      if gen.int(4) <= state.depth then
        kind = "fire"
      end
      local hp = kind == "paw" and (2 + state.depth) or (4 + state.depth * 2)
      monsters[#monsters + 1] = { x = mx, y = my, kind = kind, hp = hp }
    end
  end

  -- Items: 1..4, on any free tile (never on the stairs or the player).
  local items = {}
  for _ = 1, 1 + gen.int(3) do
    local ix, iy = random_free_cell(gen, grid, px, py, taken, 0)
    if ix ~= nil and grid[iy][ix] ~= STAIRS then
      taken[ix .. "," .. iy] = true
      local roll = gen.int(4)
      local item = { x = ix, y = iy, kind = "food" }
      if roll == 1 then
        item.kind = "gold"
        item.amount = 5 + gen.int(20)
      elseif roll == 2 then
        item.kind = "potion"
      elseif roll == 3 then
        item.kind = "weapon"
      end
      items[#items + 1] = item
    end
  end

  local floor = {}
  for y = 1, MAP_H do
    floor[y] = table.concat(grid[y])
  end
  state.floor = floor
  state.px, state.py = px, py
  state.monsters = monsters
  state.items = items
end

-- A fresh run at depth 1.
local function new_game(seed, glyphs)
  state = {
    depth = 1,
    turn = 0,
    seed = seed,
    hp = 10,
    max_hp = 10,
    gold = 0,
    weapon = 0,
    glyphs = glyphs == "ascii" and "ascii" or "nerd",
    alive = true,
  }
  combat = engine.rng(seed)
  gen_floor()
end

-- -------------------------------------------------------------- persistence

-- Save one snapshot of the run (semantic characters only, one per turn).
local function save()
  if state == nil or not state.alive then
    return
  end
  local monsters = {}
  for i, m in ipairs(state.monsters) do
    monsters[i] = { x = m.x, y = m.y, kind = m.kind, hp = m.hp }
  end
  local items = {}
  for i, it in ipairs(state.items) do
    items[i] = { x = it.x, y = it.y, kind = it.kind, amount = it.amount }
  end
  store.save({
    version = 1,
    player = engine.player(),
    glyphs = state.glyphs,
    save = {
      depth = state.depth,
      turn = state.turn,
      seed = state.seed,
      hp = state.hp,
      max_hp = state.max_hp,
      gold = state.gold,
      weapon = state.weapon,
      rng = combat.state(),
      player_pos = { state.px, state.py },
      floor = state.floor,
      monsters = monsters,
      items = items,
    },
  })
end

-- True when *rows* is a MAP_H x MAP_W table of semantic map strings.
local function floor_is_valid(rows)
  if type(rows) ~= "table" or #rows ~= MAP_H then
    return false
  end
  for _, row in ipairs(rows) do
    if type(row) ~= "string" or #row ~= MAP_W then
      return false
    end
  end
  return true
end

-- Inject a save-structure table (same code path as resuming a save file).
-- Returns true on success; on failure the previous state is kept.
local function apply_save(saved, glyphs)
  if type(saved) ~= "table" or not floor_is_valid(saved.floor) then
    return false
  end
  local pos = saved.player_pos
  if type(pos) ~= "table" or type(pos[1]) ~= "number"
    or type(pos[2]) ~= "number" then
    return false
  end
  local px = math.floor(pos[1])
  local py = math.floor(pos[2])
  if px < 1 or px > MAP_W or py < 1 or py > MAP_H then
    return false
  end
  local max_hp = math.floor(tonumber(saved.max_hp) or 10)
  local hp = math.floor(tonumber(saved.hp) or 10)
  local monsters = {}
  if type(saved.monsters) == "table" then
    for _, m in ipairs(saved.monsters) do
      if type(m) == "table" and type(m.x) == "number" and type(m.y) == "number"
        and (m.kind == "paw" or m.kind == "fire") and type(m.hp) == "number" then
        monsters[#monsters + 1] = { x = m.x, y = m.y, kind = m.kind, hp = m.hp }
      end
    end
  end
  local items = {}
  if type(saved.items) == "table" then
    for _, it in ipairs(saved.items) do
      if type(it) == "table" and type(it.x) == "number" and type(it.y) == "number"
        and type(it.kind) == "string" then
        items[#items + 1] =
          { x = it.x, y = it.y, kind = it.kind, amount = it.amount }
      end
    end
  end
  state = {
    depth = math.max(1, math.floor(tonumber(saved.depth) or 1)),
    turn = math.max(0, math.floor(tonumber(saved.turn) or 0)),
    seed = math.floor(tonumber(saved.seed) or 1),
    hp = math.min(math.max(1, hp), max_hp),
    max_hp = max_hp,
    gold = math.floor(tonumber(saved.gold) or 0),
    weapon = math.min(5, math.floor(tonumber(saved.weapon) or 0)),
    glyphs = glyphs == "ascii" and "ascii" or "nerd",
    alive = true,
    px = px,
    py = py,
    floor = {},
    monsters = monsters,
    items = items,
  }
  for y, row in ipairs(saved.floor) do
    state.floor[y] = row
  end
  combat = engine.rng(math.floor(tonumber(saved.rng) or state.seed))
  return true
end

-- ------------------------------------------------------------------ combat

-- The player attacks *m* (bump attack); a dead monster may drop gold.
local function attack_monster(m)
  m.hp = m.hp - (1 + combat.int(3) + state.weapon)
  if m.hp <= 0 then
    for i, other in ipairs(state.monsters) do
      if other == m then
        table.remove(state.monsters, i)
        break
      end
    end
    if combat.int(2) == 1 then
      state.items[#state.items + 1] =
        { x = m.x, y = m.y, kind = "gold", amount = 5 + combat.int(15) }
    end
  end
end

-- True when (x, y) is off-map, a wall, the player or another monster.
local function monster_blocked(x, y)
  if x < 1 or x > MAP_W or y < 1 or y > MAP_H then
    return true
  end
  if cell_at(x, y) == WALL then
    return true
  end
  if x == state.px and y == state.py then
    return true
  end
  return monster_at(x, y) ~= nil
end

-- Manhattan-greedy step toward the player: primary axis first (larger
-- delta, ties on x), then the other axis, otherwise stay put.
local function step_monster(m)
  local dx, dy = state.px - m.x, state.py - m.y
  local sx = (dx > 0 and 1) or (dx < 0 and -1) or 0
  local sy = (dy > 0 and 1) or (dy < 0 and -1) or 0
  local moves
  if math.abs(dx) >= math.abs(dy) then
    moves = { { sx, 0 }, { 0, sy } }
  else
    moves = { { 0, sy }, { sx, 0 } }
  end
  for _, move in ipairs(moves) do
    if move[1] ~= 0 or move[2] ~= 0 then
      local nx, ny = m.x + move[1], m.y + move[2]
      if not monster_blocked(nx, ny) then
        m.x, m.y = nx, ny
        return
      end
    end
  end
end

-- Monsters act: adjacent ones attack, the others chase one step.
local function monsters_act()
  for _, m in ipairs(state.monsters) do
    local dx, dy = state.px - m.x, state.py - m.y
    if math.abs(dx) + math.abs(dy) == 1 then
      local base = m.kind == "fire" and 2 or 1
      state.hp = state.hp - (base + combat.int(2))
    else
      step_monster(m)
    end
  end
end

-- Close one player turn: monsters respond, then either the run ends or
-- the state is saved.
local function end_turn()
  state.turn = state.turn + 1
  monsters_act()
  if state.hp <= 0 then
    state.alive = false
    store.clear()
    return
  end
  save()
end

-- ------------------------------------------------------------------ actions

-- Move / bump-attack one step; walls cost nothing.
local function try_step(dx, dy)
  local tx, ty = state.px + dx, state.py + dy
  if tx < 1 or tx > MAP_W or ty < 1 or ty > MAP_H then
    return
  end
  if cell_at(tx, ty) == WALL then
    return
  end
  local target = monster_at(tx, ty)
  if target ~= nil then
    attack_monster(target)
    end_turn()
    return
  end
  state.px, state.py = tx, ty
  end_turn()
end

-- Pick up every item under the player.
local function grab()
  local kept = {}
  for _, it in ipairs(state.items) do
    if it.x == state.px and it.y == state.py then
      if it.kind == "gold" then
        state.gold = state.gold + math.floor(tonumber(it.amount) or 0)
      elseif it.kind == "potion" then
        state.hp = math.min(state.max_hp, state.hp + 3)
      elseif it.kind == "food" then
        state.hp = math.min(state.max_hp, state.hp + 2)
      elseif it.kind == "weapon" then
        state.weapon = math.min(5, state.weapon + 1)
      end
    else
      kept[#kept + 1] = it
    end
  end
  state.items = kept
end

-- Descend: depth + 1, max hp + 2, partial heal, fresh floor.
local function descend()
  state.depth = state.depth + 1
  state.max_hp = state.max_hp + 2
  state.hp = math.min(state.max_hp, state.hp + 5)
  gen_floor()
  end_turn()
end

-- A brand new run (after death or on ``r``); keeps the glyph choice.
local function restart()
  store.clear()
  new_game(random_seed(), state.glyphs)
  save()
end

-- ------------------------------------------------------------------- draw

-- Draw the whole canvas: rounded frame, glyph map, HUD and help rows.
local function draw(s)
  local map, ent = build_glyphs(state.glyphs)
  local palette = build_palette(ent)
  local lines = { engine.box_top("nethack", INNER) }
  for y = 1, MAP_H do
    local cells = {}
    local row = state.floor[y]
    for x = 1, MAP_W do
      cells[x] = map[row:sub(x, x)] or "?"
    end
    for _, it in ipairs(state.items) do
      if it.y == y then
        cells[it.x] = ent[it.kind] or cells[it.x]
      end
    end
    for _, m in ipairs(state.monsters) do
      if m.y == y then
        cells[m.x] = ent[m.kind] or cells[m.x]
      end
    end
    if state.py == y then
      cells[state.px] = state.alive and ent.player or ent.tomb
    end
    lines[#lines + 1] = engine.glyph.v .. table.concat(cells) .. engine.glyph.v
  end
  if not state.alive then
    lines[10] = engine.glyph.v
      .. engine.center("rest in peace", INNER)
      .. engine.glyph.v
    lines[12] = engine.glyph.v
      .. engine.center("press r for a new run", INNER)
      .. engine.glyph.v
  end
  local hud = "depth " .. state.depth
    .. "  hp " .. state.hp .. "/" .. state.max_hp
    .. "  gold " .. state.gold
    .. "  turn " .. state.turn
  lines[#lines + 1] = engine.glyph.v .. engine.pad(hud, INNER) .. engine.glyph.v
  lines[#lines + 1] =
    engine.glyph.v .. engine.pad(HELP_TEXT, INNER) .. engine.glyph.v
  lines[#lines + 1] = engine.box_bottom(INNER)
  s.status("depth " .. state.depth
    .. "  hp " .. state.hp .. "/" .. state.max_hp
    .. "  gold " .. state.gold)
  return table.concat(lines, "\n"), palette
end

-- -------------------------------------------------------------------- keys

-- One keypress on the canvas.
local function on_key(key)
  if state == nil then
    return
  end
  if not state.alive then
    if key == "r" then
      restart()
    end
    if session ~= nil then
      session.paint()
    end
    return
  end
  local dx, dy = engine.direction(key)
  if dx ~= nil then
    try_step(dx, dy)
  elseif key == "space" then
    end_turn()
  elseif key == "g" then
    grab()
    end_turn()
  elseif key == "enter" then
    if on_stairs() then
      descend()
    end
  elseif key == "v" then
    state.glyphs = state.glyphs == "nerd" and "ascii" or "nerd"
    save()
  end
  if session ~= nil then
    session.paint()
  end
end

-- ------------------------------------------------------------------- start

-- Launch the game (registered as the "game-nethack" action).  A valid
-- save resumes the run; otherwise a fresh dungeon is rolled.
local function start()
  if state == nil then
    local doc = store.load()
    local restored = false
    if type(doc) == "table" and type(doc.save) == "table" then
      restored = apply_save(doc.save, doc.glyphs)
    end
    if not restored then
      new_game(random_seed(), "nerd")
    end
  end
  session = engine.open({
    name = "nethack",
    cols = COLS,
    rows = ROWS,
    draw = draw,
    on_key = on_key,
    on_close = function()
      if state ~= nil and state.alive then
        save()
      end
    end,
  })
  if session ~= nil then
    session.paint()
  end
end

-- ----------------------------------------------------------- module table

function mod.setup(_api)
  engine.register("nethack", start)
end

function mod.teardown(_api)
  if state ~= nil and state.alive then
    save()
  end
end

-- Test seam: pin the run seed and roll a fresh dungeon immediately.
function mod.set_seed(n)
  local seed = math.floor(tonumber(n) or 1)
  local glyphs = state ~= nil and state.glyphs or "nerd"
  new_game(seed, glyphs)
  return seed
end

-- Test seam: inject a save-structure table directly (deterministic tests).
-- A JSON string of the same structure is accepted too (test hosts cannot
-- hand over native Lua tables); it decodes through engine.json.decode.
function mod.load_state(saved)
  if type(saved) == "string" then
    local decoded = engine.json.decode(saved)
    if decoded == nil then
      return false
    end
    saved = decoded
  end
  return apply_save(saved, state ~= nil and state.glyphs or "nerd")
end

-- Test seam: the full observable state (fields fixed by plan F section 7).
function mod.snapshot()
  if state == nil then
    return {
      depth = 0,
      turn = 0,
      hp = 0,
      max_hp = 0,
      gold = 0,
      weapon = 0,
      player_x = 0,
      player_y = 0,
      glyphs = "nerd",
      monsters = {},
      items = {},
      alive = false,
      on_stairs = false,
      depth_saved = false,
    }
  end
  local monsters = {}
  for i, m in ipairs(state.monsters) do
    monsters[i] = { x = m.x, y = m.y, kind = m.kind, hp = m.hp }
  end
  local items = {}
  for i, it in ipairs(state.items) do
    items[i] = { x = it.x, y = it.y, kind = it.kind }
  end
  local doc = store.load()
  return {
    depth = state.depth,
    turn = state.turn,
    hp = state.hp,
    max_hp = state.max_hp,
    gold = state.gold,
    weapon = state.weapon,
    player_x = state.px,
    player_y = state.py,
    glyphs = state.glyphs,
    monsters = monsters,
    items = items,
    alive = state.alive,
    on_stairs = on_stairs(),
    depth_saved = type(doc) == "table" and type(doc.save) == "table",
  }
end

return mod
