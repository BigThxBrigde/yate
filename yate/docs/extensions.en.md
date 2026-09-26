# yate Extensions

**English** · [中文](extensions.zh.md)

A yate extension is any `.py` file that exposes a `setup(api)` function (and
optionally a `teardown(api)`). `setup` is called at application startup;
through the `api` object it receives, an extension can register commands,
actions, key bindings and language servers, and access runtime objects such as
the active buffer, document and workspace.

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
2. **Bundled extensions** in `yate/extensions/` (`python_lsp`,
   `csharp_highlight`); they auto-load regardless of the working directory;
   disable individual defaults via yaterc's `disabled_extensions` (see
   below). The directory also ships templates (`*.py.example`, never
   auto-loaded): `example_ext.py.example` and the tree-sitter grammar
   template `yatesh_syntax.py.example`;
3. Default directories: `./extensions/` in the working directory and
   `~/.yate/extensions/` (every `*.py` inside is auto-loaded at startup,
   files starting with an underscore are skipped). The project directory
   only auto-loads in a **trusted workspace** -- see "Workspace trust"
   below; the user directory always loads;
4. Command line: `--ext <file>` loads a single file, `--ext-dir <dir>` loads
   every `*.py` in a directory (both repeatable).

Load order is the numbering above; the same path runs once, so a modified copy
dropped into `~/.yate/extensions/` (step 3) can override the registrations of
the bundled same-named extension. Underscore-prefixed files and templates with
a `.example` suffix are never loaded.

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
Trusted workspaces are recorded one resolved absolute path per line in
`~/.yate/trusted_workspaces`; delete the line to stop trusting a workspace.
rc-declared paths, `--ext` / `--ext-dir` and `~/.yate/extensions/` are
deliberate user actions and always load.

### Disabling bundled defaults (disabled_extensions)

List the stems (file names without `.py`) of bundled extensions to skip in
yaterc:

```python
disabled_extensions = ["python_lsp"]
disabled_extensions = ["python_lsp", "csharp_highlight"]
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
counts as an edit — check `buf.read_only` first.

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
| `keywords` | `frozenset()` | keywords |
| `builtins` | `frozenset()` | built-in functions/objects |
| `constants` | `frozenset()` | constants (`true`/`false`/`null`, etc.) |
| `types` | `frozenset()` | built-in / common standard-library types |
| `func_def_words` | `frozenset()` | the next identifier is colored as a function name (`def`, `fn`) |
| `type_def_words` | `frozenset()` | the next identifier is colored as a type name (`class`, `struct`, `interface`) |
| `macro_call` | `False` | an identifier immediately followed by `!` is colored as a function (Rust macros) |

For a complete example see the bundled
`yate/extensions/csharp_highlight.py` (C# highlighting for `cs`/`csx`:
keywords, contextual keywords, BCL types, `$`/`@` string prefixes, etc.; this
extension is bundled and auto-loaded with no need to be in the working
directory). Turn it off in yaterc with
`disabled_extensions = ["csharp_highlight"]`, or load a modified copy
explicitly with `yate --ext csharp_highlight.py`.

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
`:set filetype=ysh` works (with Tab completion); the keys keep a minimal
regex fallback should the grammar fail to load.

Building the grammar library: `npm install -g tree-sitter-cli`, then in
your grammar repo run `tree-sitter generate` and compile
(`cc -shared -fPIC -I src src/parser.c src/scanner.c -o yatesh.so` on
POSIX; `cl /LD /Isrc src\parser.c src\scanner.c /Fe:yatesh.dll` with MSVC).
The C entry point must be named `tree_sitter_<name>`. Grammar queries use
tree-sitter capture names (`@keyword`, `@comment`, `@function.call`, ...)
mapped onto yate's token kinds by a default table
(`yate/editor_syntax/ts_backend/languages.py`); `capture_map` adds or
overrides single mappings.

A full template ships as `yate/extensions/yatesh_syntax.py.example`.
Note: `api.highlight.register` (section 4.7) always wins over the built-in
tree-sitter registration for the same extension key.

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
