--[[
yate bundled Lua module: game_engine (extensions/lib/game_engine.lua)

The shared, game-agnostic half of the bundled game pack.  This file is NOT an
extension: the loader only globs the top level of yate/extensions, and
yate/services/extensions/lua/runtime.py publishes every lib/*.lua module
through package.preload, so a game script reaches it with

    local engine = require("game_engine")

Each script runtime compiles its own private copy, so games never share state.

Contents (all of it lives here so a game only owns its rules):

  engine.json.encode / decode      minimal JSON codec (tables, arrays, escapes)
  engine.store(name)               one JSON document per game under
                                   ~/.yate/data/games/<name>.json
  engine.scores(name)              top-5 high score board with player + time
  engine.player / set_player       the player name kept in games/profile.json
  engine.register / available / dispatch   the ":game" command plumbing
  engine.open(spec)                one canvas session with the single-instance
                                   guard, paint/status/close helpers
  engine.box_top / box_bottom / center / pad / frame / panel   layout helpers
  engine.direction(key)            arrows / hjkl / wasd -> dx, dy
  engine.rng(seed)                 deterministic LCG (tests inject the seed)
  engine.utf8_char(code)           codepoint -> UTF-8 string (nerd icon helper)
  engine.trim / rep / now          small text/time helpers

Hard rules: no file I/O (yate.data is the only channel), no print(), no
os.execute, and never keep game rules in here.
]]

local engine = {}

--: Document format version written into every saved file.
engine.VERSION = 1

--: Appended to every status line so the exit key stays discoverable.
local STATUS_SUFFIX = "  escape quits"

--: Action-name prefix the ":game" dispatcher looks for.
local ACTION_PREFIX = "game-"

--: High score entries kept per game.
local MAX_SCORES = 5

--: Glyph vocabulary shared by every game (single-width Unicode, no emoji).
engine.glyph = {
  tl = "╭",
  tr = "╮",
  bl = "╰",
  br = "╯",
  h = "─",
  v = "│",
  block = "█",
  shade = "▓",
  light = "░",
  box = "▣",
  box_on_goal = "▩",
  goal = "◎",
  dot = "·",
  big_dot = "●",
  player = "☻",
  star = "★",
  heart = "♥",
  coin = "◉",
  tri = "▲",
  tri_hollow = "△",
  tri_small = "▴",
  tri_tiny = "▵",
  diamond = "◆",
  ring = "◌",
  arrow_down = "▼",
}

-- ---------------------------------------------------------------------- text

-- Strip leading and trailing whitespace.
function engine.trim(text)
  return (tostring(text or ""):gsub("^%s*(.-)%s*$", "%1"))
end

-- Repeat *text* *count* times (a non-positive count yields "").
function engine.rep(text, count)
  local times = math.floor(tonumber(count) or 0)
  if times <= 0 then
    return ""
  end
  return string.rep(tostring(text or ""), times)
end

-- Local timestamp, e.g. "2026-10-20T21:30:00".
function engine.now()
  return os.date("%Y-%m-%dT%H:%M:%S")
end

-- Codepoint -> UTF-8 string, or nil when the runtime has no utf8 library.
function engine.utf8_char(code)
  if utf8 == nil or utf8.char == nil then
    return nil
  end
  local ok, glyph = pcall(utf8.char, code)
  if not ok or type(glyph) ~= "string" or glyph == "" then
    return nil
  end
  return glyph
end

-- ---------------------------------------------------------------------- json

engine.json = {}

--: Sentinel a JSON null decodes to inside arrays (Lua arrays cannot hold nil).
engine.json.null = {}

--: Encodings of the characters that need a short escape sequence.
local JSON_ESCAPES = {
  ['"'] = '\\"',
  ["\\"] = "\\\\",
  ["\b"] = "\\b",
  ["\f"] = "\\f",
  ["\n"] = "\\n",
  ["\r"] = "\\r",
  ["\t"] = "\\t",
}

-- True when *value* is a non-empty Lua array (keys 1..n with no holes).
local function is_array(value)
  local count = 0
  for key in pairs(value) do
    if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
      return false
    end
    count = count + 1
  end
  if count == 0 then
    return true
  end
  for index = 1, count do
    if value[index] == nil then
      return false
    end
  end
  return true
end

-- Encode one string with the JSON escape rules.
local function encode_string(value)
  return '"' .. value:gsub('[%z\1-\31\\"]', function(char)
    local known = JSON_ESCAPES[char]
    if known ~= nil then
      return known
    end
    return string.format("\\u%04x", string.byte(char))
  end) .. '"'
end

local encode_value

-- Encode a Lua table, sorting object keys so output is byte-stable.
local function encode_table(value, out)
  if next(value) == nil then
    out[#out + 1] = "[]"
    return
  end
  if is_array(value) then
    out[#out + 1] = "["
    for index = 1, #value do
      if index > 1 then
        out[#out + 1] = ","
      end
      encode_value(value[index], out)
    end
    out[#out + 1] = "]"
    return
  end
  local keys = {}
  for key in pairs(value) do
    keys[#keys + 1] = key
  end
  table.sort(keys, function(left, right)
    return tostring(left) < tostring(right)
  end)
  out[#out + 1] = "{"
  for index, key in ipairs(keys) do
    if index > 1 then
      out[#out + 1] = ","
    end
    out[#out + 1] = encode_string(tostring(key))
    out[#out + 1] = ":"
    encode_value(value[key], out)
  end
  out[#out + 1] = "}"
end

-- Encode any Lua value into the *out* accumulator.
encode_value = function(value, out)
  local kind = type(value)
  if value == nil then
    out[#out + 1] = "null"
  elseif kind == "boolean" then
    out[#out + 1] = value and "true" or "false"
  elseif kind == "number" then
    if value ~= value or value == math.huge or value == -math.huge then
      out[#out + 1] = "null"
    elseif value % 1 == 0 and math.abs(value) < 1e15 then
      out[#out + 1] = string.format("%d", value)
    else
      out[#out + 1] = string.format("%.14g", value)
    end
  elseif kind == "string" then
    out[#out + 1] = encode_string(value)
  elseif kind == "table" then
    encode_table(value, out)
  else
    out[#out + 1] = "null"
  end
end

-- Encode *value* as a compact JSON string.
function engine.json.encode(value)
  local out = {}
  encode_value(value, out)
  return table.concat(out)
end

-- Decode a JSON document; returns value on success, nil + message on error.
function engine.json.decode(text)
  if type(text) ~= "string" then
    return nil, "json: input is not a string"
  end
  local position = 1
  local length = #text
  local parse_value

  local function fail(reason)
    return nil, string.format("json: %s at %d", reason, position)
  end

  local function skip_space()
    while position <= length do
      local char = text:sub(position, position)
      if char ~= " " and char ~= "\t" and char ~= "\n" and char ~= "\r" then
        return
      end
      position = position + 1
    end
  end

  local function unicode_char(code)
    if utf8 ~= nil and utf8.char ~= nil then
      local ok, glyph = pcall(utf8.char, code)
      if ok then
        return glyph
      end
    end
    return "?"
  end

  local function parse_string()
    position = position + 1
    local out = {}
    while position <= length do
      local char = text:sub(position, position)
      if char == '"' then
        position = position + 1
        return table.concat(out)
      end
      if char == "\\" then
        local marker = text:sub(position + 1, position + 1)
        local simple = {
          ['"'] = '"',
          ["\\"] = "\\",
          ["/"] = "/",
          b = "\b",
          f = "\f",
          n = "\n",
          r = "\r",
          t = "\t",
        }
        if simple[marker] ~= nil then
          out[#out + 1] = simple[marker]
          position = position + 2
        elseif marker == "u" then
          local hex = text:sub(position + 2, position + 5)
          if #hex < 4 or hex:match("^%x%x%x%x$") == nil then
            return fail("bad \\u escape")
          end
          local code = tonumber(hex, 16)
          position = position + 6
          if code >= 0xD800 and code <= 0xDBFF then
            local low = text:sub(position, position + 5)
            local low_hex, low_code = low:match("^\\u(%x%x%x%x)$")
            if low_hex ~= nil then
              local combined = 0x10000 + (code - 0xD800) * 0x400
                + (tonumber(low_hex, 16) - 0xDC00)
              out[#out + 1] = unicode_char(combined)
              position = position + 6
            else
              out[#out + 1] = unicode_char(code)
            end
          else
            out[#out + 1] = unicode_char(code)
          end
        else
          return fail("bad escape")
        end
      else
        out[#out + 1] = char
        position = position + 1
      end
    end
    return fail("unterminated string")
  end

  local function parse_number()
    local number = text:match("^-?%d+%.?%d*[eE][-+]?%d+", position)
      or text:match("^-?%d+%.?%d*", position)
    if number == nil then
      return fail("bad number")
    end
    position = position + #number
    return tonumber(number)
  end

  local function parse_array()
    position = position + 1
    local out = {}
    skip_space()
    if text:sub(position, position) == "]" then
      position = position + 1
      return out
    end
    while true do
      skip_space()
      local value, err = parse_value()
      if err ~= nil then
        return nil, err
      end
      out[#out + 1] = value
      skip_space()
      local char = text:sub(position, position)
      if char == "," then
        position = position + 1
      elseif char == "]" then
        position = position + 1
        return out
      else
        return fail("expected , or ]")
      end
    end
  end

  local function parse_object()
    position = position + 1
    local out = {}
    skip_space()
    if text:sub(position, position) == "}" then
      position = position + 1
      return out
    end
    while true do
      skip_space()
      if text:sub(position, position) ~= '"' then
        return fail("expected a key")
      end
      local key, key_err = parse_string()
      if key_err ~= nil then
        return nil, key_err
      end
      skip_space()
      if text:sub(position, position) ~= ":" then
        return fail("expected :")
      end
      position = position + 1
      skip_space()
      local value, err = parse_value()
      if err ~= nil then
        return nil, err
      end
      out[key] = value
      skip_space()
      local char = text:sub(position, position)
      if char == "," then
        position = position + 1
      elseif char == "}" then
        position = position + 1
        return out
      else
        return fail("expected , or }")
      end
    end
  end

  parse_value = function()
    skip_space()
    local char = text:sub(position, position)
    if char == "" then
      return fail("unexpected end")
    end
    if char == "{" then
      return parse_object()
    end
    if char == "[" then
      return parse_array()
    end
    if char == '"' then
      return parse_string()
    end
    if text:sub(position, position + 3) == "true" then
      position = position + 4
      return true
    end
    if text:sub(position, position + 4) == "false" then
      position = position + 5
      return false
    end
    if text:sub(position, position + 3) == "null" then
      position = position + 4
      return engine.json.null
    end
    return parse_number()
  end

  local value, err = parse_value()
  if err ~= nil then
    return nil, err
  end
  skip_space()
  if position <= length then
    return nil, string.format("json: trailing data at %d", position)
  end
  return value
end

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
    local value = engine.json.decode(text)
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
    local ok, written = pcall(yate.data.write, path, engine.json.encode(value))
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

-- -------------------------------------------------------------------- layout

-- Rounded top border with a title, total display width inner + 2.
function engine.box_top(title, inner)
  local label = tostring(title or "")
  local fill = inner - #label - 3
  if fill < 0 then
    fill = 0
  end
  return engine.glyph.tl
    .. engine.glyph.h
    .. " "
    .. label
    .. " "
    .. engine.rep(engine.glyph.h, fill)
    .. engine.glyph.tr
end

-- Rounded bottom border, total display width inner + 2.
function engine.box_bottom(inner)
  return engine.glyph.bl
    .. engine.rep(engine.glyph.h, inner)
    .. engine.glyph.br
end

-- Center *text* in a *width*-wide field (the odd space goes right).
function engine.center(text, width)
  local value = tostring(text or "")
  local left = math.floor((width - #value) / 2)
  if left < 0 then
    left = 0
  end
  return engine.rep(" ", left) .. value
end

-- Left-align *text* in a *width*-wide field (truncates when too long).
function engine.pad(text, width)
  local value = tostring(text or "")
  if #value >= width then
    return value:sub(1, width)
  end
  return value .. engine.rep(" ", width - #value)
end

-- Wrap *lines* in a titled box; every line is padded to the inner width.
function engine.frame(title, inner, lines)
  local out = { engine.box_top(title, inner) }
  for _, line in ipairs(lines or {}) do
    out[#out + 1] = engine.glyph.v .. engine.pad(line, inner) .. engine.glyph.v
  end
  out[#out + 1] = engine.box_bottom(inner)
  return out
end

-- Semantic alias of engine.frame: a side panel is a titled box.
function engine.panel(title, width, lines)
  return engine.frame(title, width, lines)
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
