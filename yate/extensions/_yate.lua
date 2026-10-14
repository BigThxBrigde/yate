--[[
yate built-in Lua API library (_yate.lua)

This is the Lua extension API library shipped with yate.  Every ``.lua``
extension script runs in its **own Lua runtime**; when yate creates a
runtime it compiles this file and does two things:

1. Registers this module as ``package.preload["yate"]`` -- so you can
   ``local yate = require("yate")``;
2. Sets the same module table as the global variable ``yate`` -- usable
   directly without a require.

Both forms hand you the same table; pick whichever you prefer.

Entry styles (the loader takes the first match; mirroring the Python
extension hook model):

* module-table style (recommended): build a module table and ``return``
  it -- yate calls its ``mod.setup(api)`` / ``mod.teardown(api)`` fields.
  The contract is explicit and touches no globals.  A returned table
  without a callable ``setup`` is a loud error (a table return signals
  module intent; a missing setup is a typo, not a fallback);
* explicit style: define a global ``function setup(api)`` -- yate calls it
  once with the same ``api`` object after the top level has run, a
  line-by-line mirror of the Python hook;
* top-level style (backward compatible): the chunk's top-level code *is*
  the setup and runs once at load time;
* the unload hook follows the same precedence: ``mod.teardown(api)`` in
  the module-table style, a global ``function teardown(api)`` otherwise.

Bridging notes (lupa semantics):

* The file name starts with ``_``, so this library is **never** auto-loaded
  as an extension;
* The global ``api`` is yate's Python-side ``ExtensionAPI`` object.  This
  library is a thin wrapper over it; advanced users may reach ``yate.api``
  directly (raw bridge passthrough);
* Python objects are used from Lua with plain dot access for attributes
  and methods: ``yate.api.buffer.get_text()``, ``yate.api.doc.path``, ...;
* **Python lists/strings are 0-based** (Lua tables are 1-based): the first
  line is ``yate.buffer().lines[0]``;
* Lua's length operator ``#`` does **not** work on Python objects; to take
  a Python list's length use the bridge's ``python.builtins.len(list)``;
* Lua cannot pass keyword arguments (kwargs) to Python, so every function
  in this library is **positional-only**: leave optional arguments as nil
  to get the Python-side defaults;
* Python strings are Lua strings, lossless in both directions; returned
  Python objects (like ``shell()``'s result) keep exposing their
  attributes from Lua;
* Registration calls happen at load time (top level and explicit setup
  alike); the commands/keys/actions registered by a script that later
  fails are rolled back automatically, never leaving half-registered
  state behind;
* Runtime errors raised inside a command/key/action callback are caught
  and reported on the message line the same way -- a failing callback
  never takes the editor down.

The ``---@param`` / ``---@return`` EmmyLua annotations on every function
below are the "open pyi" equivalent: they feed lua-language-server
completion, and the mirrored ``_yate.d.lua`` declaration file (same
functions, same signatures) exposes them to IDEs editing user scripts --
``tests/test_lua_defs.py`` keeps the two files in lockstep.

Exported functions (see each function's comment for details):

  message(text)                          show a hint on the message line
  register_command(name, fn, desc?)      register a ``:`` command
  register_action(name, fn, desc?)       register a named action
  bind_key(spec, fn, keymap?)            bind a key to a Lua callback
  bind_action(spec, action, keymap?)     bind a key to a registered action
  unbind_key(spec, keymap?)              remove a key binding (returns bool)
  shell(cmd)                             run a shell command silently
  open_path(path)                        open a file/folder in the editor
  save()                                 save the active document
  buffer() / doc() / workspace()         active buffer/document/workspace
  events.subscribe(name, fn)             subscribe to an editor event
  ui.add_segment(id, fn, align?, prio?)  contribute a status bar segment
  ui.remove_segment(id)                  remove a status bar segment
  theme.set(name) / theme.active()       switch / read the color theme
  clipboard.set(text) / clipboard.get()  system clipboard
  docs.all() / docs.is_open(path)        open documents (read-only)
  actions.run(name) / names() / has(name)   registered actions
  api / keymaps / highlight / sprites / lsp / syntax   raw bridge passthrough

See the bundled ``lua.example`` for a complete example; the extension
manual lives in ``yate/docs/extensions.en.md`` (Chinese mirror
``extensions.zh.md``).
]]

local yate = {}

-- Show a hint text on the message line.
---@param text string
---@return nil
function yate.message(text)
  api.message(text)
end

-- Register a ``:`` command.  fn receives the raw argument string after
-- the command name (may be empty).  Commands appear in the command
-- palette (Alt+Shift+P) and the :help list, with Tab completion.
-- description is optional (default "extension command").
---@param name string
---@param fn fun(args: string)
---@param description string|nil
---@return nil
function yate.register_command(name, fn, description)
  api.register_command(name, fn, description)
end

-- Register a named action.  Actions can be bound from keymaps and looked
-- up by name in the command palette.  fn has the same signature as key
-- callbacks (receives an ActionContext, safe to ignore).
-- description is optional.
---@param name string
---@param fn fun(ctx: any)
---@param description string|nil
---@return nil
function yate.register_action(name, fn, description)
  api.register_action(name, fn, description)
end

-- Bind a key.  spec uses yate's key notation, e.g. "<alt-h>",
-- "<ctrl-shift-u>".  keymap is optional (default "vsc"); one of
-- "vsc" / "vim" / "both" ("both" binds both keymaps at once).  Lua cannot
-- pass kwargs, so keymap is the 3rd positional argument.
-- Note: a Lua default argument reaches Python as nil (None), not as
-- "omitted", so the default must be applied explicitly here -- forwarding
-- the nil directly would silently bind nothing.
---@param spec string
---@param fn fun(ctx: any)
---@param keymap string|nil
---@return nil
function yate.bind_key(spec, fn, keymap)
  api.bind_key(spec, fn, keymap or "vsc")
end

-- Run a shell command synchronously (silently, no output overlay).
-- Returns the Python ShellResult object (read .output / .returncode),
-- or nil on failure.
---@param cmd string
---@return any result
function yate.shell(cmd)
  return api.shell(cmd)
end

-- Open a file or directory in the editor (new tab).
---@param path string
---@return nil
function yate.open_path(path)
  api.open_path(path)
end

-- Save the active document.
---@return nil
function yate.save()
  api.save()
end

-- Return the active buffer (Python TextBuffer object).  Note that
-- lines[0] is the first line.
---@return any buffer
function yate.buffer()
  return api.buffer
end

-- Return the active document (Python Document object:
-- path / filetype / modified / save).
---@return any doc
function yate.doc()
  return api.doc
end

-- Return the file-tree workspace object.
---@return any workspace
function yate.workspace()
  return api.workspace
end

-- Subscribe to an editor event.  Lua cannot reference the Python enum
-- directly, so name is one of these lowercase strings, mapped here to the
-- matching api.events.EditorEvent member: "document_saved",
-- "document_opened", "document_closed", "document_activated",
-- "diagnostics_updated", "keymap_changed", "theme_changed".  fn receives
-- the event payload (a frozen Python dataclass; see the extensions manual).
-- Returns the unsubscribe function -- call it (typically from teardown) to
-- drop the listener again.  An unknown name raises a Lua error naming it.
-- Nested under yate.events.
yate.events = {}

-- Lowercase event name -> api.events.EditorEvent enum member name.
local _EVENT_NAMES = {
  document_saved = "DOCUMENT_SAVED",
  document_opened = "DOCUMENT_OPENED",
  document_closed = "DOCUMENT_CLOSED",
  document_activated = "DOCUMENT_ACTIVATED",
  diagnostics_updated = "DIAGNOSTICS_UPDATED",
  keymap_changed = "KEYMAP_CHANGED",
  theme_changed = "THEME_CHANGED",
}

---@param name string
---@param fn fun(payload: any)
---@return fun() unsubscribe
function yate.events.subscribe(name, fn)
  local member = _EVENT_NAMES[name]
  if member == nil then
    error("unknown event: " .. tostring(name))
  end
  return api.events.subscribe(api.events.EditorEvent[member], fn)
end

-- Contribute a status bar segment.  provider is called once per status bar
-- refresh pass and its return value is rendered as the segment text (return
-- nil or "" to hide the segment for that pass).  align is optional (default
-- "right"; "left" or "right") and priority is optional (default 0; higher
-- sorts first within its half): Lua cannot pass kwargs, so leave them nil
-- to get the Python-side defaults.  A duplicate id raises an error.
-- Nested under yate.ui.
yate.ui = {}

---@param id string
---@param provider fun(): string|nil
---@param align string|nil
---@param priority number|nil
---@return nil
function yate.ui.add_segment(id, provider, align, priority)
  api.ui.add_segment(id, provider, align or "right", priority ~= nil and priority or 0)
end

-- Remove a previously contributed status bar segment (the id given to
-- add_segment).  An unknown id raises an error.  Call it from teardown
-- so a reloaded extension can add the same id again without a
-- duplicate-id error.
---@param id string
---@return nil
function yate.ui.remove_segment(id)
  api.ui.remove_status_segment(id)
end

-- Color theme.  Nested under yate.theme.
yate.theme = {}

-- Switch the color theme (raises when the name is unknown).
---@param name string
---@return nil
function yate.theme.set(name)
  api.theme.set(name)
end

-- Return the active theme's name.
---@return string name
function yate.theme.active()
  return api.theme.active()
end

-- System clipboard.  Nested under yate.clipboard.
yate.clipboard = {}

-- Copy text to the system clipboard; false when no backend is available.
---@param text string
---@return boolean copied
function yate.clipboard.set(text)
  return api.clipboard.set(text)
end

-- Return the clipboard text (nil when unavailable, "" when empty).
---@return string|nil text
function yate.clipboard.get()
  return api.clipboard.get()
end

-- Open documents (read-only view; no open/close -- that is yate.open_path's
-- job).  Nested under yate.docs.
yate.docs = {}

-- Return every open document as a Python list: 0-based (see the bridging
-- notes above), so docs[0] is the first document and lengths come from
-- python.builtins.len.
---@return any[] docs
function yate.docs.all()
  return api.docs.all()
end

-- True when a document showing path is already open.
---@param path string
---@return boolean open
function yate.docs.is_open(path)
  return api.docs.is_open(path)
end

-- Registered editor actions.  Nested under yate.actions.
yate.actions = {}

-- Run action name through the editor's key UI dispatch (the same path the
-- keymaps use); false when the action is unknown.
---@param name string
---@return boolean ran
function yate.actions.run(name)
  return api.actions.run(name)
end

-- Return every registered action name (Python list, 0-based).
---@return string[] names
function yate.actions.names()
  return api.actions.names()
end

-- True when action name is registered.
---@param name string
---@return boolean known
function yate.actions.has(name)
  return api.actions.has(name)
end

-- Bind a key to an already-registered action: the action must be registered
-- first (register_action, then bind_action) -- binding by name fails loudly
-- on a typo instead of dispatching to nothing.  spec uses yate's key
-- notation, e.g. "gq" or "<alt-h>".  keymap is optional (default "vsc"; one
-- of "vsc" / "vim" / "both"), applied explicitly here for the same nil
-- reason bind_key documents above.
---@param spec string
---@param action string
---@param keymap string|nil
---@return nil
function yate.bind_action(spec, action, keymap)
  api.bind_action(spec, action, keymap or "vsc")
end

-- Remove the binding for spec (optionally from a specific keymap, default
-- "vsc"; "both" clears vsc and vim at once).  Returns true when any target
-- keymap actually dropped a binding, false when the key was unbound.
---@param spec string
---@param keymap string|nil
---@return boolean removed
function yate.unbind_key(spec, keymap)
  return api.unbind_key(spec, keymap or "vsc")
end

-- Raw Python bridge passthrough: escape hatch for advanced use.
-- yate.api          -- the ExtensionAPI itself (this library wraps it)
-- yate.keymaps      -- the loaded keymap set (vsc / vim; api.keymaps)
-- yate.highlight    -- register declarative highlighting (api.highlight.register(spec, ...))
-- yate.sprites      -- register screensaver characters (api.sprites.register(...))
-- yate.lsp          -- register language servers (api.lsp.register_server(...))
-- yate.syntax       -- register tree-sitter grammars (api.syntax.register_tree_sitter(...))
yate.api = api
yate.keymaps = api.keymaps
yate.highlight = api.highlight
yate.sprites = api.sprites
yate.lsp = api.lsp
yate.syntax = api.syntax

return yate
