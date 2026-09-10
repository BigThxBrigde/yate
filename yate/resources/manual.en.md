# yate User Manual

**yate** — *yet another terminal editor*, a modern terminal text editor built on
[Textual](https://www.textualize.io/).
Version **0.1.0** (this manual ships with the program; press `F8` or type `:manual`
to open it anytime — `:manual zh` / `:manual en` picks the language, English by default).

yate uses a layered architecture: `editor_core` is pure editing logic fully
decoupled from the UI (buffers, document model, search engine), `editor_view` is
the Textual interface, `keymaps` provides pluggable key bindings, and `services`
handles the workspace, shell, extensions and fonts.

---

## Table of Contents

1. System Requirements and Installation
2. Launching and Command-Line Arguments
3. Interface Tour
4. Quick Start
5. Key Bindings (vsc / vim keymaps)
6. File Explorer
7. Search and Replace
8. Command Line (ex commands)
9. Command Palette and Quick Open
10. The yaterc Configuration File
11. Themes
12. Fonts and Nerd Font Icons
13. Shell Integration
14. Python Extensions
15. FAQ
16. Key Binding Cheat Sheet

---

## 1. System Requirements and Installation

| Item | Requirement |
|---|---|
| Python | ≥ 3.10 |
| Core dependency | textual ≥ 8.0 |
| Terminal | any modern terminal with ANSI escape support (Windows Terminal recommended) |
| Font | a Nerd Font is recommended for file icons (see section 12) |

Install from source (Windows PowerShell example):

```powershell
git clone <this repo>
cd yate
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e .
```

Two equivalent entry points are provided:

```powershell
yate                  # console script
python -m yate        # run as a module
```

Show the version: `yate --version`.

## 2. Launching and Command-Line Arguments

```
yate [path] [options]
```

| Argument | Description |
|---|---|
| `path` (optional) | File or directory to open. A directory is browsed in the file tree; a non-existent path is treated as a new file to create |
| `--keymap {vsc,vim,normal}` | Keymap for this session; `normal` is a compatibility alias for `vsc`. **Takes priority over yaterc** |
| `-u FILE` / `--yaterc FILE` | Load only this config file (vim-style `-u`); `-u NONE` skips config loading entirely |
| `--ext FILE` | Load one Python extension script (repeatable) |
| `--ext-dir DIR` | Load every `*.py` extension in a directory (repeatable) |
| `--install-font` | Install the bundled Nerd Font for the current user (configures Windows Terminal when needed), then exit without entering the UI |
| `--version` | Show the version |
| `--help` | Show help |

Launch examples:

```powershell
yate                        # empty buffer (welcome page)
yate README.md              # edit a file
yate ./src                  # open a directory in the file tree
yate --keymap vim .         # start with the vim keymap
yate -u ~/.yate/yaterc      # use a specific config file
yate -u NONE                # skip all yaterc loading
yate --ext mytool.py        # load an extension script (repeatable)
yate --ext-dir ./exts       # load every extension in a directory (repeatable)
yate --install-font         # install the bundled Nerd Font, then exit
```

## 3. Interface Tour

yate's layout mimics VS Code, top to bottom:

```
┌────────────┬──────────────────────────────────┐
│  EXPLORER  │  tab bar                          │
│  file tree │  breadcrumbs                      │
│  side bar  │  editor                           │
├────────────┴──────────────────────────────────┤
│  status bar                                   │
│  command line / message bar                   │
└───────────────────────────────────────────────┘
```

### 3.1 The EXPLORER file tree side bar

- Title `EXPLORER` at the top; roughly 34 character columns wide.
- Shows the tree of the opened directory; directories sort before files, each
  sorted by name.
- Every entry has a Nerd Font icon (folders, per-extension file type icons).
- Directories are lazily loaded: subdirectories are read on first expand.
- With no directory open it shows `no folder open`; use `:e <path>` to open one.
- Keyboard operation is covered in section 6.

### 3.2 Tab bar

- One tab per open document: ` <icon> filename`; the active tab uses the editor
  background, inactive tabs use the panel background.
- A modified file shows an orange `●` marker on its tab.
- Overlong names are truncated by display width.

### 3.3 Breadcrumbs

- Shows the current document's full path relative to the workspace root:
  `icon directory › subdirectory › filename`.
- The filename is always bold; when space runs out the left side truncates with
  an ellipsis `…` (the filename stays visible).
- Unnamed buffers show no breadcrumbs (the tab bar already shows `[no name]`).

### 3.4 Editor

- Line-number gutter on the left; the current line's number is bold and uses
  the theme accent color.
- The current line is highlighted full-width (surface background).
- Block cursor; at end of line the cursor renders on the filler cell.
- The built-in syntax highlighter colors by file type (supported languages,
  see the FAQ in section 15: Python, C/C++, Java, Rust, Go,
  JavaScript/TypeScript, Shell, JSON, Markdown, TOML, INI, YAML).
- Selections and search matches (the active match in a stronger color) render
  as theme-colored overlays.
- An empty unnamed buffer shows the welcome page: the YATE figlet banner,
  version and common key hints.

### 3.5 Status bar

Left: mode block + file info; right: position and metadata.

- **Mode block**: `VSC` under the vsc keymap; `NORMAL` / `INSERT` / `VISUAL` /
  `V-LINE` under the vim keymap; `COMMAND` / `SEARCH` / `SHELL` while the
  command line is in the corresponding input state.
- File name (with pencil icon), followed by `●` when unsaved.
- Right side: `Ln row, Col col`, total lines, file type (extension), encoding;
  then the hint icon area: loaded extension count, `:!` (shell command), `F1`
  (help).

### 3.6 Command line / message bar

The bottom line shows messages when idle
(`yate 0.1.0 — F1 help, Ctrl+P quick open, : for ex mode` at startup); when
activated for input it shows a per-mode prefix:

| Mode | Prefix | Trigger |
|---|---|---|
| Command | `:` | `:` (vsc) or `:` in vim NORMAL mode |
| Find downward | magnifier icon | `Ctrl+F` (vsc), `/` (vim) |
| Find upward | `?` | `?` (vim) |
| Replace (step 1) | `Replace:` | `F4` |
| Replace (step 2) | `With:` | entered automatically after the find text |
| Shell | terminal icon | `F2`, `:!cmd` |
| Open file | `Open: ` | `Ctrl+O`, `:e` (without arguments) |
| Save as | `Save as: ` | saving an unnamed buffer |
| New file | `New file: ` | `a` in the file tree |
| New folder | `New folder: ` | `A` in the file tree |
| Rename | `Rename: ` | `r` in the file tree |
| Delete confirm | `Delete? ` | `d` or `Del` in the file tree |

The input line keeps history: `↑` / `↓` cycles through it; `Esc` or `Ctrl+C`
cancels. In find mode all matches highlight live as you type.

### 3.7 Command palette

- `Alt+Shift+P` opens the **command palette**: fuzzy-search all `:` commands
  and run the selected one with `Enter`.
- `Ctrl+P` opens **quick open** (the file panel): fuzzy-search workspace files
  and open the selected one.
- Both share one component; see section 9.

## 4. Quick Start

1. **Open a file**: pass a path at launch, `Ctrl+P` fuzzy open, or
   `Ctrl+O` / `:e` by path; opening a directory enters the file tree.
2. **Edit**: just type (the vsc keymap is modeless). `Enter` auto-indents;
   `Tab` inserts spaces or a tab character per yaterc.
3. **Save**: `Ctrl+S` or `:w`. Unnamed buffers pop a `Save as: ` input line;
   after saving, the workspace root follows the file's directory.
4. **Switch tabs**: `Ctrl+PageUp` / `Ctrl+PageDown`, or `:bn` / `:bp`.
5. **Quit**: `Ctrl+Q` or `:q`. With unsaved changes you get
   `unsaved changes — :q! to quit anyway`; `Ctrl+S` to save first, or
   `:q!` / `:wq` to force it.
6. **Help**: `F1` key reference (grouped by the current keymap + all `:`
   commands); `F8` or `:manual` opens this manual (`Esc` / `q` closes;
   `PgUp`/`PgDn` or the wheel scrolls).

> Note: clipboard operations (cut/copy/paste) use yate's **internal
> registers** and do not touch the system clipboard (see section 5.1).

## 5. Key Bindings

yate ships two keymaps:

- **`vsc`** (default): VS Code style, modeless.
- **`vim`**: NORMAL / INSERT / VISUAL / VISUAL-LINE modes + the `:` ex command line.

Ways to switch (any one of):

| Method | Action |
|---|---|
| In-session | `Ctrl+/` (some terminals send `Ctrl+_`) toggles between the two keymaps |
| Command | `:set keymap=vsc` / `:set keymap=vim`; quick aliases `:vsc`, `:vim`, `:normal` (`:normal` aliases `:vsc`) |
| Config | `keymap = "vsc"` or `"vim"` in yaterc |
| Command line | `yate --keymap vim` (beats yaterc) |

The `F1` help overlay always shows the complete bindings of the **current**
keymap, grouped by category, plus all `:` commands.

### 5.1 vsc keymap (default, modeless)

**Editing**

| Key | Action |
|---|---|
| `Enter` | Insert newline (auto-indent) |
| `Tab` | Indent / insert tab (affected by `use_spaces`) |
| `Backspace` | Delete character before cursor |
| `Delete` | Delete character after cursor |
| `Alt+Backspace` | Delete word before cursor |
| `Alt+D` | Delete word after cursor |
| `Ctrl+D` | Duplicate current line / selection |
| `Ctrl+Shift+K` | Delete current line |
| `Alt+↑` / `Alt+↓` | Move current line up / down |
| `Ctrl+]` | Increase indent (line / selection) |
| `Shift+Tab` | Decrease indent (line / selection) |
| `Ctrl+J` | Join lines |

**Navigation**

| Key | Action |
|---|---|
| `←` `→` `↑` `↓` | Move cursor |
| `Ctrl+←` / `Ctrl+→` | Move by word |
| `Home` | Line start (toggles between column 0 and first non-blank) |
| `End` | Line end |
| `Ctrl+Home` / `Ctrl+End` | Document start / end |
| `PageUp` / `PageDown` | Page up / down |

**Selection**

| Key | Action |
|---|---|
| `Shift+←` `Shift+→` `Shift+↑` `Shift+↓` | Select by character |
| `Ctrl+Shift+←` / `Ctrl+Shift+→` | Select by word |
| `Shift+Home` / `Shift+End` | Select to line start / end |
| `Ctrl+A` | Select all |
| `Esc` | Clear selection |

**History / Clipboard**

| Key | Action |
|---|---|
| `Ctrl+Z` | Undo (contiguous typing merges into one step) |
| `Ctrl+Y` | Redo |
| `Ctrl+X` | Cut selection / current line to the internal register |
| `Ctrl+C` | Copy selection / current line to the internal register |
| `Ctrl+V` | Paste from the internal register |

> Clipboard note: copy/cut/paste use the editor's internal yank/clipboard
> register and do not exchange data with the OS clipboard.

**File**

| Key | Action |
|---|---|
| `Ctrl+S` | Save file |
| `Ctrl+O` | Open file by path (`Open: ` input line) |
| `Ctrl+N` | New empty buffer |
| `Ctrl+W` | Close current tab |
| `Ctrl+Q` | Quit yate (blocked with unsaved changes) |
| `:` | Open the ex command line (`:w` `:q` `:e` …, see section 8) |

**Search**

| Key | Action |
|---|---|
| `Ctrl+F` | Find in file (live highlight, `Enter` jumps) |
| `F3` | Next match |
| `F4` | Find and replace (two-step input, replace all) |

**View / Tools**

| Key | Action |
|---|---|
| `Ctrl+P` | Quick open file (fuzzy match) |
| `Alt+Shift+P` | Command palette (run any `:` command) |
| `Ctrl+/` | Toggle vsc / vim keymap |
| `Ctrl+E` / `Ctrl+Shift+E` | Focus the file tree (`Ctrl+Shift+E` same as VS Code) |
| `Ctrl+1` | Focus the editor (same as VS Code) |
| `Ctrl+B` | Show / hide the file tree (same as `:explorer`) |
| `F2` | Run a shell command |

**Tabs**

| Key | Action |
|---|---|
| `Ctrl+PageUp` | Previous tab |
| `Ctrl+PageDown` | Next tab |

**Help**

| Key | Action |
|---|---|
| `F1` | Key reference (help overlay) |
| `F8` | Open the user manual (this manual, read-only) |

### 5.2 vim keymap (modal)

The status bar's bottom-left shows the current mode live. Number keys
(`1`–`9`) act as count prefixes and stack before most motions and operators,
e.g. `3j`, `2dd`, `5w`.

**Motions**

| Key | Action |
|---|---|
| `h` `l` `j` `k` | Left / right / down / up |
| `w` / `b` / `e` | Next word start / previous word start / word end |
| `0` | Line start (column 0) |
| `$` | Line end |
| `gg` | Document start; prefix a number to jump to a line (e.g. `5gg`) |
| `G` | Document end; a numeric prefix jumps to that line |
| `Ctrl+D` / `Ctrl+U` | Half page down / up |
| `Ctrl+F` / `Ctrl+B` | Page down / up |

**Entering insert mode**

| Key | Action |
|---|---|
| `i` | Insert before cursor |
| `a` | Insert after cursor |
| `I` | Insert at line start |
| `A` | Insert at line end |
| `o` | New line below and insert |
| `O` | New line above and insert |
| `Esc` | Back to NORMAL (cursor moves left one cell, like vim) |

**Editing**

| Key | Action |
|---|---|
| `x` | Delete character at cursor (countable) |
| `dd` | Delete (cut) current line |
| `yy` | Yank current line |
| `d{motion}` | Delete through motion (e.g. `dw`, `d$`, `dj`) |
| `y{motion}` | Yank through motion |
| `p` / `P` | Paste below / above |
| `u` | Undo |
| `Ctrl+R` | Redo |
| `J` | Join next line |
| `v` | Character visual mode (`-- VISUAL --`) |
| `V` | Line visual mode (`-- VISUAL LINE --`) |

**Commands**

| Key | Action |
|---|---|
| `/` | Find downward |
| `?` | Find upward |
| `n` / `N` | Next / previous match |
| `:` | ex command line (`:w` `:q` `:e` `:!` …) |

**Window switching**

| Key | Action |
|---|---|
| `Ctrl+W` `h` | Focus the file tree (left pane) |
| `Ctrl+W` `l` | Focus the editor (right pane) |
| `Ctrl+W` `Ctrl+W` | Cycle between file tree and editor |

In **INSERT mode**: `Esc` returns to NORMAL; `Ctrl+W` deletes the previous
word; `Ctrl+U` deletes to line start; `Backspace` / `Delete` / `Enter` / `Tab`
and arrows behave conventionally.
In **VISUAL mode**: `v` / `V` toggles or exits; `y` yanks the selection;
`d` / `x` deletes it; `:` `/` `?` exit visual mode first, then open the
corresponding input line; motions extend the selection.
Unmapped keys in NORMAL mode are swallowed and never insert text.

Under the vim keymap `Ctrl+F` pages instead of finding; `Ctrl+P` quick open,
`Alt+Shift+P` command palette, `F1` help and `F8` manual still work.

## 6. File Explorer

### 6.1 Opening and focusing

| Key | Action |
|---|---|
| `Ctrl+B` | Show / hide the file tree (the side bar hides itself when no directory is open) |
| `Ctrl+E` / `Ctrl+Shift+E` | Focus the file tree (with no directory open you get `no folder is open — use :e <path>`; a hidden tree is shown first) |
| `Ctrl+1` | Focus the editor |
| `Esc` (inside the tree) | Focus returns to the editor |

Open a workspace with `:e <directory>`, `Ctrl+O` with a directory path, or a
directory launch argument.

### 6.2 Keyboard operations inside the tree

With the file tree focused:

| Key | Action |
|---|---|
| `j` / `k` | Cursor down / up |
| `l` / `Enter` | Expand / collapse a directory; a file opens in the editor and focus returns there |
| `h` | Collapse the current directory; when already collapsed or on a file, jump to the parent |
| `a` | New file |
| `A` | New folder |
| `r` | Rename |
| `d` / `Delete` | Delete (type `y` or `yes` to confirm, anything else cancels) |
| `Esc` | Back to the editor |

Behavior notes:

- **Create**: created inside the cursor's directory (the file's sibling
  directory when the cursor is on a file). The input line placeholder shows the
  target directory. A new **file** opens immediately in the editor (VS Code
  behavior); a new **folder** keeps tree focus. Names may not be empty, `.`,
  `..`, or contain `/` `\` `:`; duplicates are rejected.
- **Rename**: the input line is prefilled with the current name; an already
  open tab for that file is re-pointed to the new path.
- **Delete**: deleting a directory recursively removes the whole subtree; open
  tabs underneath are closed (a message reports how many). Closing all tabs
  returns to an empty buffer.
- Printable characters typed inside the tree are swallowed and never leak into
  the editor.
- The directories `.git`, `.hg`, `.svn`, `__pycache__`, `.venv`, `venv`,
  `node_modules`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.idea`,
  `.vscode` never appear in the tree and are not indexed by quick open.
- When the tree refreshes (external changes, theme switch, file save), the
  expanded state of each directory is preserved.

## 7. Search and Replace

- **Find**: `Ctrl+F` (vsc) or `/` (vim, downward), `?` (vim, upward).
  Matches highlight live as you type; `Enter` jumps to the next match in the
  current direction and shows `[index/total]`; `F3` (vsc) or `n` / `N` (vim)
  keeps jumping. Matching starts near the cursor and wraps at the end of file.
- **Cancel**: `Esc` or `Ctrl+C` closes the find input line and clears the
  highlights.
- **Replace**: `F4` runs in two steps — first the find text (`Replace:`),
  then the replacement (`With:`). On confirm **all matches are replaced in one
  pass**, recorded as a single undo entry (one `Ctrl+Z` / `u` reverts
  everything). The result message shows the replacement count.
- Case-**insensitive** by default; plain-text matching (no regex).
- With no matches the message bar shows `no matches for '…'`; pressing `F3`
  with no active search hints to start one with `/` or `Ctrl+F`.

## 8. Command Line (ex commands)

Press `:` (both keymaps) to enter the command line. Commands may take
arguments separated by spaces. `Esc` / `Ctrl+C` cancels; `↑` / `↓` cycles
history. Unknown commands report
`not an editor command: … (try :help)`.

**File operations**

| Command | Alias | Description |
|---|---|---|
| `:w` | `:write` | Save the current file |
| `:q` | `:quit` | Quit yate (blocked with unsaved changes) |
| `:q!` | — | Discard changes and force quit |
| `:wq` | — | Save and quit |
| `:e [path]` | `:edit` | Open a file or directory; without arguments pops the `Open: ` input line |
| `:enew` | — | New empty buffer |
| `:bn` | `:bnext` | Next buffer / tab |
| `:bp` | `:bprev` | Previous buffer / tab |
| `:bd` | — | Close the current buffer / tab |

**Interface and tools**

| Command | Description |
|---|---|
| `:files` | Quick open file panel (same as `Ctrl+P`) |
| `:palette` | Command palette (same as `Alt+Shift+P`) |
| `:manual` | Open the user manual (`:manual zh` / `:manual en`, English by default) |
| `:help` | Key reference overlay (same as `F1`) |
| `:explorer` | Show / hide the file tree (same as `Ctrl+B`) |
| `:font` | Detect and (when needed) install the bundled Nerd Font, configure Windows Terminal |

**Options and appearance (session only, never written back to yaterc)**

| Command | Description |
|---|---|
| `:set keymap=vsc` or `:set keymap=vim` | Switch keymap |
| `:set theme=<name>` | Switch theme |
| `:vsc` | Switch to the vsc keymap |
| `:vim` | Switch to the vim keymap |
| `:normal` | Alias of `:vsc` |
| `:theme [name]` | Switch theme; without arguments lists the current theme and all available themes |
| `:colorscheme [name]` | Alias of `:theme` |

**Shell**

| Command | Description |
|---|---|
| `:!cmd` | Run a shell command (e.g. `:!git status`), see section 13 |

## 9. Command Palette and Quick Open

Two overlays share one component; both fuzzy-match (fzf-style subsequence
scoring: query characters must appear in order, word-start and path-boundary
hits score higher, matched characters are highlighted).

- **Quick open** (`Ctrl+P` or `:files`): lists every file under the workspace
  (or the current working directory when none is open; capped at 5000 entries,
  pruned directories excluded). `Enter` opens the file and focuses the editor.
- **Command palette** (`Alt+Shift+P` or `:palette`): lists all `:` commands
  with descriptions; `Enter` runs the selected one. Spaces in the query are
  ignored (typing `ctrlp` matches `ctrl p`).

Keys inside the overlays:

| Key | Action |
|---|---|
| `↑` / `↓` (or `Ctrl+P` / `Ctrl+N`) | Move the highlight |
| `Enter` | Open the selected file / run the selected command |
| `Esc` / `Ctrl+C` | Close the overlay |

At most 12 result rows show at once; with no matches you get `no matches`.

> Why `Alt+Shift+P` instead of `Ctrl+Shift+P`?
> Windows Terminal reserves `Ctrl+Shift+P` for its own command palette;
> `Alt+Shift+P` is unbound in common terminals, hence the default.

## 10. The yaterc Configuration File

yate uses a **Python-syntax config file named yaterc** (like vim's `vimrc`):
options are plain module-level variables, and the file may contain arbitrary
Python code.

### 10.1 Locations and load order

At startup files load in this order; **later loads override same-named
options from earlier ones**:

| Order | Source | Path | Notes |
|---|---|---|---|
| 1 | User | `~/.yate/yaterc` | Global personal config; skipped when absent |
| 2 | Project | `yaterc` found by walking **upward** from the current directory (or the opened file's directory) | Nearest one wins; suited for committing with a project |
| 3 | Command line | `yate -u <file>` | **Replaces** the previous two; only this file loads |

Special case: `yate -u NONE` skips config loading entirely.

Behavior details:

- All files execute in the **same namespace**, so project config sees and can
  override user-level variables.
- Unrecognized variables are **silently ignored** — handy for helper
  functions/constants.
- Read failures, syntax errors and runtime exceptions **never crash the
  editor**: the offending file is skipped, the problem is shown in the startup
  message bar prefixed `yaterc: ...`, and remaining files still load.
- Invalid values likewise never abort loading: the option keeps its default
  and the error appears in the message bar.

### 10.2 Option reference

| Option | Type | Default | Valid values | Description |
|---|---|---|---|---|
| `keymap` | `str` | `"vsc"` | `"vsc"` / `"vim"` | Key mapping; invalid values fall back with an error |
| `theme` | `str` | `"mocha"` | a registered theme name | Color scheme, see section 11; unknown names warn in the startup message bar |
| `tab_width` | `int` | `4` | integer 1–16 (booleans like `True`/`False` are rejected) | Spaces inserted by Tab, also Tab's display width |
| `use_spaces` | `bool` | `True` | `True` / `False` | `True`: Tab inserts spaces; `False`: a real tab character |
| `extensions` | `str` or `list[str]` | none | existing file/directory paths | Extra extension scripts, see 10.4 |

- `keymap` / `theme` apply at startup; `theme` is process-global state (like
  vim's colorscheme).
- `tab_width` / `use_spaces` propagate to **every new and opened buffer**.

Minimal example (copy `yaterc.example` from the repo root as a starting
point):

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

### 10.3 Registering custom themes

A `register_theme()` function is injected into the yaterc namespace. The
simplest approach is `dataclasses.replace` to copy a built-in theme and
override a few colors:

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # must be unique; reusing a built-in name overrides it
    label="My Mocha",
    accent="#89b4fa",       # primary: status bar bg, active tab, selection
    accent2="#cba6f7",      # secondary
))

theme = "my-mocha"
```

`Theme` fields by purpose: backgrounds (`bg`/`panel`/`surface`/`gutter_bg`/`border`),
overlays (`selection_bg`/`match_bg`/`match_active_bg`/`on_accent`),
foregrounds (`fg`/`fg_dim`/`fg_muted`/`fg_bright`),
accents (`accent`/`accent2`/`green`/`yellow`/`red`/`orange`),
mode blocks (`mode_normal_bg`/`mode_insert_bg`/`mode_visual_bg`/`mode_command_bg`),
syntax palette (`syn_keyword`/`syn_string`/`syn_number`/`syn_comment`/
`syn_function`/`syn_type`/`syn_constant`/`syn_builtin`/`syn_decorator`/
`syn_operator`/`syn_property`).

### 10.4 Extension paths (extensions)

`extensions` accepts one path string or a list of paths; each entry may be:

- **A directory**: every `*.py` inside is loaded (files starting with an
  underscore are skipped);
- **A `.py` file**: just that file.

```python
extensions = "~/.yate/myext.py"          # single file
extensions = [
    "~/.yate/extensions",                # directory: every .py inside
    "./tools/yate_exts",                 # relative: relative to this yaterc's directory
    "/opt/yate/extra.py",                # absolute
]
```

Rules:

- `~` expands to the home directory; **relative paths resolve against the
  directory of the yaterc declaring them**, so project configs keep working
  when the project moves.
- The `extensions` of user-level and project-level yaterc **accumulate**
  (unlike scalar options, where later wins); a repeated path loads only once.
- Non-existent paths or type errors surface as config errors in the message
  bar without affecting other options.
- Even if the same script is hit by rc, default directory and command line at
  once, it loads exactly once (deduplicated by resolved absolute path).

Beyond rc declarations, extensions also auto-load from the default
directories `./extensions/` and `~/.yate/extensions/`, and can be added with
`--ext <file>` / `--ext-dir <dir>` (see section 14).

## 11. Themes

The four built-in themes are all [Catppuccin](https://catppuccin.com/) flavors:

| Name | Theme | Mode |
|---|---|---|
| `mocha` | Catppuccin Mocha | dark (default) |
| `macchiato` | Catppuccin Macchiato | dark |
| `frappe` | Catppuccin Frappé | dark |
| `latte` | Catppuccin Latte | light |

Ways to switch:

| Method | Action |
|---|---|
| Command | `:theme latte`, `:colorscheme latte` (without arguments lists all available themes) |
| Option | `:set theme=latte` |
| Config | `theme = "latte"` in yaterc |
| Custom | register via `register_theme(...)` in yaterc, then switch by name (see 10.3) |

Switching affects only the current session; write it into yaterc to persist.
Unknown theme names raise an error listing the available themes.

## 12. Fonts and Nerd Font Icons

yate's file tree, tab bar and status bar draw icons from **Nerd Font** private
use area codepoints (folders, per-extension file type icons, status bar hint
icons, …). The terminal emulator decides which font to use — a program cannot
pick one — so yate provides a complete font fallback chain:

1. **Detection**: on Windows, registry font entries are scanned (HKLM and
   HKCU, entries containing "Nerd" whose file is loadable); macOS / Linux use
   `fc-list`.
2. **On-demand install**: without a detected Nerd Font, the bundled font is
   installed.
3. **Terminal configuration**: Windows Terminal, when detected, is configured
   automatically.

### 12.1 `yate --install-font` (or in-session `:font`)

Both entry points behave identically (`:font` runs inside the editor;
`--install-font` runs and exits):

- **Windows (no admin required, current user only)**
  - Font files are copied to `%LOCALAPPDATA%\Microsoft\Windows\Fonts\`;
  - Registry values are written under
    `HKCU\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts`. Each value
    stores the TTF's **full path** (bare file names are silently ignored by
    Windows, which makes icons render as replacement glyphs — the classic
    failure of older install approaches);
  - Stale same-family registry entries and duplicate copies such as
    `_0.ttf` are cleaned up;
  - `WM_FONTCHANGE` is broadcast so running apps pick up the font.
- **macOS / Linux**
  - Fonts are copied to `~/.local/share/fonts/yate/`, then `fc-cache -f`
    refreshes the cache.
- **Windows Terminal auto-configuration**
  - Locates
    `%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal*_8wekyb3d8bbwe\LocalState\settings.json`;
  - Sets `profiles.defaults`'s `font.face` to `JetBrainsMono NFM` (forced);
  - Also rewrites profiles that **explicitly override `font.face`**
    (e.g. Cascadia Mono) so their override cannot break icons; profiles
    without an explicit font inherit the default and are untouched;
  - Keeps a `settings.json.yate-bak` backup next to the settings file before
    writing;
  - Idempotent: already on the target font reports "already uses".

The bundled font is **JetBrains Mono Nerd Font Mono** (OFL license, see
`yate/resources/fonts/OFL.txt`); its GDI family name is `JetBrainsMono NFM`.
After installing, **restart the terminal**; if icons still do not show, see
the FAQ.

### 12.2 Manual installation

1. Download any Nerd Font from [nerdfonts.com](https://www.nerdfonts.com/)
   (or use the JetBrains Mono Nerd Font Mono TTF bundled with yate).
2. Install it into the system or user font directory (on Windows,
   right-click → "Install for current user").
3. Set the terminal's font to that Nerd Font and restart the terminal.

Verification: `yate --install-font` first prints its detection result
(`Nerd Font already available: ...` or
`no Nerd Font detected -- run 'yate --install-font' or ':font'`).

## 13. Shell Integration

- **Entry points**: `F2` opens the shell input line, or type `:!cmd` directly
  in the command line (e.g. `:!git status`, `:!ls -la`).
- **Working directory**: the opened workspace root if any; else the current
  document's directory; else the process start directory. The output overlay
  header shows the actual cwd and shell used.
- **Shell choice**: Windows uses `cmd.exe`; macOS / Linux use `/bin/sh`
  (equivalent to `subprocess.run(shell=True)`).
- **Output**: shown in a scrollable overlay titled `$ command`, annotated with
  the exit code (a green check for 0, a red cross otherwise); stdout and
  stderr are both shown. Timeout is 60 seconds, returning code 124.
- `Esc` / `q` / `Ctrl+C` closes the output overlay.
- Extensions can run commands silently via `api.shell(cmd)` (no output
  overlay).

## 14. Python Extensions

An extension is any `.py` file exposing `setup(api)` (optionally
`teardown(api)`):

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

What `api` provides:

| Category | API |
|---|---|
| Registration | `command(name, description)` decorator / `register_command(name, func, description)` to register `:` commands; `bind_key(key_spec, callback, keymap=...)` to bind keys (`"vsc"` / `"vim"` / `"both"`; `normal` aliases `vsc`); `register_action(name, func, description)` for named actions |
| Access | `api.buffer`, `api.doc`, `api.workspace`, `api.keymaps`, `api.app` |
| Services | `api.message(text)`, `api.shell(command)`, `api.open_path(path)`, `api.save()` |

Key specs use yate's key notation: `<ctrl-x>`, `<alt-x>`, `<shift-x>`,
`<f1>`…`<f12>`, `<enter>`, `<esc>`, `<tab>`, `<backspace>`,
`<up>`, `<down>`, `<left>`, `<right>`, `<home>`, `<end>`,
`<pageup>`, `<pagedown>`, `<delete>`, `<space>`; plain characters are written
directly as `"a"`, `"1"`, `":"`, `"/"`. Modifiers join with `-`, e.g.
`<alt-shift-p>`, `<ctrl-]>`.

Loading sources (combinable, deduplicated by resolved absolute path):

1. yaterc's `extensions` option (user level before project level);
2. Default directories `./extensions/` and `~/.yate/extensions/`
   (auto-loaded at startup);
3. Command line `--ext <file>` / `--ext-dir <dir>`.

Exceptions inside extensions never crash the editor; errors appear in the
message bar as `extension <name>: ...`. The repo ships a sample at
`extensions/example_ext.py` (providing the `:upper` / `:lower` / `:words` /
`:sh` commands and an `Alt+U` binding) usable as a template.

## 15. FAQ

**Icons render as boxes, diamonds or question marks?**
The terminal is not using a Nerd Font. Run `yate --install-font` (or
in-session `:font`), follow section 12, then **restart the terminal**. On
Windows Terminal, profiles that explicitly set another `font.face` are
rewritten by `--install-font` as well.

**`Ctrl+Shift+P` doesn't open yate's command palette?**
Windows Terminal reserves that combo. yate's command palette defaults to
`Alt+Shift+P`.

**A shortcut does nothing or gets "eaten" by the terminal?**
Terminal emulators intercept some combos (e.g. `Ctrl+Shift+P`, `Ctrl+/` on
some terminals). Unbind it in the terminal settings, or use the equivalent
commands (`:explorer`, `:palette`, `:set keymap=...`, …).

**What if my config file is broken?**
No crash. The offending yaterc is skipped and the error appears in the
startup message bar prefixed `yaterc: ...`; invalid option values keep their
defaults. Use `yate -u NONE` to verify whether a problem is config-related.

**Quit reports unsaved changes?**
yate blocks quitting with unsaved modifications. `:w` then `:q`, or `:q!` to
discard, `:wq` to save and quit.

**Which languages get syntax highlighting?**
The built-in highlighter recognizes by extension: Python (`py`/`pyi`/`pyw`),
C (`c`/`h`), C++ (`cpp`/`cc`/`cxx`/`c++`/`hpp`/`hxx`/`h++`/`hh`/`ino`),
Java (`java`), Rust (`rs`), Go (`go`), JavaScript (`js`/`mjs`/`cjs`/`jsx`),
TypeScript (`ts`/`tsx`/`mts`/`cts`), Shell (`sh`/`bash`/`zsh`/`fish`),
JSON (`json`/`jsonc`), Markdown (`md`/`markdown`/`mdx`), TOML (`toml`),
INI (`ini`/`cfg`/`conf`/`properties`), YAML (`yaml`/`yml`).
Everything else renders as plain text.

**Some files report not a text file?**
yate decides editability by an extension whitelist (common code/text suffixes
plus suffix-less names like `Dockerfile`, `Makefile`, `README`, `License`);
suffix-less files are sniffed — the first 2048 bytes must be valid UTF-8 and
contain no NUL byte.

**How is file encoding handled?**
On open it tries UTF-8 → the system's preferred encoding → cp1252 sniffing;
line endings are normalized to LF and saved as LF too (Windows CRLF files are
saved back as consistent LF). The status bar's right side shows the current
file type and encoding.

**Do CJK/emoji align correctly?**
Rendering measures terminal cell widths: wide characters (CJK, fullwidth,
most emoji) occupy 2 columns, combining characters 0, and tabs expand to the
`tab_width` alignment.

**Forgot a key binding or command?**
`F1` shows the full reference for the current keymap plus all `:` commands;
`F8` / `:manual` opens this manual.

## 16. Key Binding Cheat Sheet

vsc keymap (default):

| Key | Action | Key | Action |
|---|---|---|---|
| `Ctrl+S` | Save | `Ctrl+P` | Quick open file |
| `Ctrl+O` | Open file | `Alt+Shift+P` | Command palette |
| `Ctrl+N` | New buffer | `:` | ex command line |
| `Ctrl+W` | Close tab | `Ctrl+F` | Find |
| `Ctrl+Q` | Quit | `F3` | Next match |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo | `F4` | Find & replace |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste | `Ctrl+B` | Toggle file tree |
| `Ctrl+A` | Select all | `Ctrl+E` | Focus file tree |
| `Ctrl+D` | Duplicate line/selection | `F2` | Shell command |
| `Ctrl+Shift+K` | Delete line | `Ctrl+/` | Toggle keymap |
| `Alt+↑` / `Alt+↓` | Move line | `Ctrl+PageUp`/`PageDown` | Switch tab |
| `Ctrl+]` / `Shift+Tab` | Indent / dedent | `F1` | Key help |
| `Ctrl+J` | Join lines | `F8` | User manual |

Inside the file tree: `j`/`k` move · `l`/`Enter` open/expand · `h` collapse ·
`a` new file · `A` new folder · `r` rename · `d`/`Del` delete (`y` confirms) ·
`Esc` back to editor.

vim keymap:

| Key | Action | Key | Action |
|---|---|---|---|
| `h j k l` | Move | `i a I A o O` | Enter insert mode |
| `w b e` | Word motions | `Esc` | Back to NORMAL |
| `0` / `$` | Line start / end | `x` | Delete character |
| `gg` / `G` | Document start / end (line number prefix) | `dd` / `yy` | Delete / yank line |
| `Ctrl+D` / `Ctrl+U` | Half page down / up | `d{motion}` / `y{motion}` | Delete / yank through motion |
| `Ctrl+F` / `Ctrl+B` | Page down / up | `p` / `P` | Paste below / above |
| `v` / `V` | Visual / line visual | `u` / `Ctrl+R` | Undo / redo |
| `/` / `?` | Find down / up | `J` | Join lines |
| `n` / `N` | Next / previous match | numeric prefix | Count (e.g. `3j`, `2dd`) |
| `:` | ex command line | `Ctrl+W` / `Ctrl+U` (insert mode) | Delete word / to line start |

Command line cheat sheet: `:w` `:q` `:q!` `:wq` `:e` `:enew` `:bn` `:bp` `:bd`
`:files` `:palette` `:manual` `:help` `:explorer` `:font`
`:set keymap=…` `:set theme=…` `:vsc` `:vim` `:theme` `:colorscheme` `:!cmd`

---

*yate 0.1.0 — MIT License — built with Textual*
