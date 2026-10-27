# yate Extensions

**English** · [中文](extensions.zh.md)

A yate extension is any `.py` file that exposes a `setup(api)` function (and
optionally a `teardown(api)`). `setup` is called at application startup;
through the `api` object it receives, an extension can register commands,
actions, key bindings and language servers, and access runtime objects such as
the active buffer, document and workspace. Lua is supported too: a `.lua`
script can be a module table, an explicit `setup(api)` or a top-level
script (see section 6), provided the optional `lupa` bridge is installed
(`pip install yate[lua]`).

This file is the complete extension-writing reference; sections 10.4 / 15 of
the manual are a short introduction.

---

## 1. What an extension looks like

Minimal extension:

```python
# ~/.yate/extensions/hello.py
def setup(api):
    @api.command("hello", "greet from my extension")
    def hello(args):
        api.message(f"hello, {args or 'world'}!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

After loading, trigger it with `:hello you` or `Alt+H`.

The bundled `yate/extensions/example_ext.py.example` provides `:upper`,
`:lower`, `:words` and `:sh` commands plus an `Alt+U` binding; drop the
`.example` suffix and copy it into an extension directory to use it as a
template.

---

## 2. Loading sources and precedence

Extensions load from the following sources, **deduplicated by resolved
absolute path** (a script hit by several sources still runs exactly once):

1. The `extensions` option in yaterc (user rc before project rc; entries
   **accumulate**, they do not overwrite);
2. **Bundled extensions** in `yate/extensions/` (currently `python_lsp`,
   the Python language server, plus the game pack: `games`, the `:game`
   dispatcher, and `snake` / `pacman` / `nethack` / `tetris`;
   the shared `lib/game_engine.lua` module they all `require` lives in
   `yate/extensions/lib/`, which the loader never treats as an extension);
   they auto-load regardless of the working
   directory; disable individual defaults via yaterc's
   `disabled_extensions` (see below). The directory also ships templates
   (`*.py.example`, never auto-loaded): `example_ext.py.example`, the
   tree-sitter grammar template `yatesh_syntax.py.example`, and
   syntax-highlighting templates `batch_syntax.py.example`,
   `ini_syntax.py.example`, `fsharp_syntax.py.example`,
   `diff_syntax.py.example`, `git_syntax.py.example`, and the Lua template
   `lua.example`;
3. Default directories: `./extensions/` in the working directory and
   `~/.yate/extensions/` (every `*.py` and `*.lua` inside is auto-loaded at
   startup, files starting with an underscore are skipped). The project
   directory only auto-loads in a **trusted workspace** -- see "Workspace trust"
   below; the user directory always loads;
4. Command line: `--ext <file>` loads a single file, `--ext-dir <dir>` loads
   every `*.py`/`*.lua` in a directory (both repeatable).

Load order is the numbering above **except** for `--ext-dir`: those directories
load *before* the two default directories, so the real sequence is step 1 →
step 2 → `--ext-dir` → step 3 → `--ext <file>`. The same path runs once, so a
modified copy dropped into `~/.yate/extensions/` (step 3) can override the
registrations of the bundled same-named extension. Underscore-prefixed files and
templates with a `.example` suffix are never loaded.

### Workspace trust (:trust)

Opening a repository must never execute that repository's own code, so the
project `./extensions/` directory auto-loads only in workspaces you have
explicitly trusted. When startup finds the directory in an untrusted
workspace it skips it and reports
`extensions: skipped untrusted <path> (run :trust to load them)` on the
message bar. Run

```
:trust
```

to trust the current workspace and load its `./extensions/` immediately.
A workspace whose path contains a symlink component is **refused**: the trust
store holds resolved roots, so a symlinked cwd cannot be trusted as-is. yate
reports `refused to trust <path>: it contains a symlink component` and you
should trust the resolved directory instead.
Trusted workspaces are recorded one resolved absolute path per line in
`~/.yate/trusted_workspaces`; delete the line to stop trusting a workspace.
rc-declared paths, `--ext` / `--ext-dir` and `~/.yate/extensions/` are
deliberate user actions and always load.

### Disabling bundled defaults (disabled_extensions)

List the stems (file names without the script suffix) of bundled extensions
to skip in yaterc:

```python
disabled_extensions = ["python_lsp"]
```

- Accepts a string or a list of strings; entries **accumulate** and de-duplicate
  across rc files;
- Only affects bundled defaults -- scripts from rc paths, `./extensions/`
  in trusted workspaces, `~/.yate/extensions/` and the command line always
  load;
- Invalid values (non-string lists, empty strings) are reported as config
  errors in the startup message bar.

Declaring in yaterc:

```python
extensions = "~/.yate/myext.py"          # single file
extensions = [
    "~/.yate/extensions",                # directory: every .py inside
    "./tools/yate_exts",                 # relative: resolves against this yaterc's directory
    "/opt/yate/extra.py",                # absolute path
]
```

`~` is expanded; relative paths resolve against **the directory of the yaterc
that declares them**, so project configs keep working when the project moves.
A missing path or wrong type is shown as a config error in the message bar
without affecting other options.

---

## 3. `setup(api)` and `teardown(api)`

| Hook | When |
|---|---|
| `setup(api)` | Called once when the extension loads. The extension **must** provide this function or loading fails with `has no setup(api) function`. |
| `teardown(api)` | Optional. Called on application exit, to release resources owned by the extension (spawned subprocesses, timers). |

Both receive the same `ExtensionAPI` instance. Any exception inside an
extension never crashes the editor: errors appear in the message bar as
`extension <name>: <exception>`.

If `setup` raises partway through, everything it registered before the
failure -- actions, commands, key bindings, language servers, event
subscriptions, status segments, sprites -- is **rolled back
automatically** (the rollback scope): a failed setup never leaves
half-registered state behind, and its `teardown` never runs.

---

## 4. API reference

### 4.1 Registering `:` commands

```python
@api.command("name", "description shown in :help / palette")
def cmd(args: str) -> None:
    ...

# or imperatively
api.register_command("name", func, "description")
```

The command function receives the raw argument string after the command name
(which may be empty). For `:upper foo bar`, `args` is `"foo bar"`.

Commands appear in the command palette (`Alt+Shift+P`) and the `:help` list,
and support `Tab` completion of command names.

### 4.2 Registering named actions

```python
api.register_action("my_action", func, "description")
```

Actions can be bound via `api.bind_key` or a keymap, and searched/executed by
name from the command palette. `func` has the same signature as keymap
callbacks (takes an `ActionContext` or no arguments).

### 4.3 Binding keys

```python
api.bind_key(key_spec, callback, *, keymap="vsc",
             description="extension binding", category="extension")
```

- `keymap`: `"vsc"`, `"vim"` or `"both"` (`"normal"` is an alias for `"vsc"`).
- Usable as a decorator: when `callback` is omitted a decorator is returned.
- `callback` receives an `ActionContext` (the argument can be ignored).

**Key notation** (same as the keymap tables):

- Modifiers: `<ctrl-x>`, `<alt-x>`, `<shift-x>`, `<alt-shift-p>`
- Special keys: `<f1>`…`<f12>`, `<enter>`, `<esc>`, `<tab>`, `<backspace>`,
  `<up>`, `<down>`, `<left>`, `<right>`, `<home>`, `<end>`,
  `<pageup>`, `<pagedown>`, `<delete>`, `<space>`
- Plain characters are written directly: `"a"`, `"1"`, `":"`, `"/"`

Example:

```python
@api.bind_key("<ctrl-shift-u>", keymap="both", description="uppercase")
def _upper(ctx):
    api.buffer.insert_text((api.buffer.selected_text() or "").upper())
```

### 4.4 Accessing runtime objects

| Attribute | Type | Description |
|---|---|---|
| `api.buffer` | `TextBuffer` | active buffer |
| `api.doc` | `Document` | active document (path, saving, etc.) |
| `api.workspace` | `Workspace` | file-tree workspace |
| `api.keymaps` | `KeymapSet` | all loaded keymaps (`vsc`/`vim`); look one up with `api.keymaps.get(name)` |
| `api.app` | `ExtensionContext` | the concrete services an extension drives (advanced use) |

**`api.app` (`ExtensionContext`) fields** (advanced use; the narrow accessors
above are preferred):

| Field | Type | Description |
|---|---|---|
| `session` | `EditorSession` | the open-documents session (`session.doc` / `session.buffer`) |
| `workspace` | `Workspace` | file-tree workspace |
| `lsp` | `LspManager` | language-server manager (`api.lsp` is the narrow bridge) |
| `keymaps` | `KeymapSet` | all loaded keymaps (`vsc`/`vim`) |
| `actions` | `ActionRegistry` | named actions |
| `commands` | `CommandRegistry` | `:` commands |
| `message(text)` | callable | report a hint on the message line |
| `run_shell(command, show_output)` | callable | run a shell command synchronously; returns `ShellResult` or `None` |
| `open_path(path)` | callable | open a file/folder in the editor |
| `save()` | callable | save the active document |

**Common `api.buffer` (TextBuffer) methods**:

| Method | Purpose |
|---|---|
| `row` / `col` | cursor row/column (0-based) |
| `lines` | list of lines (assign to replace one, then call `mark_content_changed()`) |
| `get_text()` / `set_text(t)` | get/set the whole text |
| `insert_text(text)` | insert text at the cursor |
| `replace_range(start, end, text)` | replace a range |
| `has_selection()` / `selected_text()` | selection checks and text retrieval |
| `select_all()` / `clear_selection()` | selection operations |
| `undo()` / `redo()` | undo/redo |
| `move_left/right/up/down(select=False, word=False)` | cursor movement |
| `move_line_start/end()` / `move_doc_start/end()` | jumps |
| `mark_content_changed()` | call after editing `lines` directly, refreshes highlighting/caches |

When the buffer is read-only (`buf.read_only` is `True`, set via
`--readonly` or `:set readonly=true`), every mutating method raises
`yate.editor_core.BufferReadOnlyError`; wrap extensions' edits in
`try`/`except` if they must tolerate read-only documents. Assigning to
`lines` directly bypasses the guard (no exception), but the change still
counts as an edit — check `buf.read_only` first.  `doc.save()` honours
the flag too: it raises `BufferReadOnlyError` on a read-only buffer, so
deliberate persistence must lift the flag first (`buf.read_only = False`),
which is also what the interactive `:saveas` command does.

Repaint timing: yate repaints the UI (all panes) after every key-bound
action or `:` command dispatch completes. When a buffer is mutated outside
those dispatch paths (a timer or a background thread, say), the change
becomes visible at the next repaint trigger (a keypress, a pane switch,
...); `mark_content_changed()` keeps highlighting and caches in sync but
does not trigger a repaint by itself.

**Common `api.doc` (Document) members**:

| Member | Description |
|---|---|
| `doc.path` | `Path` or `None` |
| `doc.filetype` | extension without the leading dot (e.g. `py`, `rs`) |
| `doc.name` / `doc.display_path` | display name/path |
| `doc.modified` | unsaved changes? |
| `doc.save(path=None)` | save (optionally save as) |

### 4.5 Service methods

| Method | Purpose |
|---|---|
| `api.message(text)` | show a hint in the message bar |
| `api.shell(command)` | run a shell command silently, returns `ShellResult` (with `output`, `returncode`); no output popup |
| `api.open_path(path)` | open a file in a new tab |
| `api.save()` | save the current document |

### 4.6 Language servers (LSP)

See [lsp.en.md](./lsp.en.md) ([中文](./lsp.zh.md)). Core API:

```python
api.lsp.register_server(
    name="rust-analyzer",
    command="rust-analyzer",            # "" means known-missing, fails lazily
    args=[],
    filetypes=["rs"],                   # extensions without the leading dot
    language_ids={"rs": "rust"},        # textDocument languageId
    root_markers=["Cargo.toml", ".git"],
    initialization_options=None,
    settings=None,
    env=None,
)
api.lsp.statuses()        # {"rust-analyzer": "ready" | "starting" | "failed" | ...}
api.lsp.has_state(name, "ready")
```

Registering the same name again replaces the old config and discards its cached
process and diagnostics.

### 4.7 Syntax highlighting (custom languages)

`api.highlight` registers highlighting for a new language or **overrides a
built-in one** (registering the same extension again replaces it). The
highlighting engine is declarative: provide comment markers and a few word
sets; strings, numbers, comments and multiline state are handled by the
engine.

```python
from yate.editor_syntax import LangSpec

def setup(api):
    spec = LangSpec(
        name="mylang",
        line_comment="#",
        block_comment=("/*", "*/"),
        keywords=frozenset({"if", "else", "return"}),
        types=frozenset({"int", "str"}),
        constants=frozenset({"true", "false", "null"}),
        builtins=frozenset({"print"}),
        type_def_words=frozenset({"class"}),   # the next identifier is colored as a type name
        func_def_words=frozenset({"fn"}),      # the next identifier is colored as a function name
    )
    api.highlight.register(spec, "ml", "mylang")   # .ml / .mylang files
```

It takes effect immediately: `.ml` files highlight automatically, and
`:set filetype=ml` / `:set filetype=mylang` work within a session (both the
extension and the language name resolve), along with command-line `Tab`
completion and status-bar type sync. Words in `type_def_words` /
`func_def_words` are colored as keywords even without being listed in
`keywords`.

**API**:

| Method/attribute | Purpose |
|---|---|
| `api.highlight.register(spec, *extensions)` | register/replace a language; extensions without dots (dots tolerated) |
| `api.highlight.LangSpec` | language spec dataclass (or `from yate.editor_syntax import LangSpec`) |
| `api.highlight.spec(**kwargs)` | build a `LangSpec` from keyword arguments |
| `api.highlight.available()` | all extension and language names currently usable with `:set filetype` |

**`LangSpec` fields**:

| Field | Default | Description |
|---|---|---|
| `name` | (required) | language name, also a candidate for `:set filetype=<name>` |
| `mode` | `"code"` | `"code"` / `"json"` / `"markdown"` / `"config"`, selects the tokenizer |
| `line_comment` | `None` | line comment prefix, e.g. `"#"`, `"//"` |
| `block_comment` | `None` | block comment start/end markers, e.g. `("/*", "*/")` (multiline) |
| `triple_strings` | `False` | Python-style `'''`/`"""` multiline strings |
| `string_prefixes` | `""` | prefix characters allowed right before a quote (1–2), e.g. C#'s `"@$"` |
| `sigils` | `False` | highlight `$var`/`${var}` forms (shell) |
| `at_sigil` | `False` | `@name` is a variable sigil, not a decorator (perl/ruby/PowerShell) |
| `paren_vars` | `False` | highlight `$(VAR)` expansions (make) |
| `hyphenated_idents` | `False` | `font-size` scans as one identifier (CSS property names) |
| `keywords` | `frozenset()` | keywords |
| `builtins` | `frozenset()` | built-in functions/objects |
| `constants` | `frozenset()` | constants (`true`/`false`/`null`, etc.) |
| `types` | `frozenset()` | built-in / common standard-library types |
| `func_def_words` | `frozenset()` | the next identifier is colored as a function name (`def`, `fn`) |
| `type_def_words` | `frozenset()` | the next identifier is colored as a type name (`class`, `struct`, `interface`) |
| `macro_call` | `False` | an identifier immediately followed by `!` is colored as a function (Rust macros) |

**Built-in languages**: the languages yate already recognizes need no
extension. The regex backend ships word-list highlighting for Python, C,
C++, Java, Rust, Go, JavaScript, TypeScript, Shell, JSON, Markdown, TOML,
INI, YAML, C#, HTML, CSS, PowerShell, Lua, Make, XML, XAML, Perl, PHP, Ruby,
SQL, Zig, JSONC, SCSS and LESS -- 30 in all; with the optional
tree-sitter backend installed
(`pip install yate[ts]`), 25 of them are highlighted through a real parser
instead -- every one except JSONC, INI, Perl, SCSS and LESS. SCSS and LESS
share the CSS word lists and stay on the regex backend -- no grammar for
them exists on PyPI, and routing them through the CSS grammar would mis-parse
`$var` / `@mixin` / `//`.

For a complete example see the template
`yate/extensions/batch_syntax.py.example` (declarative highlighting for
Windows batch files: `rem` comments plus keyword word lists -- `%VAR%`
expansion and `:label` targets have no lexical form the word-list backend can
paint); `ini_syntax.py.example`, `git_syntax.py.example` and
`diff_syntax.py.example` cover config-mode INI/Git files and diffs, and
`fsharp_syntax.py.example` shows the tree-sitter bridge. Drop the `.example`
suffix, copy the file into an extension directory and it registers on the
next launch -- a registered extension replaces the built-in spec for the same
extension.

### 4.8 Syntax highlighting via tree-sitter (custom grammars)

`api.syntax.register_tree_sitter` binds a real tree-sitter grammar plus a
`highlights.scm` query to a language -- syntax-tree based highlighting for
custom languages (e.g. your own shell), where word-list specs are not
enough. Requires the optional dependency `pip install yate[ts]`.

```python
from pathlib import Path

def setup(api):
    here = Path(__file__).resolve().parent
    api.syntax.register_tree_sitter(
        name="yatesh",
        grammar=str(here / "yatesh.so"),   # compiled grammar (see below), or
                                           # a pip pack name "tree_sitter_yatesh"
        extensions=["ysh", "yatesh"],      # file types that select the language
        query=str(here / "highlights.scm"),  # query file path or source string
        capture_map={"operator.special": "operator"},  # optional overrides
    )
```

After registration `*.ysh` / `*.yatesh` files highlight automatically and
`:set filetype=ysh` works (with Tab completion). Registration is
all-or-nothing: the keys are published only after the grammar and the query
load, so a missing `tree_sitter`, a missing pack or an invalid query registers
nothing and the extension reports an error. If you want a fallback, register a
`LangSpec` for the same extensions through `api.highlight.register` as well.

Building the grammar library: `npm install -g tree-sitter-cli`, then in
your grammar repo run `tree-sitter generate` and compile
(`cc -shared -fPIC -I src src/parser.c src/scanner.c -o yatesh.so` on
POSIX; `cl /LD /Isrc src\parser.c src\scanner.c /Fe:yatesh.dll` with MSVC).
The C entry point must be named `tree_sitter_<name>`. Grammar queries use
tree-sitter capture names (`@keyword`, `@comment`, `@function.call`, ...)
mapped onto yate's token kinds by a default table
(`yate/editor_syntax/ts_backend/languages.py`); `capture_map` adds or
overrides single mappings.

A full template ships as `yate/extensions/yatesh_syntax.py.example`;
`fsharp_syntax.py.example` demonstrates binding a grammar from a pip pack
(`tree-sitter-fsharp`) instead of a compiled `.so`/`.dll`.
Note: `api.highlight.register` (section 4.7) always wins over the built-in
tree-sitter registration for the same extension key.

### 4.9 Screensaver characters (`api.sprites`)

`api.sprites.register` adds a custom character to the idle screensaver
(`Alt+Shift+S`): it joins the 27 built-in sprites in the parade, takes part
in playlist shuffling, and can be named in the yaterc
`screen_saver.characters` whitelist.

**Frame format** -- a character is a sequence of frames plus a palette.
Each frame is a sequence of strings, one string per pixel row, all rows the
same length; every character in a row is either a palette key (a colored
pixel) or `.` (transparent). The palette maps every key character to a
`"#rrggbb"` color string:

```python
FRAMES = (
    (   # frame 1: eyes open
        "..GG..",
        ".GGGG.",
        "GGWWGG",
        ".GGGG.",
        "..GG..",
    ),
    (   # frame 2: eyes red
        "..GG..",
        ".GGGG.",
        "GGRRGG",
        ".GGGG.",
        "..GG..",
    ),
)
PALETTE = {"G": "#00aa00", "W": "#ffffff", "R": "#cc0000"}

def setup(api):
    api.sprites.register("blob", FRAMES, PALETTE)
```

**Rendering rules** -- the screensaver draws two pixel rows per terminal
text row with Unicode half blocks: the upper pixel becomes the foreground
of `▀` and the lower pixel its background (same color → solid `█`, only a
lower pixel → `▄`, nothing → blank space). A sprite of *n* pixel rows
therefore occupies `ceil(n / 2)` text rows, and *w* pixel columns occupy
*w* text columns (1 pixel = 1 cell). Keep sprites small enough for a
24-row terminal (about 40 pixel rows at most) so the parade never clips.

**Constraints** -- validated at registration, with the same rules the
built-in roster enforces at import:

- at least 2 animation frames;
- all frames share one width and one height (no ragged frames);
- every non-`.` pixel has a palette entry.

Violations raise `ValueError`; the loader reports it on the startup
message bar as `extension <name>: ValueError ...` and the character is
not registered. Duplicates are rejected too -- including built-in names,
which an extension can never replace.

**API**:

| Method | Purpose |
|---|---|
| `api.sprites.register(name, frames, palette)` | register a character; raises `ValueError` on duplicates or invalid data |
| `api.sprites.unregister(name)` | remove a character this extension registered (built-ins cannot be removed; unknown names raise `KeyError`) |
| `api.sprites.names()` | every registered character name (built-ins + extensions), usable as a self-check |

**Full example with teardown**:

```python
# ~/.yate/extensions/blob.py
FRAMES = (...)   # as above
PALETTE = {"G": "#00aa00", "W": "#ffffff", "R": "#cc0000"}

def setup(api):
    api.sprites.register("blob", FRAMES, PALETTE)
    assert "blob" in api.sprites.names()  # self-check

def teardown(api):
    api.sprites.unregister("blob")  # no ghost names on reload
```

**Whitelist timing** -- yaterc's `screen_saver.characters` whitelist is
checked at startup, when only the built-in roster is known, so a whitelist
entry naming an extension character produces one harmless startup warning
(`unknown screensaver character: 'blob'`). The warning is cosmetic: the
screensaver re-filters the whitelist against the live registry every time
it is toggled on, so the extension character works as soon as its
extension has loaded. Either accept the known noise or leave the whitelist
unset (empty = the whole roster, extensions included).

### 4.10 Editor events (`api.events`)

`api.events.subscribe` listens to editor lifecycle events. Event
identities are `EditorEvent` enum members, re-exported as
`api.events.EditorEvent` so extensions need no yate imports -- never
strings -- and every payload is a frozen dataclass:

```python
def setup(api):
    def on_theme(payload):
        api.message(f"theme switched to {payload.name}")

    unsubscribe = api.events.subscribe(
        api.events.EditorEvent.THEME_CHANGED, on_theme)
    # call unsubscribe() to stop listening again
```

| Event | Payload | Emitted when |
|---|---|---|
| `EditorEvent.DOCUMENT_SAVED` | `DocumentSaved(doc)` | a document was written to disk (`:w`, `:saveas`, `api.save()`) |
| `EditorEvent.DOCUMENT_OPENED` | `DocumentOpened(doc)` | a file opened that was not already open in the session |
| `EditorEvent.DOCUMENT_CLOSED` | `DocumentClosed(docs)` | one or more documents left the session (`:bd`, last-tab close) |
| `EditorEvent.DOCUMENT_ACTIVATED` | `DocumentActivated(doc)` | a document became the active one (open, `:bn`/`:bp`, tab click) |
| `EditorEvent.DIAGNOSTICS_UPDATED` | `DiagnosticsUpdated(doc)` | the language server published diagnostics; the payload carries the document they belong to |
| `EditorEvent.KEYMAP_CHANGED` | `KeymapChanged(name)` | the active keymap changed (`vsc` / `vim`) |
| `EditorEvent.THEME_CHANGED` | `ThemeChanged(name)` | the color theme changed (`:theme`) |

Dispatch contract:

- **Synchronous, same-thread, subscription order** -- a listener sees the
  state at emit time; never block inside a listener.
- **Per-listener isolation** -- a raising listener is logged (trace log)
  and reported on the message line; the remaining listeners still run and
  the editor operation that emitted continues.
- `subscribe` returns an **unsubscribe thunk**; duplicates register
  separately (VS Code disposables semantics), unsubscribing twice is a
  safe no-op.
- Subscriptions made while `setup` runs are covered by the rollback
  scope: a failing setup drops them again.
- **`DOCUMENT_OPENED` precedes `DOCUMENT_ACTIVATED`** -- a freshly
  opened document emits `DOCUMENT_OPENED` first, then
  `DOCUMENT_ACTIVATED` once it becomes active; reusing an already open
  document emits only the activation.

Emissions live at low-frequency points only (save / open / close /
activate / diagnostics / keymap / theme) -- there is intentionally no
per-keystroke event.

### 4.11 Status bar segments and canvases (`api.ui`)

`api.ui.add_segment` contributes a text segment to the status
bar. The bar is a **pull-model** registry: on every refresh it calls each
registered provider once and paints the returned string with the bar's
own styles -- extensions contribute text only, never widgets or colors.

Keep providers **cheap**: the bar refreshes on every cursor move and
mode change, so a provider that scans the whole buffer runs on each of
those. Prefer short strings and cheap lookups; heavier aggregations are
better computed in event listeners (e.g. on `DOCUMENT_OPENED` /
`DOCUMENT_SAVED`) and returned from a precomputed value.

```python
def setup(api):
    api.ui.add_segment(
        "wordcount",
        lambda: f"{len(api.buffer.get_text().split())}w",
        align="right",   # "left" or "right" (default "right")
        priority=0,      # higher sorts first within its half
    )
    # Equivalent explicit form -- build the frozen StatusSegment yourself:
    #   from yate.services.extensions import StatusSegment
    #   api.ui.add_status_segment(StatusSegment(
    #       "wordcount", provider, align="right", priority=0))
```

Rules:

- Returning `None` or `""` hides the segment for that pass -- use it to
  make a segment conditional.
- A raising provider degrades to a `!` placeholder (logged, never
  fatal); one broken extension cannot take the rest of the bar down.
- Duplicate ids raise `ValueError`; `api.ui.remove_status_segment(id)`
  drops a segment (`KeyError` when unknown).
- Registrations participate in the rollback scope: a failing setup
  removes them again.

**`api.ui.open_canvas(cols, rows, on_key, on_tick, on_close)`** opens a
full-screen modal canvas the script draws into -- the mechanism behind the
bundled Tetris (`:game tetris`). It returns a **handle** with three methods:

| Method | Purpose |
|---|---|
| `handle.draw(grid, palette)` | repaint the grid: *grid* is one newline-joined string (one string per row), *palette* maps a cell character to a `"#rrggbb"` color; blanks and unknown characters keep the default color; rows/columns beyond the grid are clipped |
| `handle.set_status(text)` | replace the status line under the grid |
| `handle.close()` | close the canvas (idempotent) |

The callbacks: *on_key* receives Textual key names (`left`, `space`, ...) for
every key the canvas consumes (modal: nothing reaches the editor underneath;
`escape` is the canvas' own exit and never reaches *on_key*); *on_tick* fires
on the canvas' own clock (15 ticks per second -- accumulate ticks to slow
game gravity down); *on_close* runs once after the screen is gone.

```python
def setup(api):
    handle = None

    def on_key(key):            # "left" / "right" / "space" / ...
        ...                     # update game state; draw on the next tick
    def on_tick():
        if handle:
            handle.draw("##  \n    \n", {"#": "#e57373"})
            handle.set_status("score 0")
    def on_close():
        pass

    handle = api.ui.open_canvas(10, 20, on_key, on_tick, on_close)
```

Rules:

- `cols` / `rows` are the grid dimensions; the screen centers the grid and
  clips when the terminal is smaller.
- The handle dies with the canvas: calls after the screen is gone are
  ignored, so a tick racing the dismissal is harmless.
- Opening when the host has no UI (headless construction) raises
  `RuntimeError`.
- A raising callback is reported and the canvas keeps running; `escape`
  always works.

### 4.12 Running actions and rebinding keys (`api.actions` / `bind_action` / `unbind_key`)

`api.actions` runs registered editor actions by name and inspects the
registry. `run` goes through the editor's normal key dispatch, so an
extension-triggered action behaves exactly like a keypress:

| Method | Purpose |
|---|---|
| `api.actions.run(name)` | run action *name*; returns `False` when the name is unknown |
| `api.actions.names()` | every registered action name |
| `api.actions.has(name)` | `True` when *name* is registered |

```python
if api.actions.has("delete_line"):
    api.actions.run("delete_line")   # same dispatch path the keymaps use
```

`api.bind_action(key_spec, action_name, keymap="vsc")` rebinds a key to a
**named action** -- built-in or your own. This is how an extension moves
built-in keys around:

```python
def setup(api):
    # Re-point <ctrl-shift-d> at the built-in delete_line action, in both
    # keymaps ("both" = "vsc" + "vim"; "normal" is an alias for "vsc").
    api.bind_action("<ctrl-shift-d>", "delete_line", keymap="both")

    # Your own action: register first, then bind -- bind_action references
    # the action by name.
    api.register_action("ext.duplicate",
                        lambda ctx: ctx.buffer.duplicate_line(),
                        "duplicate the current line")
    api.bind_action("<ctrl-shift-alt-d>", "ext.duplicate")
```

- Optional `description` / `category` mirror `api.bind_key`; there is no
  decorator form -- the action is referenced by name, not passed in.
- **Register, then bind**: an unknown *action_name* binds nothing and only
  reports a warning (naming the registered actions); an unknown *keymap*
  name behaves the same. A typo never silently occupies a key.
- Rollback (section 3): a failing setup restores the previous binding of
  every key `bind_action` touched.

`api.unbind_key(key_spec, keymap="vsc")` removes a binding again
(`keymap="both"` removes it from both keymaps). It returns `True` when any
target keymap actually dropped a binding, `False` when the key was already
unbound or the keymap name is unknown:

```python
removed = api.unbind_key("<ctrl-shift-alt-d>")
api.unbind_key("<ctrl-shift-d>", keymap="both")
```

### 4.13 Theme, clipboard and open documents (`api.theme` / `api.clipboard` / `api.docs`)

**`api.theme`** switches and reads the color theme:

```python
api.theme.set("gruvbox-dark")   # KeyError when the name is unknown
current = api.theme.active()    # the active theme's name (read-only)
```

**`api.clipboard`** reads and writes the system clipboard; when no
clipboard backend is available both calls degrade gracefully (`False` /
`None`), so extension code never sees a platform exception:

```python
api.clipboard.set("copied!")    # False when unavailable
text = api.clipboard.get()      # str ("" when empty), None when unavailable
```

**`api.docs`** is a read-only view of the session's open documents:

| Method | Purpose |
|---|---|
| `api.docs.all()` | every open document -- a fresh list of `Document` (members: section 4.4) |
| `api.docs.is_open(path)` | `True` when a document showing *path* is already open |

```python
for doc in api.docs.all():
    api.message(f"{doc.name}: {'modified' if doc.modified else 'saved'}")
if not api.docs.is_open("notes.md"):
    api.open_path("notes.md")   # changes go through the normal flows
```

Deliberately narrow: there is no open/activate/close here -- the document
lifecycle goes through the editor's UI flows (`api.open_path`, `api.save`,
the `:` commands), never around them.

### 4.14 Passing IDE lint for Lua scripts (`_yate.d.lua` + `.luarc.json`)

Lua extension scripts are ordinary Lua files, so an editor knows neither
the global `yate` table nor the `api` parameter of `setup(api)` -- out of
the box both are flagged as unknown globals. yate ships two pieces of
lint infrastructure:

- `yate/extensions/_yate.d.lua` -- a `---@meta` declaration file that
  declares every exported function of `_yate.lua` with the same
  `---@param` / `---@return` annotations (no logic; the `_` prefix keeps
  it out of the auto-load scan);
- `.luarc.json` (repo root) -- the lua-language-server configuration
  yate's own Lua files lint under; its `workspace.library` entry is the
  same knob recipe (a) below uses.

The recommended editor setup is VS Code with the **"Lua"** plugin
(lua-language-server). Two recipes make your own scripts lint clean:

**(a) Point the workspace library at your yate installation** -- keep the
single shipped definition file and reference its directory:

```json
{
  "workspace.library": ["<yate>/yate/extensions"]
}
```

`<yate>` is the installed `yate` package directory -- for a wheel install
that is `.../site-packages/yate/extensions`; a frozen binary or an
editable install keeps the same folder elsewhere (the directory holding
`_yate.lua` / `_yate.d.lua` is the one to point at).

**(b) Copy the meta file into your project** -- self-contained, survives
reinstalls and upgrades:

copy `yate/extensions/_yate.d.lua` into your project (`.vscode/` is a
conventional spot) and configure the one global the definitions cannot
provide:

```json
{
  "diagnostics.globals": ["api"]
}
```

With either recipe, `yate.*` gains signature completion and the
unknown-global diagnostics for it disappear; the `api` entry covers the
`setup(api)` parameter, which only exists at runtime.

### 4.15 Persistent data (`api.data`)

`api.data` reads and writes small UTF-8 text documents under
`~/.yate/data`. It is the only file channel an extension gets: names are
relative to that directory (an absolute path, a drive letter or a `..`
component raises `ValueError`, which the bridge reports as `None` / `False`
instead of crashing the editor), and every write is atomic -- a temporary
sibling file is renamed onto the target, so a crash mid-write leaves the
previous version intact.

| Method | Returns |
|---|---|
| `api.data.read(name)` | the document text, or `None` when it does not exist |
| `api.data.write(name, text)` | `True` on success, `False` on a bad name or I/O error |
| `api.data.remove(name)` | `True` when a file was actually removed |
| `api.data.list(prefix)` | the file names inside a sub-directory, sorted (`[]` when missing) |

```python
import json

def setup(api):
    raw = api.data.read("games/snake.json")
    best = json.loads(raw)["high_scores"][0]["score"] if raw else 0
    api.data.write(
        "games/snake.json",
        json.dumps({"version": 1, "high_scores": [{"score": best + 1}]}),
    )
```

The bundled games keep one JSON document per game under `games/`; their
schemas are documented in [games.en.md](games.en.md). The Lua wrapper is
`yate.data.read` / `.write` / `.remove` / `.list` (see the table in
section 6).

---

## 5. Full example: word count + uppercase selection

```python
from yate.services.shell import ShellResult

def setup(api):
    @api.command("words", "count words in the document")
    def words(_args):
        api.message(f"word count: {len(api.buffer.get_text().split())}")

    @api.command("upper", "uppercase the selection (or current line)")
    def upper(_args):
        buf = api.buffer
        if buf.has_selection():
            buf.insert_text((buf.selected_text() or "").upper())
        else:
            row = buf.row
            buf.lines[row] = buf.lines[row].upper()
            buf.mark_content_changed()  # required after editing lines directly
        api.message("uppercased!")

    api.bind_key("<alt-u>", lambda ctx: upper(""), keymap="both",
                 description="uppercase selection/line (extension)")
```

---

## 6. Lua extensions

`.lua` extension scripts run on the same loader pipeline as Python ones
(discovery, sorting, `disabled_extensions`, dedup, workspace trust, rollback
scope and teardown) once the optional bridge package is installed:

```
pip install yate[lua]
```

Without it, loading a `.lua` extension records the actionable error
`lua extensions require the lupa package; install with: pip install yate[lua]`
and everything else keeps working.

### Shape of a Lua extension

Three styles; the loader takes the first match by precedence:
**module table > global `setup` > top level**:

- **Module-table style (recommended)**: the standard Lua library idiom --
  build a module table and `return` it; yate calls its `setup(api)` /
  `teardown(api)` fields. The contract is explicit and touches no globals,
  which suits maintained extensions. Note: **returning a table without a
  callable `setup` field is a loud error** -- returning a table signals
  module intent, so a missing entry point is most likely a typo, and
  silently accepting it would leave a "loaded but registered nothing"
  mystery behind;
- **Explicit style**: define a global `function setup(api)` -- yate calls
  it once with the same `api` object after the top level has run, a
  line-by-line mirror of the Python `setup(api)`, handy for migrating
  from a Python extension or for side-by-side reading of this manual;
- **Top-level style** (the Lua scripting idiom, backward compatible): the
  chunk's **top-level code is the setup** -- there is no `setup(api)`
  function, ideal for a ten-line quick script.

The unload hook follows the same precedence: `mod.teardown(api)` in the
module-table style, the global `teardown(api)` in the other two.

Module-table example (recommended):

```lua
-- ~/.yate/extensions/hello.lua
local mod = {}

function mod.setup(api)
  api.register_command("lua-hello", function(args)
    api.message("hello from lua! args: " .. (args or ""))
  end, "greet from a lua extension")

  api.bind_key("<alt-h>", function(ctx)
    api.message("Alt+H pressed")
  end, "both")                   -- positional args (Lua has no kwargs)
end

function mod.teardown(api)
  -- optional cleanup on exit (release the resources this extension holds)
end

return mod
```

Top-level example (quick script):

```lua
-- ~/.yate/extensions/hello.lua
local yate = require("yate")   -- or just use the global `yate`

yate.register_command("lua-hello", function(args)
  yate.message("hello from lua! args: " .. (args or ""))
end, "greet from a lua extension")

yate.bind_key("<alt-h>", function(ctx)
  yate.message("Alt+H pressed")
end, "both")                   -- positional args (Lua has no kwargs)

-- optional cleanup on exit:
-- teardown = function(api) ... end
```

Errors never crash the editor: a failing chunk is reported as
`extension <name>: LuaError: ...` and every registration it already made is
rolled back automatically. In the module-table style, a returned table
missing the `setup` field is reported as
`extension <name>: RuntimeError: extension module table has no setup(api) function ...`.
Runtime errors raised inside a command, key or action callback are caught
too and reported on the message line the same way, so a failing callback
never takes the editor down.

### The `yate` API library

The bundled library `yate/extensions/_yate.lua` ships into every extension's
runtime: `require("yate")` and the global `yate` are the same module table
(the underscore prefix keeps the library out of the auto-load scan).

| Function | Purpose |
|---|---|
| `yate.message(text)` | show a hint on the message line |
| `yate.register_command(name, fn, desc?)` | register a `:` command; `fn` receives the raw argument string |
| `yate.register_action(name, fn, desc?)` | register a named action |
| `yate.bind_key(spec, fn, keymap?)` | bind a key (`"vsc"` / `"vim"` / `"both"`; default `"vsc"`) |
| `yate.bind_action(spec, action, keymap?)` | bind a key to a **registered** action (built-in or your own; register first, section 4.12) |
| `yate.unbind_key(spec, keymap?)` | remove a key binding; returns `true` when something was removed |
| `yate.events.subscribe(name, fn)` | subscribe to editor events; `name` is the lowercase event name (`"document_saved"` ... `"theme_changed"`, section 4.10) |
| `yate.ui.add_segment(id, provider, align?, priority?)` | contribute a status bar segment (section 4.11) |
| `yate.ui.remove_segment(id)` | remove a previously contributed status bar segment (section 4.11) |
| `yate.ui.open_canvas(cols, rows, on_key, on_tick, on_close)` | open a full-screen modal canvas; returns the draw handle (section 4.11) |
| `yate.theme.set(name)` / `yate.theme.active()` | switch / read the color theme (section 4.13) |
| `yate.clipboard.set(text)` / `yate.clipboard.get()` | system clipboard (section 4.13) |
| `yate.docs.all()` / `yate.docs.is_open(path)` | read-only view of the open documents (section 4.13) |
| `yate.data.read(name)` / `.write(name, text)` / `.remove(name)` / `.list(prefix)` | documents under `~/.yate/data` (section 4.15) |
| `yate.actions.run(name)` / `.names()` / `.has(name)` | run / list / probe registered actions (section 4.12) |
| `yate.keymaps` | the loaded keymap set (pass-through of `api.keymaps`) |
| `yate.shell(cmd)` | run a shell command silently; returns the `ShellResult` object (read `.output` / `.returncode`) |
| `yate.open_path(path)` | open a file/folder in the editor |
| `yate.save()` | save the active document |
| `yate.buffer()` / `yate.doc()` / `yate.workspace()` | runtime objects (members see section 4.4) |
| `yate.api` / `yate.highlight` / `yate.sprites` / `yate.lsp` / `yate.syntax` | raw Python bridges (advanced use) |

Every wrapper above mirrors a member of the Python API one-to-one -- same
names, same semantics, positional arguments (Lua has no keyword arguments)
with omitted optionals falling back to the Python defaults; sections
4.10 / 4.11 / 4.12 / 4.13 document the shared behaviour.

Unlike the Python enum, `yate.events.subscribe` takes the lowercase event
names shown above; the payload arrives as the same frozen dataclass (read
its fields with a dot). The raw Python bridges stay reachable for anything
beyond this table via `yate.api`.

### Shared Lua modules (`extensions/lib/`)

Code that several Lua scripts need at once has one home: a `.lua` file in
`yate/extensions/lib/`, reached with `require("<file stem>")`. The loader
compiles every `lib/*.lua` into the runtime's `package.preload` table before
the script runs, so:

- nothing in `lib/` is ever auto-loaded as an extension (the loader only scans
  the top level of a directory);
- a shared module must **not** define `setup` / `teardown` -- it is a library,
  not a script;
- each runtime compiles its own copy, so two scripts requiring the same module
  still cannot observe each other's state;
- adding a module needs no Python change: the next start picks it up.

```lua
local engine = require("game_engine")   -- yate/extensions/lib/game_engine.lua

local game = {}
function game.setup(_api)
  engine.register("mygame", start)       -- exposed by that shared module
end
return game
```

The bundled game pack is built exactly this way and also shows the intended
sizing: the engine is split over `lib/game_engine.lua` (document store, high
score board, dispatch, canvas session), `lib/engine_json.lua` (the codec) and
`lib/engine_layout.lua` (glyph vocabulary and box layout) — `game_engine`
re-exports the other two, so a game still requires one name — while
`games.lua` plus one file per game only carry their own rules. See
[games.en.md](games.en.md) for the engine API table and a complete minimal
game.

### Editor completion for Lua (`---@` annotations)

Every exported function in `_yate.lua` carries EmmyLua annotations
(`---@param` / `---@return`): an editor running lua-language-server shows
signature completion for `require("yate")` out of the box. The
annotations are the "open pyi" equivalent; a mirrored `---@meta` file,
`_yate.d.lua`, ships so your own project can lint against the same
surface (see section 4.14).

### lupa semantics to keep in mind

- Every `.lua` extension gets its **own Lua runtime**; scripts cannot see
  each other's globals.
- Python objects are called with a dot from Lua
  (`yate.api.buffer.get_text()`), and their **indices are 0-based**: the
  first buffer line is `yate.buffer().lines[0]`.
- Lua's length operator `#` does not work on Python objects; take a Python
  list's length with the bridge-provided `python.builtins.len(list)`.
- Lua cannot pass keyword arguments to Python -- every library function is
  positional and omitted optional arguments fall back to the Python
  defaults. This is why `bind_key` also accepts `keymap` / `description` /
  `category` positionally (Python callers are unaffected).
- Python strings arrive as Lua strings and vice versa, losslessly.

### Installing the example

`yate --setup-defaults` places `lua.example` into `~/.yate/extensions/`;
rename it (e.g. to `hello.lua`) to activate it, or just read it -- it is a
fully commented walkthrough.

---

## 7. Extension packages (`.yxp`)

An extension package bundles several files into one archive for easy
distribution and installation. A `.yxp` file (Yate eXtension Package) is a
zip archive holding the payload files plus two reserved members:

- `manifest` -- JSON metadata: `name` (required, `^[A-Za-z0-9._-]+$`),
  `version` / `description` / `author` (optional), and the `files` list of
  every payload member.
- `checksum` -- JSON mapping each payload member to its lowercase SHA-256
  hex digest. Optional by format, but always written by the packager; when
  present, yate verifies the file list and every digest before extracting.

### Installing, uninstalling, listing

```text
yate --install-extension hello_yxp.yxp          # verify + extract + record
yate --uninstall-extension hello_yxp            # remove the recorded files
yate --list-extensions                          # show installed packages
```

Each flag runs as a side command (prints a report, then exits; repeatable
for install/uninstall; exit code 1 on failure). The same operations are
available inside the editor:

```text
:install-extension hello_yxp.yxp
:uninstall-extension hello_yxp
:list-extensions            " report in an output overlay
```

### What install does

- The payload extracts **flat** into `~/.yate/extensions/` -- the directory
  the startup loader already scans, so top-level `*.py` / `*.lua` members
  activate on the next start (restart after installing).
- Ownership is recorded in `~/.yate/extensions/_manifests/<name>.json`.
- A target file that already exists but is not owned by the same package
  refuses the install -- your hand-placed files are never clobbered.
- Reinstalling the same package name upgrades in place: its files are
  overwritten and files dropped from the new version are removed.
- Uninstalling removes exactly the recorded files (missing files are
  tolerated), then the record.

### Building packages with `tools/yxp`

The repository ships a packager (development tool, not part of the wheel):

```bash
python -m tools.yxp --create my_ext                     # scaffold ./my_ext/
python -m tools.yxp --pack tools/yxp/example/hello_yxp  # -> hello_yxp.yxp
python -m tools.yxp --verify hello_yxp.yxp
```

`--create NAME` scaffolds a source directory: a `manifest` metadata file
plus a starter `<name>.py` extension (one greeting command) -- fill in the
metadata and grow the payload from there. `--pack DIR` takes a source
directory containing a `manifest` metadata file (JSON with `name` /
`version` / `description` / `author` -- no `files` field, the packager
computes it). It writes the packaged manifest, the `checksum` member and
every payload file, skipping `__pycache__`, `.git` and `*.pyc`. The bundled
example (`tools/yxp/example/hello_yxp/`) registers a `:hello-yxp` greeting
command -- build it, install it, restart yate and run `:hello-yxp`.

### Security notes

- Verification is integrity-only (SHA-256): it detects corrupted or
  tampered archives but is not a signature -- only install packages you
  trust.
- Unsafe member names (absolute paths, `..` segments, backslashes, the
  reserved `_manifests/` directory) are rejected before anything is
  written.
- Packages without a `checksum` member install unverified; check with
  `python -m tools.yxp --verify FILE.yxp` first.
