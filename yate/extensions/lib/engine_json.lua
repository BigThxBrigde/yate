--[[
yate bundled Lua module: engine_json (extensions/lib/engine_json.lua)

A minimal JSON codec for saved game state.  Reached through

    local engine = require("game_engine")
    local text = engine.json.encode(state)     -- re-export of this module

or directly with require("engine_json").

Encoding rules: nil -> null, booleans and numbers verbatim, strings escaped
(quotes, backslash, the short control escapes, \u00XX for the rest), tables
as arrays when their keys are exactly 1..n (an empty table encodes as []),
otherwise as objects with their keys sorted so output is byte-stable.
Decoding returns nil plus a "json: ..." message on malformed input; a null
inside an array becomes engine.json.null (an empty table) because Lua arrays
cannot hold nil.

Hard rules: no file I/O, no print(), no os.execute, no game rules.
]]

local json = {}

--: Sentinel a JSON null decodes to inside arrays (Lua arrays cannot hold nil).
json.null = {}

--: Encodings of the characters that need a short escape sequence.
local ESCAPES = {
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
    local known = ESCAPES[char]
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
function json.encode(value)
  local out = {}
  encode_value(value, out)
  return table.concat(out)
end

-- Decode a JSON document; returns value on success, nil + message on error.
function json.decode(text)
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
            local low_hex = low:match("^\\u(%x%x%x%x)$")
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
      return json.null
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

return json
