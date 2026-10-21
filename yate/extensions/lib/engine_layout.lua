--[[
yate bundled Lua module: engine_layout (extensions/lib/engine_layout.lua)

The presentation half of the bundled game engine: the shared glyph
vocabulary, small text helpers (trim / rep / timestamp / UTF-8 codepoint) and
the rounded-box layout used by every game.  Reached through

    local engine = require("game_engine")

which re-exports this table as engine.glyph / engine.box_top / engine.frame /
engine.center / engine.pad / engine.trim / engine.rep / engine.now /
engine.utf8_char; a game may also require("engine_layout") directly.

Width rules (the reason this module exists):

- Every sizing helper works in **display columns**, measured with
  layout.width() -- one per UTF-8 codepoint.  All glyphs the pack draws are
  single width (blocks, box drawing, geometric shapes, Font Awesome 4
  private-use icons); emoji are forbidden precisely because their width is
  not knowable.
- Byte arithmetic (`#text`, `text:sub`) must never be used on a string that
  can contain multi-byte glyphs: `#` counts bytes, so a row of blocks would
  look three times longer than it is.  Truncation goes through
  layout.truncate(), which cuts on a codepoint boundary and never splits a
  glyph.
- layout.center() pads BOTH sides so the result is exactly *width* columns;
  a bordered row built as glyph.v .. center(x, inner) .. glyph.v is then
  guaranteed to line up with the box borders.

Hard rules: no file I/O, no print(), no os.execute, and no game rules -- this
module only knows about characters and widths.
]]

local layout = {}

--: Glyph vocabulary shared by every game (single-width Unicode, no emoji).
layout.glyph = {
  tl = "╭",
  tr = "╮",
  bl = "╰",
  br = "╯",
  h = "─",
  v = "│",
  block = "█",
  shade = "▓",
  mid = "▒",
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

-- Display width of *text* in codepoints (ASCII fast path included).
function layout.width(text)
  local value = tostring(text or "")
  local count = 0
  local index = 1
  local length = #value
  while index <= length do
    local byte = value:byte(index)
    if byte < 0x80 then
      index = index + 1
    elseif byte < 0xE0 then
      index = index + 2
    elseif byte < 0xF0 then
      index = index + 3
    else
      index = index + 4
    end
    count = count + 1
  end
  return count
end

-- Cut *text* to *width* display columns without splitting a glyph.
function layout.truncate(text, width)
  local value = tostring(text or "")
  if layout.width(value) <= width then
    return value
  end
  local index = 1
  local length = #value
  for _ = 1, width do
    local byte = value:byte(index)
    if byte == nil then
      return value
    end
    if byte < 0x80 then
      index = index + 1
    elseif byte < 0xE0 then
      index = index + 2
    elseif byte < 0xF0 then
      index = index + 3
    else
      index = index + 4
    end
  end
  return value:sub(1, index - 1)
end

-- Strip leading and trailing whitespace.
function layout.trim(text)
  return (tostring(text or ""):gsub("^%s*(.-)%s*$", "%1"))
end

-- Repeat *text* *count* times (a non-positive count yields "").
function layout.rep(text, count)
  local times = math.floor(tonumber(count) or 0)
  if times <= 0 then
    return ""
  end
  return string.rep(tostring(text or ""), times)
end

-- Local timestamp, e.g. "2026-10-20T21:30:00".
function layout.now()
  return os.date("%Y-%m-%dT%H:%M:%S")
end

-- Codepoint -> UTF-8 string, or nil when the runtime has no utf8 library.
function layout.utf8_char(code)
  if utf8 == nil or utf8.char == nil then
    return nil
  end
  local ok, glyph = pcall(utf8.char, code)
  if not ok or type(glyph) ~= "string" or glyph == "" then
    return nil
  end
  return glyph
end

-- Rounded top border with a title, total display width inner + 2.
function layout.box_top(title, inner)
  local label = tostring(title or "")
  local fill = inner - layout.width(label) - 3
  if fill < 0 then
    fill = 0
  end
  return layout.glyph.tl
    .. layout.glyph.h
    .. " "
    .. label
    .. " "
    .. layout.rep(layout.glyph.h, fill)
    .. layout.glyph.tr
end

-- Rounded bottom border, total display width inner + 2.
function layout.box_bottom(inner)
  return layout.glyph.bl
    .. layout.rep(layout.glyph.h, inner)
    .. layout.glyph.br
end

-- Center *text* in a *width*-wide field, padding both sides to the exact
-- width (the odd column goes to the right).
function layout.center(text, width)
  local value = layout.truncate(text, width)
  local slack = width - layout.width(value)
  local left = math.floor(slack / 2)
  return layout.rep(" ", left) .. value .. layout.rep(" ", slack - left)
end

-- Left-align *text* in a *width*-wide field (truncates on a glyph boundary).
function layout.pad(text, width)
  local value = layout.truncate(text, width)
  return value .. layout.rep(" ", width - layout.width(value))
end

-- Wrap *lines* in a titled box; every line is padded to the inner width.
function layout.frame(title, inner, lines)
  local out = { layout.box_top(title, inner) }
  for _, line in ipairs(lines or {}) do
    out[#out + 1] = layout.glyph.v .. layout.pad(line, inner) .. layout.glyph.v
  end
  out[#out + 1] = layout.box_bottom(inner)
  return out
end

-- Semantic alias of layout.frame: a side panel is a titled box.
function layout.panel(title, width, lines)
  return layout.frame(title, width, lines)
end

return layout
