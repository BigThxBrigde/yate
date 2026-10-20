--[[
yate bundled Lua module: engine_layout (extensions/lib/engine_layout.lua)

The presentation half of the bundled game engine: the shared glyph
vocabulary, small text helpers (trim / rep / timestamp / UTF-8 codepoint) and
the rounded-box layout used by every game.  Reached through

    local engine = require("game_engine")

which re-exports this table as engine.glyph / engine.box_top / engine.frame /
engine.center / engine.pad / engine.trim / engine.rep / engine.now /
engine.utf8_char; a game may also require("engine_layout") directly.

Hard rules: no file I/O, no print(), no os.execute, and no game rules -- this
module only knows about characters and widths.  Every helper sizes text by
byte length, so callers keep frame content ASCII; games that draw multi-byte
glyphs (sokoban, nethack) build their rows with table.concat instead.
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
  local fill = inner - #label - 3
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

-- Center *text* in a *width*-wide field (the odd space goes right).
function layout.center(text, width)
  local value = tostring(text or "")
  local left = math.floor((width - #value) / 2)
  if left < 0 then
    left = 0
  end
  return layout.rep(" ", left) .. value
end

-- Left-align *text* in a *width*-wide field (truncates when too long).
function layout.pad(text, width)
  local value = tostring(text or "")
  if #value >= width then
    return value:sub(1, width)
  end
  return value .. layout.rep(" ", width - #value)
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
