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
* Registration calls happen at load time; the commands/keys/actions
  registered by a script that later fails are rolled back automatically,
  never leaving half-registered state behind;
* Runtime errors raised inside a command/key/action callback are caught
  and reported on the message line the same way -- a failing callback
  never takes the editor down.

Exported functions (see each function's comment for details):

  message(text)                          show a hint on the message line
  register_command(name, fn, desc?)      register a ``:`` command
  register_action(name, fn, desc?)       register a named action
  bind_key(spec, fn, keymap?)            bind a key
  shell(cmd)                             run a shell command silently
  open_path(path)                        open a file/folder in the editor
  save()                                 save the active document
  buffer() / doc() / workspace()         active buffer/document/workspace
  api / highlight / sprites / lsp / syntax   raw Python bridge passthrough

See the bundled ``lua.example`` for a complete example; the extension
manual lives in ``yate/docs/extensions.en.md`` (Chinese mirror
``extensions.zh.md``).
]]

local yate = {}

-- Show a hint text on the message line.
function yate.message(text)
  api.message(text)
end

-- Register a ``:`` command.  fn receives the raw argument string after
-- the command name (may be empty).  Commands appear in the command
-- palette (Alt+Shift+P) and the :help list, with Tab completion.
-- description is optional (default "extension command").
function yate.register_command(name, fn, description)
  api.register_command(name, fn, description)
end

-- Register a named action.  Actions can be bound from keymaps and looked
-- up by name in the command palette.  fn has the same signature as key
-- callbacks (receives an ActionContext, safe to ignore).
-- description is optional.
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
function yate.bind_key(spec, fn, keymap)
  api.bind_key(spec, fn, keymap or "vsc")
end

-- Run a shell command synchronously (silently, no output overlay).
-- Returns the Python ShellResult object (read .output / .returncode),
-- or nil on failure.
function yate.shell(cmd)
  return api.shell(cmd)
end

-- Open a file or directory in the editor (new tab).
function yate.open_path(path)
  api.open_path(path)
end

-- Save the active document.
function yate.save()
  api.save()
end

-- Return the active buffer (Python TextBuffer object).  Note that
-- lines[0] is the first line.
function yate.buffer()
  return api.buffer
end

-- Return the active document (Python Document object:
-- path / filetype / modified / save).
function yate.doc()
  return api.doc
end

-- Return the file-tree workspace object.
function yate.workspace()
  return api.workspace
end

-- Raw Python bridge passthrough: escape hatch for advanced use.
-- yate.api          -- the ExtensionAPI itself (this library wraps it)
-- yate.highlight    -- register declarative highlighting (api.highlight.register(spec, ...))
-- yate.sprites      -- register screensaver characters (api.sprites.register(...))
-- yate.lsp          -- register language servers (api.lsp.register_server(...))
-- yate.syntax       -- register tree-sitter grammars (api.syntax.register_tree_sitter(...))
yate.api = api
yate.highlight = api.highlight
yate.sprites = api.sprites
yate.lsp = api.lsp
yate.syntax = api.syntax

return yate
