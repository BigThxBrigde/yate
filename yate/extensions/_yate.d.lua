---@meta yate
--[[
yate built-in Lua API declarations (_yate.d.lua)

lua-language-server definition file for yate's Lua extension API: it
mirrors the shipped ``_yate.lua`` library (same functions, same
``---@param`` / ``---@return`` signatures) as pure declarations -- this
file contains no executable logic.

Put this directory on your lua-language-server workspace library (the
``.luarc.json`` at the yate repository root already does that) and every
``yate.*`` call in a Lua script gets completion and type hints with zero
unknown-global diagnostics.

The file name starts with ``_``, so yate's extension loader never picks
it up as an extension, and ``---@meta`` files are never executed by the
IDE either.  ``tests/test_lua_defs.py`` keeps this file and ``_yate.lua``
in lockstep: edit ``_yate.lua`` first, then mirror the change here.
]]

-- Show a hint text on the message line.
---@param text string
---@return nil
function yate.message(text) end

-- Register a ``:`` command.  fn receives the raw argument string after
-- the command name (may be empty).  description is optional
-- (default "extension command").
---@param name string
---@param fn fun(args: string)
---@param description string|nil
---@return nil
function yate.register_command(name, fn, description) end

-- Register a named action (bindable from keymaps, listed in the palette).
---@param name string
---@param fn fun(ctx: any)
---@param description string|nil
---@return nil
function yate.register_action(name, fn, description) end

-- Bind a key to a Lua callback.  spec uses yate's key notation,
-- e.g. "<alt-h>"; keymap is optional (default "vsc").
---@param spec string
---@param fn fun(ctx: any)
---@param keymap string|nil
---@return nil
function yate.bind_key(spec, fn, keymap) end

-- Run a shell command synchronously (silently, no output overlay).
-- Returns the Python ShellResult object (read .output / .returncode),
-- or nil on failure.
---@param cmd string
---@return any result
function yate.shell(cmd) end

-- Open a file or directory in the editor (new tab).
---@param path string
---@return nil
function yate.open_path(path) end

-- Save the active document.
---@return nil
function yate.save() end

-- Return the active buffer (Python TextBuffer object).  Note that
-- lines[0] is the first line.
---@return any buffer
function yate.buffer() end

-- Return the active document (Python Document object:
-- path / filetype / modified / save).
---@return any doc
function yate.doc() end

-- Return the file-tree workspace object.
---@return any workspace
function yate.workspace() end

-- The lowercase event names accepted by yate.events.subscribe.
---@alias yate.EventName
---| "document_saved"
---| "document_opened"
---| "document_closed"
---| "document_activated"
---| "diagnostics_updated"
---| "keymap_changed"
---| "theme_changed"

-- Subscribe to an editor event.  fn receives the event payload (a frozen
-- Python dataclass); returns the unsubscribe function -- call it
-- (typically from teardown) to drop the listener again.
---@param name yate.EventName
---@param fn fun(payload: any)
---@return fun() unsubscribe
function yate.events.subscribe(name, fn) end

-- Contribute a status bar segment.  provider is called once per status
-- bar refresh pass; align defaults to "right", priority to 0 (leave nil).
---@param id string
---@param provider fun(): string|nil
---@param align string|nil
---@param priority number|nil
---@return nil
function yate.ui.add_segment(id, provider, align, priority) end

-- Remove a previously contributed status bar segment (the id given to
-- add_segment).  An unknown id raises an error.
---@param id string
---@return nil
function yate.ui.remove_segment(id) end

-- One open modal canvas, as returned by yate.ui.open_canvas.  The methods
-- are Python methods: call them with a dot (handle.draw(...)), never with a
-- colon.
---@class yate.CanvasHandle
---@field draw fun(grid: string, palette: table<string, string>)
---@field set_status fun(text: string)
---@field close fun()

-- Open a modal character canvas of cols x rows characters.  on_key receives
-- Textual key names ("left", "space", "r", ...; escape closes the canvas and
-- never reaches the hook), on_tick fires on a fixed 15 Hz clock, and on_close
-- runs once after the screen is gone.  draw() takes the whole canvas as one
-- newline-joined string plus a character -> color palette (the "*" entry
-- gives the glyph painted for every colored cell, e.g. solid blocks).
---@param cols integer
---@param rows integer
---@param on_key fun(key: string)
---@param on_tick fun()
---@param on_close fun()
---@return yate.CanvasHandle handle
function yate.ui.open_canvas(cols, rows, on_key, on_tick, on_close) end

-- Switch the color theme (raises when the name is unknown).
---@param name string
---@return nil
function yate.theme.set(name) end

-- Return the active theme's name.
---@return string name
function yate.theme.active() end

-- Copy text to the system clipboard; false when no backend is available.
---@param text string
---@return boolean copied
function yate.clipboard.set(text) end

-- Return the clipboard text (nil when unavailable, "" when empty).
---@return string|nil text
function yate.clipboard.get() end

-- Return every open document as a Python list (0-based: docs[0] is the
-- first document; lengths via python.builtins.len).
---@return any[] docs
function yate.docs.all() end

-- True when a document showing path is already open.
---@param path string
---@return boolean open
function yate.docs.is_open(path) end

-- Run action name through the editor's key UI dispatch; false when the
-- action is unknown.
---@param name string
---@return boolean ran
function yate.actions.run(name) end

-- Return every registered action name (Python list, 0-based).
---@return string[] names
function yate.actions.names() end

-- True when action name is registered.
---@param name string
---@return boolean known
function yate.actions.has(name) end

-- Persistent per-user documents under ~/.yate/data: the only file channel an
-- extension gets.  Names are relative to ~/.yate/data (absolute paths and ".."
-- are rejected); writes are atomic.  The bundled games keep one JSON document
-- per game under "games/".
---@param name string
---@return string|nil text
function yate.data.read(name) end

-- Write a document (creating parent directories); false on failure.
---@param name string
---@param text string
---@return boolean written
function yate.data.write(name, text) end

-- Delete a document; true when a file was actually removed.
---@param name string
---@return boolean removed
function yate.data.remove(name) end

-- List the file names inside a sub-directory (Python list, 0-based).
---@param prefix string
---@return string[] names
function yate.data.list(prefix) end

-- Bind a key to an already-registered action: the action must be
-- registered first (register_action, then bind_action).  keymap is
-- optional (default "vsc"; one of "vsc" / "vim" / "both").
---@param spec string
---@param action string
---@param keymap string|nil
---@return nil
function yate.bind_action(spec, action, keymap) end

-- Remove the binding for spec (default keymap "vsc"; "both" clears vsc
-- and vim at once).  Returns true when any target keymap dropped it.
---@param spec string
---@param keymap string|nil
---@return boolean removed
function yate.unbind_key(spec, keymap) end

-- Raw Python bridge passthrough (read-only handles, advanced use):
-- yate.api        -- the ExtensionAPI itself (this library wraps it)
-- yate.keymaps    -- the loaded keymap set (vsc / vim; api.keymaps)
-- yate.highlight  -- declarative highlighting (api.highlight.register(spec, ...))
-- yate.sprites    -- screensaver characters (api.sprites.register(...))
-- yate.lsp        -- language servers (api.lsp.register_server(...))
-- yate.syntax     -- tree-sitter grammars (api.syntax.register_tree_sitter(...))
---@type any
yate.api = nil

---@type any
yate.keymaps = nil

---@type any
yate.highlight = nil

---@type any
yate.sprites = nil

---@type any
yate.lsp = nil

---@type any
yate.syntax = nil
