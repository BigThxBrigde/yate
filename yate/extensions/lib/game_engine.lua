--[[
yate bundled Lua module: game_engine (extensions/lib/game_engine.lua)

The shared, game-agnostic half of the bundled game pack.  This file is NOT an
extension: the loader only globs the top level of yate/extensions, and
yate/services/extensions/lua/runtime.py publishes every lib/*.lua module
through package.preload, so a game script reaches it with

    local engine = require("game_engine")

Each script runtime compiles its own private copy, so games never share state.

The module is deliberately split over three files (the presentation helpers
and the codec are separate modules, re-exported here so a game only ever
requires one name):

  engine_json.lua    engine.json.encode / decode        (JSON codec)
  engine_layout.lua  engine.glyph / box_* / frame / pad (glyphs, layout)
  game_engine.lua    store / scores / player / register / dispatch / open /
                     direction / rng                    (this file)

Hard rules: no file I/O (yate.data is the only channel), no print(), no
os.execute, and never keep game rules in here.
]]

local json = require("engine_json")
local layout = require("engine_layout")

local engine = {}

--: Document format version written into every saved file.
engine.VERSION = 1

--: Appended to every status line so the exit key stays discoverable.
local STATUS_SUFFIX = "  escape quits"

--: Action-name prefix the ":game" dispatcher looks for.
local ACTION_PREFIX = "game-"

--: High score entries kept per game.
local MAX_SCORES = 5

--: Presentation half, re-exported for the game scripts.
engine.json = json
engine.glyph = layout.glyph
engine.trim = layout.trim
engine.rep = layout.rep
engine.now = layout.now
engine.width = layout.width
engine.truncate = layout.truncate
engine.utf8_char = layout.utf8_char
engine.box_top = layout.box_top
engine.box_bottom = layout.box_bottom
engine.center = layout.center
engine.pad = layout.pad
engine.frame = layout.frame
engine.panel = layout.panel

-- --------------------------------------------------------------------- store

--: Documents whose failed save was already reported (one notice each).
local warned_saves = {}

-- Report a failed save once per document, then stay quiet.
local function report_save_failure(name)
  if warned_saves[name] then
    return
  end
  warned_saves[name] = true
  yate.message("save failed: " .. name)
end

-- One saved document (games/<name>.json) with load / save / clear.
function engine.store(name)
  local path = "games/" .. name .. ".json"
  local store = { name = name, path = path }

  -- Read and decode the document; nil when missing or unreadable.
  function store.load()
    local ok, text = pcall(yate.data.read, path)
    if not ok or type(text) ~= "string" then
      return nil
    end
    local value = json.decode(text)
    if type(value) ~= "table" then
      return nil
    end
    return value
  end

  -- Encode and write the document; false (plus one notice) on failure.
  function store.save(value)
    if type(value) ~= "table" then
      return false
    end
    local ok, written = pcall(yate.data.write, path, json.encode(value))
    if not ok or written ~= true then
      report_save_failure(name)
      return false
    end
    warned_saves[name] = nil
    return true
  end

  -- Delete the document (true when a file was actually removed).
  function store.clear()
    local ok, removed = pcall(yate.data.remove, path)
    return ok and removed == true
  end

  return store
end

-- ---------------------------------------------------------------- player name

--: Fallback when neither the profile nor the environment names a player.
local DEFAULT_PLAYER = "player"

-- The player name: profile.json first, then the OS user name.
function engine.player()
  local document = engine.store("profile").load()
  if type(document) == "table" and type(document.player) == "string"
    and document.player ~= "" then
    return document.player
  end
  local name = os.getenv("USERNAME") or os.getenv("USER") or ""
  if name == "" then
    return DEFAULT_PLAYER
  end
  return name
end

-- Persist *name* as the player name (an empty name changes nothing).
function engine.set_player(name)
  local trimmed = engine.trim(name)
  if trimmed == "" then
    return engine.player()
  end
  engine.store("profile").save({ version = engine.VERSION, player = trimmed })
  return trimmed
end

-- -------------------------------------------------------------------- scores

-- The high score board of game *name*.
function engine.scores(name)
  local store = engine.store(name)
  local board = {}

  -- Saved entries, best first, clipped to MAX_SCORES.
  function board.entries()
    local out = {}
    local document = store.load()
    if type(document) ~= "table" or type(document.high_scores) ~= "table" then
      return out
    end
    for _, entry in ipairs(document.high_scores) do
      if type(entry) == "table" and type(entry.score) == "number" then
        out[#out + 1] = {
          score = entry.score,
          player = tostring(entry.player or DEFAULT_PLAYER),
          at = tostring(entry.at or ""),
        }
      end
      if #out >= MAX_SCORES then
        break
      end
    end
    return out
  end

  -- Best score so far, 0 when the board is empty.
  function board.best()
    local entries = board.entries()
    local top = entries[1]
    return top and top.score or 0
  end

  -- Insert *score* for the current player; returns the 1..5 rank or nil.
  function board.add(score)
    if type(score) ~= "number" then
      return nil
    end
    local document = store.load()
    if type(document) ~= "table" then
      document = {}
    end
    if type(document.high_scores) ~= "table" then
      document.high_scores = {}
    end
    local entries = {}
    for index, entry in ipairs(document.high_scores) do
      if type(entry) == "table" and type(entry.score) == "number" then
        entries[#entries + 1] = {
          score = entry.score,
          player = tostring(entry.player or DEFAULT_PLAYER),
          at = tostring(entry.at or ""),
          order = index,
        }
      end
    end
    local player = engine.player()
    entries[#entries + 1] = {
      score = score,
      player = player,
      at = engine.now(),
      order = #entries + 1,
    }
    local newest = #entries
    table.sort(entries, function(left, right)
      if left.score ~= right.score then
        return left.score > right.score
      end
      return left.order < right.order
    end)
    local top = {}
    local rank = nil
    for index, entry in ipairs(entries) do
      if entry.order == newest and index <= MAX_SCORES then
        rank = index
      end
      if index <= MAX_SCORES then
        top[#top + 1] = {
          score = entry.score,
          player = entry.player,
          at = entry.at,
        }
      end
    end
    document.version = engine.VERSION
    document.player = player
    document.high_scores = top
    store.save(document)
    return rank
  end

  return board
end

-- ------------------------------------------------------------------ registry

-- Register the launcher of game *name* as the action "game-<name>".
function engine.register(name, launch)
  yate.register_action(
    ACTION_PREFIX .. name,
    launch,
    "launch the " .. name .. " game"
  )
end

-- Available game names: every registered "game-*" action, sorted.
function engine.games()
  local names = {}
  local ok, listed = pcall(function()
    return yate.actions.names()
  end)
  if not ok or listed == nil then
    return names
  end
  local count = 0
  if python ~= nil and python.builtins ~= nil then
    local len_ok, length = pcall(python.builtins.len, listed)
    if len_ok and type(length) == "number" then
      count = length
    end
  end
  for index = 0, count - 1 do
    local name = listed[index]
    if type(name) == "string" and name:sub(1, #ACTION_PREFIX) == ACTION_PREFIX then
      names[#names + 1] = name:sub(#ACTION_PREFIX + 1)
    end
  end
  table.sort(names)
  return names
end

-- The available game names as one space-separated string.
function engine.available()
  return table.concat(engine.games(), " ")
end

-- The ":game" command handler (dispatch, player name, usage messages).
function engine.dispatch(args)
  local raw = engine.trim(args)
  if raw == "" then
    yate.message("usage: :game <name> (games: " .. engine.available() .. ")")
    return
  end
  local word, rest = raw:match("^(%S+)%s*(.*)$")
  if word == "player" then
    if rest == "" then
      yate.message("player: " .. engine.player())
    else
      yate.message("player: " .. engine.set_player(rest))
    end
    return
  end
  if not yate.actions.has(ACTION_PREFIX .. word) then
    yate.message(
      "unknown game: " .. word .. " (available: " .. engine.available() .. ")"
    )
    return
  end
  yate.actions.run(ACTION_PREFIX .. word)
end

-- -------------------------------------------------------------------- canvas

--: The one open session of this runtime (each game has its own runtime).
local active = nil

-- Open a canvas session for *spec* (nil when this game is already running).
--
-- spec = { name, cols, rows, draw(session) -> grid, palette,
--          on_key(key, session), on_tick(session), on_close(session) }
-- The three optional hooks receive the session as an extra argument; *draw*
-- must return the whole canvas as one newline-joined string plus its palette.
function engine.open(spec)
  if spec == nil or spec.name == nil then
    error("engine.open: spec.name is required")
  end
  if active ~= nil and not active.closed then
    yate.message(spec.name .. " is already running")
    return nil
  end

  local session = {
    name = spec.name,
    cols = spec.cols,
    rows = spec.rows,
    closed = false,
  }

  local function paint()
    if session.closed or spec.draw == nil then
      return
    end
    local grid, palette = spec.draw(session)
    if grid == nil then
      return
    end
    session.handle.draw(grid, palette or {})
  end

  local function on_key(key)
    if session.closed or spec.on_key == nil then
      return
    end
    spec.on_key(key, session)
  end

  local function on_tick()
    if session.closed or spec.on_tick == nil then
      return
    end
    spec.on_tick(session)
  end

  local function on_close()
    session.closed = true
    active = nil
    if spec.on_close ~= nil then
      spec.on_close(session)
    end
  end

  session.handle = yate.ui.open_canvas(
    spec.cols,
    spec.rows,
    on_key,
    on_tick,
    on_close
  )
  active = session

  -- Repaint the whole canvas from spec.draw.
  function session.paint()
    paint()
  end

  -- Replace the status line (the exit hint is appended once).
  function session.status(text)
    if session.closed then
      return
    end
    local line = tostring(text or "")
    if line:sub(-#STATUS_SUFFIX) ~= STATUS_SUFFIX then
      line = line .. STATUS_SUFFIX
    end
    session.handle.set_status(line)
  end

  -- Dismiss the canvas (idempotent).
  function session.close()
    if session.closed then
      return
    end
    session.closed = true
    active = nil
    session.handle.close()
  end

  -- True while this session is the open one.
  function session.is_open()
    return active == session and not session.closed
  end

  return session
end

-- --------------------------------------------------------------------- input

--: Key name -> { dx, dy } for arrows, hjkl and wasd.
local DIRECTIONS = {
  left = { -1, 0 },
  h = { -1, 0 },
  a = { -1, 0 },
  right = { 1, 0 },
  l = { 1, 0 },
  d = { 1, 0 },
  up = { 0, -1 },
  k = { 0, -1 },
  w = { 0, -1 },
  down = { 0, 1 },
  j = { 0, 1 },
  s = { 0, 1 },
}

-- Map a Textual key name to a step; nil for every other key.
function engine.direction(key)
  local delta = DIRECTIONS[key]
  if delta == nil then
    return nil
  end
  return delta[1], delta[2]
end

-- ----------------------------------------------------------------------- rng

--: LCG parameters (Numerical Recipes); state stays below 2^31.
local RNG_MODULUS = 2147483648
local RNG_MULTIPLIER = 1103515245
local RNG_INCREMENT = 12345

--: Seed used when the caller passes none.
local DEFAULT_SEED = 2147483647

-- A deterministic pseudo random generator (same seed, same sequence).
function engine.rng(seed)
  local rng = {}
  local state = 0

  -- Reset the generator to *new_seed* (nil keeps the default seed).
  function rng.set(new_seed)
    local value = math.floor(tonumber(new_seed) or DEFAULT_SEED) % RNG_MODULUS
    if value <= 0 then
      value = value + RNG_MODULUS - 1
    end
    state = value
    return state
  end

  -- The current generator state (persist it to resume a sequence).
  function rng.state()
    return state
  end

  -- Next integer in 1..count (always advances the state).
  function rng.int(count)
    local limit = math.floor(tonumber(count) or 1)
    state = (state * RNG_MULTIPLIER + RNG_INCREMENT) % RNG_MODULUS
    if limit < 1 then
      return 1
    end
    return state % limit + 1
  end

  -- Pick one element of the array *list*.
  function rng.pick(list)
    if type(list) ~= "table" or #list == 0 then
      return nil
    end
    return list[rng.int(#list)]
  end

  rng.set(seed)
  return rng
end

return engine
