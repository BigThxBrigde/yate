# yate

**English** · [中文](README.zh.md)

**yate** — *yet another terminal editor*, a modern terminal text editor built
on [Textual](https://www.textualize.io/). Layered architecture: `editor_core`
holds the pure editing logic (UI-agnostic, headlessly testable) and
`editor_view` is the Textual interface.

## 📖 Manual

The full manual ships in both languages; press `F8` or run `:manual` inside
yate to open it:

| Language | File |
|---|---|
| 中文 | [yate/resources/manual.zh.md](yate/resources/manual.zh.md) |
| English | [yate/resources/manual.en.md](yate/resources/manual.en.md) |

## Features

- **VS Code-style layout**: active tab bar, EXPLORER file tree sidebar, breadcrumb path bar, flat status bar
- **Two built-in keymaps**: `vsc` (VS Code style, modeless, default) and `vim` (NORMAL/INSERT/VISUAL/VISUAL-LINE modes + `:` ex command line); `Ctrl+/` toggles between them at runtime
- **Syntax highlighting**: built-in engine colors keywords/strings/numbers/comments/functions by file type, with a bundled C# extension and `:set filetype=` manual override
- **Four Catppuccin themes**: `mocha` (default dark), `macchiato`, `frappe`, `latte` (light); register custom themes in yaterc, or bulk-load theme files via `theme_dirs` / `--theme-dir`
- **Nerd Font icons**: file tree and file-type icons (`yate --install-font` installs the bundled font and configures Windows Terminal)
- **Fuzzy finding**: `Ctrl+P` quick open (fzf-style subsequence matching with hit highlighting), `Alt+Shift+P` command palette (every `:` command and named action)
- **Multi-buffer tabs**: open by path (`Ctrl+O` / `:e`), new buffer (`Ctrl+N` / `:enew`), close tab (`Ctrl+W` / `:bd`), switch with `Ctrl+PageUp/Down` or `:bn` / `:bp`
- **Welcome screen**: version and key hints when starting with an empty buffer
- **Find & replace**: `Ctrl+F` live find with `[index/total]` match count, `F3` / `Enter` jump to the next match, `F4` two-step replace-all recorded as a single undo entry
- **Shell commands**: `F2` or `:!cmd` (e.g. `:!git status`) runs a command in a background worker; stdout/stderr show in a scrollable overlay annotated with the exit code
- **Integrated terminal**: `` Ctrl+` `` toggles a bottom terminal panel (VS Code-style layout) running a real shell over a PTY (Windows ConPTY / POSIX pty); `:term` / `:termclose`; the shell is configurable via yaterc's `shell` option, panel height via `terminal_height` (default 12 rows)
- **yaterc config**: Python-syntax config file (vimrc style) with user / project / `-u` three-level loading
- **Python extensions**: any `.py` script registers commands, key bindings and actions through `setup(api)`; the bundled extensions in `yate/extensions/` (Python LSP, C# highlighting) auto-load at startup and can be disabled by name via yaterc's `disabled_extensions`
- **LSP support**: zero-dependency built-in LSP client (`editor_lsp`) with completion popup and diagnostics (underlines / gutter marks / status bar counts / `:diagnostics`); with no server running, completion falls back to words collected from open buffers; servers register declaratively in yaterc (`language_servers`) or through extensions, including a bundled Python server (auto-discovers pyright / python-lsp-server)

## Requirements

- Python ≥ 3.10
- Dependency: [textual](https://pypi.org/project/textual/) ≥ 8.0

## Installation

```powershell
git clone <this repo>
cd yate
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e .
```

Two equivalent entry points are installed:

```powershell
yate                  # console script
python -m yate        # module form
```

## Usage

```powershell
yate                        # empty buffer (welcome screen)
yate README.md              # edit a file
yate ./src                  # open a directory, browse the file tree
yate --keymap vim .         # start with the vim keymap
yate -u ~/.yate/yaterc      # use an explicit config file
yate -u NONE                # start without any yaterc
yate --ext mytool.py        # load an extension script (repeatable)
yate --ext-dir ./exts       # load every extension in a directory (repeatable)
yate --theme-dir ./themes   # load a custom theme directory (a single .py works too; repeatable)
yate --theme my-mocha       # start with a specific theme (overrides yaterc)
yate --install-font         # install the bundled Nerd Font and exit
```

### Common keys (vsc keymap)

| Key | Function |
|---|---|
| `Ctrl+P` | fuzzy quick open |
| `Alt+Shift+P` | command palette (search and run every `:` command and named action; in vsc mode `:` is a plain character) |
| `F5` | open the command line (ex commands, `Esc` to exit) |
| `Ctrl+Q` | quit (blocked while there are unsaved changes) |
| `Ctrl+S` | save |
| `Ctrl+O` / `Ctrl+N` / `Ctrl+W` | open file by path / new empty buffer / close current tab |
| `Ctrl+PageUp` / `Ctrl+PageDown` | previous / next tab |
| `Ctrl+F` / `F3` / `F4` | find in file / next match / find and replace all (two-step) |
| `F2` | run a shell command (same as `:!cmd`; output opens in an overlay) |
| `Ctrl+G` | go to line (typing `:42` directly is equivalent; `:+5` is relative) |
| `Ctrl+B` | show/hide the file tree (palette `explorer` does the same) |
| `` Ctrl+` `` | show/hide the integrated terminal (palette `term` / `termclose`) |
| `Ctrl+E` / `Ctrl+Shift+E` | focus the file tree (the latter matches VS Code) |
| `Ctrl+1` | focus the editor (matches VS Code) |
| `Ctrl+/` | toggle between the vsc and vim keymaps (or `:set keymap=…`) |
| `Ctrl+Space` | trigger completion (LSP when a server is running, otherwise words from open buffers; accept with `Tab`/`Enter`) |
| `F1` / `F8` | help / all key bindings · open the bilingual user manual |

Inside the file tree (when focused): `j`/`k` to move, `l`/`h` to expand/collapse,
`Enter` to open, `a` new file, `A` new folder, `r` rename, `d`/`Del` delete
(type `y` to confirm), `Esc` back to the editor. Renames/deletes update open
tabs.

With the vim keymap: `i` enters insert mode, `Esc` returns to NORMAL, `:` opens
the command line; after `Ctrl+W` press `h`/`l` to move between tree and editor
(`Ctrl+W Ctrl+W` toggles). See F1 help for the full list.

## Configuration (yaterc)

The config file is plain Python: options are module-level variables. At
startup yate loads `~/.yate/yaterc` (user level) and then a `yaterc` found by
walking up from the current directory (project level; later files win for
same-named options).

```python
keymap = "vim"            # "vsc" (default) / "vim"
theme = "mocha"           # mocha | macchiato | frappe | latte | custom theme
tab_width = 4
use_spaces = True
shell = "pwsh -NoLogo"    # integrated terminal shell (default pwsh/PowerShell/cmd or $SHELL/bash)
terminal_height = 12      # terminal panel height, 3-40 rows
theme_dirs = ["~/.yate/themes"]  # custom theme directories (./themes is scanned too)
extensions = [            # extra extension paths (dirs or .py files, accumulated/deduped across rc files)
    "~/.yate/extensions",
    "./tools/my_ext.py",
]
disabled_extensions = []  # turn off bundled defaults, e.g. ["python_lsp", "csharp_highlight"]
language_servers = [      # declarative LSP: auto-activates when a matching file opens, no extension needed
    {"name": "rust-analyzer", "command": "rust-analyzer",
     "filetypes": ["rs"], "language_ids": {"rs": "rust"},
     "root_markers": ["Cargo.toml", ".git"]},
]
```

Full documentation (custom themes, path resolution rules, error behavior) is in
[yate/docs/yaterc.en.md](yate/docs/yaterc.en.md) ([中文](yate/docs/yaterc.zh.md));
copy [yaterc.example](yate/yaterc.example) as a starting point. The example is
guaranteed by tests to load cleanly.

## Extensions

An extension is any `.py` file exposing `setup(api)`:

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

Loading sources (combinable):

- **Bundled**: every `*.py` in `yate/extensions/` auto-loads at startup (from
  any working directory); disable stems in yaterc via
  `disabled_extensions = ["python_lsp"]`
- Drop into `./extensions/` or `~/.yate/extensions/` (auto-loaded at startup)
- Declare paths with `extensions = [...]` in yaterc
- On the command line: `--ext file.py` / `--ext-dir dir`

`api` registers commands (`command` / `register_command`), key bindings
(`bind_key`, supports `vsc` / `vim` / `both`) and named actions
(`register_action`), and exposes `api.buffer` / `api.doc` / `api.workspace`,
`api.shell()` / `api.open_path()` / `api.save()` / `api.message()`. A complete
template lives at
[yate/extensions/example_ext.py.example](yate/extensions/example_ext.py.example)
(use after dropping the `.example` suffix; it provides the `:upper` /
`:lower` / `:words` / `:sh` commands and an `Alt+U` binding).

### LSP language servers

Servers match by file extension and start lazily when the first matching file
is opened, providing completion plus diagnostics. Two configuration styles:

- **Declarative in yaterc (recommended)**: a list of dicts as
  `language_servers = [...]`; servers auto-activate when matching files open,
  no extension needed (see the example above and
  [yate/docs/lsp.en.md](yate/docs/lsp.en.md)).
- **Extension**: register programmatically with
  `api.lsp.register_server(...)`.

The bundled [yate/extensions/python_lsp.py](yate/extensions/python_lsp.py)
auto-connects a Python language server when opening `.py` files; install one
implementation yourself:

```powershell
pip install python-lsp-server     # pylsp
npm install -g pyright            # or pyright-langserver
```

You can also set the command line via the `YATE_PYTHON_LSP` environment
variable (set it to `off` to disable). See manual section 16 for the full API
and behavior ([中文](yate/resources/manual.zh.md) /
[English](yate/resources/manual.en.md), or `:manual` / `F8` in-session).

## Project layout

```
yate/
  editor_core/    # pure editing logic: buffer, document model, search engine (no Textual dependency)
  editor_term/    # PTY backends (ConPTY/POSIX pty), VT100 emulation, shell parsing
  editor_lsp/     # UI-agnostic LSP client: JSON-RPC, process management, completion/diagnostic state
  editor_view/    # Textual UI: editor, file tree, status bar, palette, terminal, highlighting, themes
  keymaps/        # vsc / vim keymap definitions and action dispatch
  services/       # workspace traversal, shell, extension loading, font installation
  extensions/     # bundled extensions: python_lsp (built-in LSP), csharp_highlight (C# highlighting),
                  #   example_ext.py.example (template; the .example suffix is never auto-loaded)
  docs/           # bilingual docs: yaterc config, extension API, themes, LSP recipes
                  #   (*.zh.md / *.en.md)
  resources/      # manual.zh.md / manual.en.md bilingual manual, bundled fonts
  __init__.py     # package metadata (__version__)
  __main__.py     # `python -m yate` entry
  actions.py      # named action registry shared by keymaps, command palette and extensions
  config.py       # yaterc configuration system
  app.py          # YateApp: UI assembly, command registration, lifecycle
  cli.py          # command-line entry point
  paths.py        # single resource-location authority (source / wheel / PyInstaller frozen layouts)
  yaterc.example  # configuration template
tests/            # unit tests + Textual pilot end-to-end tests
```

## Packaging

The two distribution methods are independent:

```powershell
# 1) Wheel (library-style install via pip install yate-*.whl; the yate script is generated)
python -m pip install build
python -m build --wheel          # output in dist/

# 2) PyInstaller executable (no Python needed on the target machine)
python -m pip install -e ".[build]"
pyinstaller yate.spec            # one-folder: dist/yate/yate.exe + runtime files
pyinstaller yate-onefile.spec    # single file: dist/yate.exe (16 MB, self-extracts on launch)
```

`yate.spec` / `yate-onefile.spec` and the build settings live in
[pyproject.toml](pyproject.toml): resources (fonts, bilingual docs and manuals,
`yaterc.example`, bundled extensions) keep their `yate/...` paths inside the
bundle and are resolved through [yate/paths.py](yate/paths.py), so behavior is
identical when run from source, installed as a wheel, or frozen. The onefile
build unpacks into a temporary `sys._MEIPASS` directory on every launch and
cleans it up on exit, so the resources live *inside* the exe rather than next
to it; pick one-folder when faster startup matters.

## Development

```powershell
# Run the full test suite (288 tests, including Textual pilot end-to-end tests)
python -m unittest discover -s tests

# Type checking: pyright strict, 0 diagnostics required
python -m pyright
```

## License

MIT
