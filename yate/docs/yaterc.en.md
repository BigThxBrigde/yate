# yaterc Configuration Guide

**English** · [中文](yaterc.zh.md)

yate uses a Python-syntax configuration file called **yaterc** (like vim's
`vimrc` / neovim's `init.vim`): options are ordinary module-level variables,
and the file may contain arbitrary Python code.

A minimal config:

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

Use the bundled [yaterc.example](../yaterc.example) as a starting point (copy
it to `~/.yate/yaterc` or a project-local `yaterc`).

## Configuration file locations and load order

At startup yate loads configuration in the following order; **files loaded
later override same-named options from earlier files** (matching vim's
`~/.vimrc` → `./.vimrc` rule):

| Order | Source | Path | Notes |
|---|---|---|---|
| 1 | User level | `~/.yate/yaterc` | global personal config; skipped if missing |
| 2 | Project level | a file named `yaterc` searched **upwards** from the current directory (or the directory of the file opened at startup) | the nearest one wins; suitable for committing with the project |
| 3 | Command line | `yate -u <file>` | **replaces** the two sources above; only that file is loaded |

Special case: `yate -u NONE` skips configuration loading entirely (vim
semantics).

Loading details (implementation in [yate/config.py](../config.py)):

- Multiple files execute in order inside **the same namespace**, so project
  config can see (and override) variables already set by user config.
- Only the nine options in the table below are recognized; **unrecognized
  variables are silently ignored**, though you can freely define helper
  variables/functions for later use.
- File read failures, syntax errors and runtime exceptions **never crash the
  editor**: the offending file is skipped, the problem is shown in the startup
  message bar with a `yaterc: ...` prefix, and the remaining files continue
  loading.

## Option reference

| Option | Type | Default | Valid values | Description |
|---|---|---|---|---|
| `keymap` | `str` | `"vsc"` | `"vsc"` / `"vim"` | Key map. Invalid values fall back to the default and report an error. |
| `theme` | `str` | `"mocha"` | built-in or custom theme name | Color scheme; see below. |
| `tab_width` | `int` | `4` | integer `1`–`16` | Spaces inserted per Tab and Tab display width; non-integers such as `True`/`False` are rejected. |
| `use_spaces` | `bool` | `True` | `True` / `False` | `True` inserts spaces for Tab; `False` inserts a real tab character. |
| `extensions` | `str` or `list[str]` | none | existing file/directory paths | Extra extension script paths, see [below](#extension-paths-extensions); **accumulates** across rc files rather than overwriting. |
| `disabled_extensions` | `str` or `list[str]` | none | non-empty extension-name strings | Disable bundled default extensions by stem (e.g. `["python_lsp"]`), see [below](#extension-paths-extensions); accumulates and de-duplicates across rc files. |
| `theme_dirs` | `str` or `list[str]` | none | existing file/directory paths | Custom theme directories (or a single `*.py` theme file), see [below](#custom-theme-directories-theme_dirs); **accumulates** across rc files. |
| `shell` | `str` | platform default | non-empty string | Shell launched in the integrated terminal (open with `` Ctrl+` ``); arguments allowed (e.g. `"pwsh -NoLogo"`). Windows default: `pwsh`→Windows PowerShell→`cmd.exe`; POSIX: `$SHELL`→`bash`→`/bin/sh`. |
| `terminal_height` | `int` | `12` | integer `3`–`40` (bools/floats/strings rejected) | Integrated terminal panel height in rows. |
| `language_servers` | `list[dict]` | none | see [below](#declarative-language-servers-language_servers) | Declaratively register LSP language servers; they activate automatically when matching files open -- no extension needed. |

Invalid values never abort loading: the option keeps its default and an error
appears in the startup message bar.

Option scope:

- `keymap` / `theme` apply at startup; `theme` is process-global state (like
  vim's colorscheme).
- `tab_width` / `use_spaces` propagate to **every new and opened buffer**
  (see `_make_buffer` / `_apply_buffer_options` in [yate/app.py](../app.py)).
- `shell` is read when a terminal shell is launched (restart the shell after
  `:set shell=…`); `terminal_height` also supports immediate in-session changes
  via `:set terminal_height=<n>`.

## Built-in themes

The four built-in themes are all [Catppuccin](https://catppuccin.com/) flavors:

| Name | Flavor | Mode |
|---|---|---|
| `mocha` | Catppuccin Mocha | dark (default) |
| `macchiato` | Catppuccin Macchiato | dark |
| `frappe` | Catppuccin Frappé | dark |
| `latte` | Catppuccin Latte | light |

## Custom themes

A `register_theme()` function is injected into the yaterc namespace to
register custom `Theme` instances. The easiest approach is
`dataclasses.replace` to copy a built-in theme and override a few colors:

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # must be unique, referenced by the theme option
    label="My Mocha",
    accent="#89b4fa",      # primary: status bar bg, active tab, selection
    accent2="#cba6f7",     # secondary: mauve/purple
))

theme = "my-mocha"
```

The `Theme` fields (defined in
[yate/editor_view/theme.py](../editor_view/theme.py)) grouped by purpose:

- **Backgrounds**: `bg` (editor), `panel` (tab bar/sidebar/status bar),
  `surface` (current line/inputs), `gutter_bg` (line-number gutter),
  `border` (separators)
- **Overlays**: `selection_bg` (selection), `match_bg` / `match_active_bg`
  (search match / current match), `on_accent` (text drawn on accent blocks)
- **Foregrounds**: `fg`, `fg_dim` (comments/de-emphasis), `fg_muted`,
  `fg_bright` (emphasis)
- **Accents**: `accent`, `accent2`, `green`, `yellow`, `red`, `orange`
- **Mode chips**: `mode_normal_bg`, `mode_insert_bg`, `mode_visual_bg`,
  `mode_command_bg`
- **Syntax palette**: `syn_keyword`, `syn_string`, `syn_number`,
  `syn_comment`, `syn_function`, `syn_type`, `syn_constant`, `syn_builtin`,
  `syn_decorator`, `syn_operator`, `syn_property`

Note: reusing a built-in theme's `name` overrides that built-in theme.

## Custom theme directories (theme_dirs)

A few color tweaks can go straight into yaterc via `register_theme()` (see the
section above); for a maintainable library of reusable themes, point
`theme_dirs` at directories. Every `*.py` theme file inside loads at startup
(underscore-prefixed files are skipped), and a single `*.py` file is accepted
too:

```python
theme_dirs = "~/.yate/themes"          # one directory, a string is enough
theme_dirs = [
    "~/.yate/themes",                  # ~ is expanded
    "./team-themes",                   # relative: relative to this yaterc's directory
    "./extras/solarized.py",           # a single theme file
]
theme = "my-mocha"                     # pick a theme registered by those files
```

Theme files are ordinary Python with `Theme` and `register_theme()` already in
scope; regular imports work as well. Example file
(`~/.yate/themes/my_mocha.py`):

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(THEMES["mocha"], name="my-mocha", accent="#89b4fa"))
```

Path rules and loading behavior:

- `~` expands to the home directory; **relative paths resolve against the
  directory of the yaterc declaring them**.
- `theme_dirs` from user-level and project-level yaterc **accumulates**; a
  repeated path de-duplicates.
- Missing paths and type errors are reported as config errors in the startup
  message bar; one broken theme file does not affect the others.
- The same file executes exactly once even if hit by multiple sources
  (deduplicated by resolved absolute path).

Beyond rc declarations, `./themes/` and `~/.yate/themes/` are scanned
automatically, and the command-line `--theme-dir <dir or file>` (repeatable)
adds more; `~` is expanded (also under PowerShell/cmd). Same-name load
precedence (later wins): built-in themes < default directories < yaterc
`theme_dirs` (user rc first, project rc after) < command-line `--theme-dir`.
Once registered, switch with `:theme <name>` or select at startup with
`--theme <name>` (overrides yaterc's `theme`).

## Extension paths (extensions)

The `extensions` option declares custom extension scripts to load (the
extension API is documented in
[yate/services/extensions.py](../services/extensions.py)). An extension is a
`.py` file exposing a `setup(api)` function that registers actions, key
bindings and `:` commands through `api`:

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello from my extension!")
```

`extensions` accepts one path string or a list of paths; each entry may be:

- **A directory**: every `*.py` inside is loaded (underscore-prefixed files
  skipped);
- **A `.py` file**: just that file.

```python
extensions = "~/.yate/myext.py"          # single file
extensions = [
    "~/.yate/extensions",                # directory: every .py inside
    "./tools/yate_exts",                 # relative: relative to this yaterc's directory
    "/opt/yate/extra.py",                # absolute
]
```

Path rules and loading behavior:

- `~` expands to the home directory; **relative paths resolve against the
  directory of the yaterc declaring them** (so relative paths in a project
  yaterc keep working when the project moves).
- `extensions` from user-level and project-level yaterc **accumulates**
  (unlike the scalar "later wins" semantics); a path repeated across files
  loads only once.
- Missing paths and type errors (non-string/non-list) surface as config errors
  in the startup message bar without affecting other options.
- The same script loads exactly once even if hit by an rc path, a default
  directory and a command-line argument at the same time (deduplicated by
  resolved absolute path), preventing duplicate command/binding registration.

Beyond rc declarations, yate first auto-loads the **bundled extensions** in
`yate/extensions/` (currently `python_lsp` and `csharp_highlight`, from any
working directory), then scans the default directories `./extensions/` and
`~/.yate/extensions/`; command-line `--ext <file>` / `--ext-dir <dir>` adds
more. To skip a bundled default, list its stem (file name without `.py`) in
`disabled_extensions`:

```python
disabled_extensions = ["python_lsp"]
disabled_extensions = ["python_lsp", "csharp_highlight"]
```

The option accepts a string or a list of strings (whitespace trimmed),
accumulates and de-duplicates across rc files; it only affects bundled
extensions -- user/project/command-line scripts always load. Invalid values
are reported as config errors in the startup message bar. The full load order
and extension API are documented in
[extensions.en.md](extensions.en.md).

## Declarative language servers (language_servers)

`language_servers` declares LSP servers as a plain data list, no extension
required. Once configured, a server **auto-activates** when a file with a
matching extension opens (lazy start on first match, one process per
server × project root). The fields match the extension API
`api.lsp.register_server(...)`:

```python
language_servers = [
    {
        "name": "rust-analyzer",                  # required: status bar name
        "command": "rust-analyzer",               # required: executable (non-empty)
        "args": [],                                # optional: CLI args, default []
        "filetypes": ["rs"],                      # required: extensions without the leading dot (".rs" accepted)
        "language_ids": {"rs": "rust"},           # optional: filetype -> LSP languageId
        "root_markers": ["Cargo.toml", ".git"],   # optional: built-in markers used if absent
        "env": {"RUST_LOG": "info"},              # optional: extra environment variables
        "initialization_options": None,           # optional: initializeOptions
        "settings": None,                         # optional: server settings
    },
    {
        "name": "typescript",
        "command": "typescript-language-server",
        "args": ["--stdio"],
        "filetypes": ["ts", "tsx", "js", "jsx"],
        "language_ids": {"ts": "typescript", "tsx": "typescriptreact",
                         "js": "javascript", "jsx": "javascriptreact"},
        "root_markers": ["package.json", "tsconfig.json", ".git"],
    },
]
```

Validation and loading semantics:

- `name` / `command` / `filetypes` are required; `command` must be a non-empty
  string and `filetypes` a non-empty list of strings (the same applies to
  `args` / `root_markers`, etc.). List fields also accept tuples; leading/trailing
  whitespace around `name` / `command` is trimmed; leading dots on extensions
  are stripped (`".rs"` → `"rs"`, while values like `"."` / `".."` error);
  `language_ids` / `env` must be string-to-string maps; unknown extra keys are
  ignored. Invalid entries are skipped and reported in the startup message bar;
  the remaining entries in the same list still take effect.
- As with scalar options, a later yaterc **replaces the whole list** (no merge).
- The option registers **after** extensions load: same-named entries replace
  extension registrations (including the built-in Python server), so
  `"name": "python"` can customize the Python server command.
- Configuration alone spawns nothing; unnamed buffers and non-matching files
  are unaffected.

> For install commands and full recipes for mainstream languages, see
> [lsp.en.md](lsp.en.md) ([中文](lsp.zh.md)).

## Command-line interaction

- `yate -u <file>`: load only the specified configuration file.
- `yate -u NONE`: load no configuration at all.
- `yate --keymap vim`: an explicit command-line keymap **takes precedence over
  yaterc** (`--keymap normal` is a compatibility alias for `vsc`); without
  `--keymap`, the yaterc value is used.

## In-session temporary changes

The following `:` commands affect only the current session and are never
written back to yaterc:

- `:set keymap=vsc|vim`, `:vim`, `:vsc` (`:normal` is an alias for `:vsc`)
- `:theme <name>` / `:colorscheme <name>` (no argument lists available themes)
- `:set shell=<command>` (applies the next time a terminal shell starts),
  `:set terminal_height=<3-40>` (resizes the terminal panel immediately)

For a permanent change, write the option into yaterc.
