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
13. Integrated Terminal
14. Shell Integration
15. Python Extensions
16. Language servers (LSP)
17. FAQ
18. Key Binding Cheat Sheet

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
| `--theme-dir DIR` | Load custom `*.py` color themes from a directory (repeatable; also accepts a single `*.py` file; defaults to `./themes` and `~/.yate/themes`); see section 10.3 |
| `--theme NAME` | Color theme to start with (built-in or a registered custom theme); overrides the `theme` set in yaterc |
| `--install-font` | Install the bundled Nerd Font for the current user (configures Windows Terminal when needed), then exit without entering the UI |
| `--version` | Show the version |
| `--changelog [LANG]` | Print the changelog (`en` by default, or `zh`) and exit — no UI is started |
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
yate --theme-dir ./themes   # load custom color themes from a directory
yate --theme my-mocha       # start with a (custom) color theme
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
  see the FAQ in section 17: Python, C/C++, Java, Rust, Go,
  JavaScript/TypeScript, Shell, JSON, Markdown, TOML, INI, YAML).
- Selections and search matches (the active match in a stronger color) render
  as theme-colored overlays.
- An empty unnamed buffer shows the welcome page: the YATE figlet banner,
  version and common key hints. The welcome page appears once at startup:
  typing into it or creating a buffer with `:enew` (and the "new empty
  buffer" action) dismisses it, and it never comes back when switching tabs;
  run `:welcome` to show it again (on an empty unnamed buffer).

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
(`yate 0.1.0 — F1 help, Ctrl+P quick open, Alt+Shift+P command palette` in
vsc mode; `-- NORMAL -- (F1 help, : commands)` in vim mode); when
activated for input it shows a per-mode prefix:

| Mode | Prefix | Trigger |
|---|---|---|
| Command | `:` | `:` in vim NORMAL mode; `F5` in vsc mode (or command palette) |
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

**Feedback colors.** Every command outcome takes over the line: green means
success (`:w`, `:set …`, `:term` …), yellow means a warning or a blocked
action (`:q` with unsaved changes, unknown command, `:bn` with one tab), red
means an error. Commands that open a full-screen overlay (`:manual`, `:help`,
`:files`, `:palette`, `:diagnostics`, shell-command output) reset the line to
its idle hint first, so a previous command's message never reappears, stale,
when the overlay closes.

### 3.7 Command palette

- `Alt+Shift+P` opens the **command palette**: lists every `:` command
  (gear icon) and named action (keyboard icon), fuzzy-searchable by full
  name (command descriptions match too); `Enter` runs the selected entry.
- `Ctrl+P` opens **quick open** (the file panel): fuzzy-search workspace files
  and open the selected one.
- Both share one component; see section 9.

### 3.8 Integrated terminal

- A bottom panel (between the editor and the status bar) hosts a real shell
  over a pseudo terminal; `` Ctrl+` `` toggles it and focuses the shell.
- It stays alive while hidden, restarts on any key after the shell exits,
  and is configurable via `shell` / `terminal_height`; see section 13.

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
   `PgUp`/`PgDn` or the wheel scrolls; `/` or `Ctrl+F` searches the
   manual text, `Enter` / `Shift+Enter` jump between matches, `n` / `N`
   repeat the last search after closing the search bar).
7. **Terminal**: press `` Ctrl+` `` to open the integrated shell at the bottom
   (`:term` / `:termclose` do the same); the shell keeps running while the
   panel is hidden.

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
| `Ctrl+G` | Go to line: type a line number and press Enter (or just run `:42`; `:+5` is relative) |

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

> `:` is **not** a vsc-mode binding — it is typed into the buffer like any
> other character. To run ex commands in vsc mode press `F5` to open the
> command line (type `w`, `q`, … without the leading colon), or open the
> command palette with `Alt+Shift+P` (section 3.7).

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
| `F5` | Command line (ex commands: `:w` `:q` `:e` …; `Esc` closes) |
| `Ctrl+/` | Toggle vsc / vim keymap |
| `Ctrl+E` / `Ctrl+Shift+E` | Focus the file tree (`Ctrl+Shift+E` same as VS Code) |
| `Ctrl+1` | Focus the editor (same as VS Code) |
| `Ctrl+B` | Show / hide the file tree (same as `:explorer`) |
| `` Ctrl+` `` | Show / hide the integrated terminal (see section 13) |
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
| `F8` | Open the user manual (this manual, read-only; `/` or `Ctrl+F` searches inside it) |

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
| `Ctrl+G` | Open the go-to-line prompt, type a line number and press Enter (same as `:42`) |
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

**Panes and windows (`Ctrl+W` prefix in NORMAL mode; see 8.1)**

| Key | Action |
|---|---|
| `Ctrl+W` `s` / `v` | Horizontal / vertical split (no argument clones the current document) |
| `Ctrl+W` `q` / `o` | Close the active pane / keep only the active pane (same as `:only`) |
| `Ctrl+W` `h` `j` `k` `l` | Move focus to the pane in that direction (`h` can reach the file tree on the left) |
| `Ctrl+W` `Ctrl+W` | Cycle through the editor panes and the file tree |
| `Ctrl+W` `+` / `-` | Grow / shrink the active pane's height |
| `Ctrl+W` `<` / `>` | Shrink / grow the active pane's width |
| `Ctrl+W` `=` | Equalize panes in the same split group |
| From the file tree | `Ctrl+W` `h` stays in the tree; `l` / `j` / `k` returns to the editor |

In **INSERT mode**: `Esc` returns to NORMAL; `Ctrl+W` deletes the previous
word; `Ctrl+U` deletes to line start; `Backspace` / `Delete` / `Enter` / `Tab`
and arrows behave conventionally.
In **VISUAL mode**: `v` / `V` toggles or exits; `y` yanks the selection;
`d` / `x` deletes it; `:` `/` `?` exit visual mode first, then open the
corresponding input line; motions extend the selection.
Unmapped keys in NORMAL mode are swallowed and never insert text.

Under the vim keymap `Ctrl+F` pages instead of finding; `Ctrl+P` quick open,
`Alt+Shift+P` command palette, `` Ctrl+` `` integrated terminal, `F1` help and
`F8` manual still work.

## 6. File Explorer

### 6.1 Opening and focusing

| Key | Action |
|---|---|
| `Ctrl+B` | Show / hide the file tree (focuses the tree when shown; the side bar hides itself when no directory is open) |
| `Ctrl+E` / `Ctrl+Shift+E` | Focus the file tree (with no directory open you get `no folder is open — use :e <path>`; a hidden tree is shown first) |
| `Ctrl+1` | Focus the editor |
| `Esc` (inside the tree) | Focus returns to the editor |

Open a workspace with `:e <directory>`, `Ctrl+O` with a directory path, or a
directory launch argument.

The launch argument decides the initial side-bar state: a **directory**
argument shows the file tree (browse mode); a **file** argument (including a
not-yet-created file path) starts with the tree hidden and focus in the
editor (press `Ctrl+B` or run `:explorer` to reveal it; the workspace root is
the file's parent directory). Starting with no argument hides it as well.

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
| `H` | Toggle hidden (dotfile) visibility |
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
- **File filtering**: dot-prefixed files (`.env`, `.eslintrc`, ...) are hidden
  by default — press `H` to toggle. Directories like `.git`, `.hg`,
  `__pycache__`, `.venv`, `node_modules` are always hidden. yate also reads
  `.gitignore` / `.yateignore` files from the workspace root and each
  subdirectory, applying their glob patterns (supports `!` negation and
  trailing `/` for directory-only). Set `show_hidden = True` in yaterc to
  change the default.
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

Press `:` in vim NORMAL mode to enter the command line. In vsc mode press
`F5` to open the command line (or use the command palette `Alt+Shift+P`),
since `:` is an ordinary editable character there. Commands may take
arguments separated by spaces. `Esc` / `Ctrl+C` cancels; `↑` / `↓` cycles
history. Unknown commands report
`not an editor command: … (try :help)`.

### 8.1 Split panes (`:split` / `:vsplit`)

Like vim, the editor area can be split into multiple panes. Each pane shows
one document and keeps its **own cursor, selection and scroll position** —
the same file in two panes never interferes with itself.

| Command | Alias | Description |
|---|---|---|
| `:split [path]` | `:sp` | Horizontal split (two panes stacked); no argument opens the current document in the new pane |
| `:vsplit [path]` | `:vs` | Vertical split (two panes side by side); no argument opens the current document in the new pane |
| `:only` | — | Keep only the active pane, close the rest (documents stay open as tabs / hidden buffers) |
| `:close` | `:cl` | Close the active pane (no-op on the last one; use `:q` to quit; same as `Ctrl+W q`) |

- With a path, that file opens in the new pane; relative paths resolve against
  the current document's directory first, then the working directory; a
  directory argument opens the folder in the file tree.
- The vim keymap provides `Ctrl+W` chords (see the window table in 5.2).
  Under the vsc keymap there are no chords — run the same commands from the
  `F5` command line.
- Close a pane with `:close` (alias `:cl`) or vim's `Ctrl+W q`: only the
  pane goes away, the document stays open as a tab / hidden buffer; it is a
  no-op on the last pane and never blocks on unsaved changes.
- `:q` / `:quit` **always quit the whole yate**, even with several panes
  open (blocked on unsaved changes; `:q!` discards them and forces the
  quit, `:wq` saves first).

**Go to line.** Typing just a number and pressing Enter jumps to that line
(`:42`, equivalent to VS Code's `Ctrl+G`; `Ctrl+G` opens the same go-to-line
prompt in both keymaps). Numbers outside the document clamp to the first or
last line; a leading sign makes the jump relative — `:+5` moves five lines
down, `:-2` two lines up.

**Tab completion.** Press `Tab` to complete the typed text (bash-style):
command names are completed first; once a command is followed by a space,
`Tab` completes its argument — filesystem paths for `:e`/`:edit`, theme
names for `:theme`/`:colorscheme`, option keys and values for `:set`,
syntax type names (including `auto`) for `:filetype`/`:ft`/`:language`
and `:set filetype=`, and `en`/`zh` for `:manual`. The first `Tab`
expands to the longest common prefix of all matches (a single match is
inserted immediately); repeated `Tab`s cycle through every match.

**File operations**

| Command | Alias | Description |
|---|---|---|
| `:w` | `:write` | Save the current file |
| `:q` | — | Quit yate entirely (even with multiple panes; blocked on unsaved changes, `:q!` forces) |
| `:quit` | — | Alias of `:q` |
| `:q!` | — | Discard changes and force quit |
| `:wq` | — | Save and quit |
| `:e [path]` | `:edit` | Open a file or directory; without arguments pops the `Open: ` input line |
| `:split [path]` | `:sp` | Horizontal split; no argument clones the current document (see 8.1) |
| `:vsplit [path]` | `:vs` | Vertical split; no argument clones the current document (see 8.1) |
| `:only` | — | Keep only the active pane |
| `:close` | `:cl` | Close the active pane (no-op on the last pane) |
| `:enew` | — | New empty buffer (also dismisses the welcome page for this session) |
| `:welcome` | — | Show the welcome page again (on an empty unnamed buffer) |
| `:bn` | `:bnext` | Next buffer / tab |
| `:bp` | `:bprev` | Previous buffer / tab |
| `:bd` | — | Close the current buffer / tab |
| `:42` | — | Jump to line 42 (any bare number in the command line is a line jump, same as `Ctrl+G`); `:+3`/`:-2` jump relative to the current line |

**Interface and tools**

| Command | Description |
|---|---|
| `:files` | Quick open file panel (same as `Ctrl+P`) |
| `:palette` | Command palette (same as `Alt+Shift+P`) |
| `:manual` | Open the user manual (`:manual zh` / `:manual en`, English by default) |
| `:changelog` | Open the bilingual changelog viewer (`:changelog zh` / `:changelog en`, English by default; search and close work like `:manual`) |
| `:help` | Key reference overlay (same as `F1`) |
| `:explorer` | Show / hide the file tree (same as `Ctrl+B`) |
| `:term` | Show / focus the integrated terminal (alias `:terminal`, see section 13); the line confirms `terminal shown` |
| `:termclose` | Hide the integrated terminal (the shell keeps running); confirms `terminal hidden`, warns if it was already hidden |
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
| `:set shell=<command>` | Set the terminal shell command (takes effect on the next shell launch) |
| `:set terminal_height=<n>` | Terminal panel height in rows (`3`–`40`), applied immediately |
| `:set filetype=<type>` | Force the current buffer's syntax type (aliases `ft` / `language` / `lang`); see the FAQ in section 17 |
| `:filetype [type]` | Same as above; without arguments shows the current type and all available types (aliases `:ft`, `:language`) |

**Shell**

| Command | Description |
|---|---|
| `:!cmd` | Run a shell command (e.g. `:!git status`), see section 14 |

## 9. Command Palette and Quick Open

Two overlays share one component; both fuzzy-match (fzf-style subsequence
scoring: query characters must appear in order, word-start and path-boundary
hits score higher, matched characters are highlighted).

- **Quick open** (`Ctrl+P` or `:files`): lists every file under the workspace
  (or the current working directory when none is open; capped at 5000 entries,
  pruned directories excluded). `Enter` opens the file and focuses the editor.
- **Command palette** (`Alt+Shift+P` or `:palette`): lists every `:` command
  (gear icon) and every named action (keyboard icon, built-in and extension
  registered), each shown by its full name, fuzzy-searchable by full name.
  In command mode the description text matches as well (description hits
  rank below name hits). `Enter` runs the selected entry. Spaces in the query
  are ignored (typing `ctrlp` matches `ctrl p`).

Keys inside the overlays:

| Key | Action |
|---|---|
| `↑` / `↓` (or `Ctrl+P` / `Ctrl+N`) | Move the highlight |
| `Tab` / `Shift+Tab` | Cycle the highlight forward / backward; **with a single match left, `Tab` runs/opens it immediately** (bash-style) |
| `Enter` | Open the selected file / run the selected command or action |
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
| `theme_dirs` | `str` or `list[str]` | none | existing file/directory paths | Directories (or a single `*.py` file) holding custom color themes, see 10.3 |
| `shell` | `str` | platform default (see section 13) | non-empty string | Shell command for the integrated terminal, with optional arguments (e.g. `"pwsh -NoLogo"`); an existing file path may contain spaces |
| `terminal_height` | `int` | `12` | integer 3–40 (booleans/floats rejected) | Integrated terminal panel height in rows |
| `show_hidden` | `bool` | `False` | `True` / `False` | Show dot-prefixed hidden files in the explorer by default |
| `language_servers` | `list[dict]` | none | see 16.2 | Declarative language server registrations; a server **auto-activates** when a file of a matching language is opened — no extension needed |

- `keymap` / `theme` apply at startup; `theme` is process-global state (like
  vim's colorscheme).
- `tab_width` / `use_spaces` propagate to **every new and opened buffer**.
- `shell` is read when a terminal shell is launched (restart the shell after
  changing it); `terminal_height` also applies immediately via
  `:set terminal_height=<n>`.
- `language_servers` is registered with the LSP manager at startup; the
  server process starts lazily, only when a matching file is opened
  (see 16.2).

Minimal example (copy the bundled `yate/yaterc.example` as a starting
point):

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

### 10.3 Custom theme directories (`theme_dirs`)

A `register_theme()` function is injected into the yaterc namespace, so a
handful of tweaks can live directly in a yaterc file. For a library of
reusable themes, point `theme_dirs` at one or more directories; every
`*.py` inside is loaded at startup (files starting with an underscore are
skipped), and a single `*.py` file is accepted too:

```python
theme_dirs = "~/.yate/themes"           # one directory (a string is enough)
theme_dirs = [
    "~/.yate/themes",                   # ~ is expanded
    "./team-themes",                    # relative: relative to this yaterc's directory
    "./extras/solarized.py",            # a single theme file
]
theme = "my-mocha"                      # pick a theme registered by those files
```

A theme file is ordinary Python with `Theme` and `register_theme()` already
in scope; regular `import` statements work as well. The simplest approach
is `dataclasses.replace` to copy a built-in theme and override a few colors:

```python
# ~/.yate/themes/my_mocha.py
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # must be unique; reusing a built-in name overrides it
    label="My Mocha",
    accent="#89b4fa",       # primary: status bar bg, active tab, selection
    accent2="#cba6f7",      # secondary
))
```

Themes can also be placed in the default locations without any
configuration: `./themes` next to the working directory and
`~/.yate/themes` are scanned automatically, or pass one-off directories on
the command line with `--theme-dir DIR` (repeatable). Load precedence when
the same name is registered more than once (later wins):

1. built-in themes (lowest)
2. `./themes`, `~/.yate/themes`
3. `theme_dirs` in yaterc (user rc first, project rc after)
4. `--theme-dir` on the command line (highest)

A broken theme file never aborts startup: its error is shown in the
startup message line and the remaining files still load. Once registered,
a custom theme is selected like any other: `theme = "my-mocha"` in yaterc,
`:theme my-mocha` at runtime, or `:theme` to list all registered names.

`Theme` fields by purpose: backgrounds (`bg`/`panel`/`surface`/`gutter_bg`/`border`),
overlays (`selection_bg`/`match_bg`/`match_active_bg`/`on_accent`),
foregrounds (`fg`/`fg_dim`/`fg_muted`/`fg_bright`),
accents (`accent`/`accent2`/`green`/`yellow`/`red`/`orange`),
mode blocks (`mode_normal_bg`/`mode_insert_bg`/`mode_visual_bg`/`mode_command_bg`),
syntax palette (`syn_keyword`/`syn_string`/`syn_number`/`syn_comment`/
`syn_function`/`syn_type`/`syn_constant`/`syn_builtin`/`syn_decorator`/
`syn_operator`/`syn_property`).

> For the full `Theme` field reference, a from-scratch theme example, and the
> complete load precedence, see [`yate/docs/themes.en.md`](../docs/themes.en.md).

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

Beyond rc declarations, yate first auto-loads the **bundled extensions**
(`python_lsp` and `csharp_highlight` from `yate/extensions/`, regardless of
the working directory), then scans the default directories `./extensions/`
and `~/.yate/extensions/`, and finally accepts `--ext <file>` /
`--ext-dir <dir>` (see section 15). To skip a bundled default, list its stem
in yaterc: `disabled_extensions = ["python_lsp"]`.

> For the full extension API reference (commands, actions, key bindings,
> buffer/doc/workspace access, LSP registration), see
> [`yate/docs/extensions.en.md`](../docs/extensions.en.md).

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
| CLI flag | `yate --theme latte` (overrides the yaterc `theme`) |
| Custom | inline `register_theme(...)` in yaterc, or `*.py` files under `theme_dirs` / `--theme-dir`; then switch by name (see 10.3) |

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

## 13. Integrated Terminal

yate embeds a real shell in a bottom panel (VS Code style), connected through
a pseudo terminal, so full-screen TUI programs (vim, htop, python REPL, …)
work directly inside it. On Windows the backend is ConPTY (Windows 10 1809+);
on macOS / Linux it is the POSIX `pty` device.

**Opening / hiding**

- `` Ctrl+` `` toggles the panel (grave accent, the key above Tab). Opening it
  focuses the terminal; hiding it returns focus to the editor.
- On **Windows conhost / legacy xterm**, `` Ctrl+` `` and `Ctrl+Space` are the
  same NUL byte. In the editor that byte always means `Ctrl+Space` (manual
  completion) and never opens the terminal; while the terminal is open it
  still closes it. Use `:term` or the command palette to open a terminal.
- Hiding does **not** kill the shell: the process keeps running, exactly like
  VS Code, and toggling again brings the same session back.
- `:term` (alias `:terminal`) shows and focuses the panel; `:termclose` hides
  it.

**Using the terminal**

- Every keystroke is forwarded to the shell, including control keys and
  pasted text (bracketed paste is supported). `` Ctrl+` `` remains intercepted so
  you can hide the panel from the keyboard.
- Scroll back with `Shift+PageUp` / `Shift+PageDown` or the mouse wheel; the
  scrollback keeps the last 5000 lines.
- The panel header shows the shell name, the title reported by the program
  (OSC escape sequences), and its state: `starting` / `running` / `exited`.
- When the shell exits, the last line shows
  `[shell exited (exit code N); any key restarts]` — press any key to spawn a
  fresh shell.
- The panel resizes with the window; the shell receives SIGWINCH /
  ResizePseudoConsole automatically.

**Default shell and configuration**

Without configuration, yate picks:

- Windows: `pwsh` if found on `PATH`, else Windows PowerShell
  (`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, launched
  with `-NoLogo`), else `%COMSPEC%` / `cmd.exe`.
- macOS / Linux: `$SHELL`, else `bash`, else `/bin/sh`.

Set `shell` in yaterc to override it (see 10.2):

```python
shell = "pwsh -NoLogo"
```

The value is split like a shell command line; on Windows, if the value is an
existing file path it is used as-is, so quoted paths containing spaces work
(e.g. `shell = r"C:\Program Files\PowerShell\7\pwsh.exe"`). Changing `shell`
takes effect the next time a shell is launched (toggle the panel after the
current shell exits, or restart yate).

The panel height defaults to 12 rows; `terminal_height` accepts `3`–`40`, and
`:set terminal_height=<n>` changes it immediately for the current session.

## 14. Shell Integration

- **Entry points**: `F2` opens the shell input line, or type `:!cmd` directly
  in the command line (e.g. `:!git status`, `:!ls -la`).
- **Working directory**: the opened workspace root if any; else the current
  document's directory; else the process start directory. The output overlay
  header shows the actual cwd and shell used.
- **Shell choice**: Windows uses `cmd.exe`; macOS / Linux use `/bin/sh`
  (equivalent to `subprocess.run(shell=True)`).
- **Non-blocking**: commands execute in a background worker thread — the
  editor keeps responding (you can even open F1 help while a command runs);
  the message line shows `running: …` and the output overlay opens when the
  command finishes.
- **Output**: shown in a scrollable overlay titled `$ command`, annotated with
  the exit code (a green check for 0, a red cross otherwise); stdout and
  stderr are both shown. Timeout is 60 seconds, returning code 124.
- `Esc` / `q` / `Ctrl+C` closes the output overlay.
- Extensions can run commands silently via `api.shell(cmd)` (no output
  overlay).

## 15. Python Extensions

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
| Language servers | `api.lsp.register_server(...)` (see section 16); `api.lsp.statuses()` returns `{name: state}` |
| Syntax highlighting | `api.highlight.register(spec, *extensions)` registers or overrides a declarative custom language (`LangSpec`); usable from `:set filetype=` once registered |

Key specs use yate's key notation: `<ctrl-x>`, `<alt-x>`, `<shift-x>`,
`<f1>`…`<f12>`, `<enter>`, `<esc>`, `<tab>`, `<backspace>`,
`<up>`, `<down>`, `<left>`, `<right>`, `<home>`, `<end>`,
`<pageup>`, `<pagedown>`, `<delete>`, `<space>`; plain characters are written
directly as `"a"`, `"1"`, `":"`, `"/"`. Modifiers join with `-`, e.g.
`<alt-shift-p>`, `<ctrl-]>`.

Loading sources (combinable, deduplicated by resolved absolute path):

1. yaterc's `extensions` option (user level before project level);
2. The bundled extensions in `yate/extensions/` (`python_lsp`,
   `csharp_highlight`; auto-loaded from any working directory; skip stems
   with yaterc's `disabled_extensions`);
3. Default directories `./extensions/` and `~/.yate/extensions/`
   (auto-loaded at startup);
4. Command line `--ext <file>` / `--ext-dir <dir>`.

Exceptions inside extensions never crash the editor; errors appear in the
message bar as `extension <name>: ...`. The bundled template
`yate/extensions/example_ext.py.example` (use it after dropping the
`.example` suffix; it provides the `:upper` / `:lower` / `:words` / `:sh`
commands and an `Alt+U` binding) is a good starting point;
`yate/extensions/csharp_highlight.py` shows how `api.highlight.register` adds
highlighting for C# (`.cs`/`.csx`).

> For the full extension API reference (commands, actions, key bindings,
> buffer/doc/workspace access, LSP registration, custom syntax highlighting
> and the `LangSpec` fields), see
> [`yate/docs/extensions.en.md`](../docs/extensions.en.md).

## 16. Language servers (LSP)

yate ships a small built-in [LSP](https://microsoft.github.io/language-server-protocol/)
client (no extra dependencies): it spawns language server processes over
stdio, speaks JSON-RPC itself, and provides:

* **Autocomplete** -- a popup appears automatically while typing an
  identifier (after the server's trigger characters, e.g. `.` in Python),
  and `Ctrl+Space` requests suggestions manually (it also works with no
  language server). Navigate with `↑` / `↓`, accept with `Tab` or `Enter`,
  dismiss with `Esc`. When no language server is available for the current
  file, the popup falls back to the built-in **buffer completion**: words
  already typed, collected from every open buffer (plus filesystem paths
  when the typed prefix contains `/`, `\` or `~`), with no external process
  required.
* **Diagnostics** -- errors and warnings are underlined in the editor, the
  gutter shows `✖` (error) / `▲` (warning) and tints the line number, the
  diagnostic under the cursor is echoed on the message bar, and the status
  bar shows live counts. `:diagnostics` lists every diagnostic of the
  current file in an output screen.

Documents are synchronized whole-text on open / save / after a short idle
debounce while typing. Servers start lazily when the first matching file is
opened, one process per (server, project root). The status bar shows the
server name when ready, `LSP…` while starting, and `LSP ✖` when the server
could not start.

### 16.1 Python (built-in extension)

`yate/extensions/python_lsp.py` is a bundled extension, auto-loaded from any
working directory; it registers a Python server for `.py` / `.pyi` files.
Skip it with `disabled_extensions = ["python_lsp"]` in yaterc. Install
either implementation yourself (neither is bundled):

```powershell
pip install python-lsp-server     # provides pylsp
# or
npm install -g pyright            # provides pyright-langserver
pip install pyright               # alternative, also installs the binary
```

Server discovery, in order:

1. The `YATE_PYTHON_LSP` environment variable: a full command line with
   shell-style quoting, e.g.
   `set YATE_PYTHON_LSP=C:\tools\pyright-langserver.cmd --stdio`.
   Setting it to `0`, `off`, `false`, `none` or `no` disables the Python
   server entirely (registration stays, nothing spawns).
2. `pyright-langserver` on `PATH` (started with `--stdio`).
3. `pylsp` on `PATH`.

If none is found, nothing is spawned and no error is shown until a Python
file is opened; the status bar then reports `LSP ✖`.

### 16.2 Declaring servers in yaterc (auto-activation)

Instead of writing an extension, declare language servers with the
`language_servers` yaterc option (section 10). Once configured, **no manual
command is needed**: when a file with a matching extension is opened, yate
starts the server automatically — one process per (server, project root),
lazily on the first match. Switching tabs, opening with `:e`, or changing
the type via `:set filetype=…` performs the didOpen/didClose automatically:

```python
language_servers = [
    {
        "name": "rust-analyzer",                  # required: status-bar name
        "command": "rust-analyzer",               # required: executable (non-empty)
        "args": [],                                # optional: command-line arguments
        "filetypes": ["rs"],                      # required: extensions without dot (".rs" works too)
        "language_ids": {"rs": "rust"},           # optional: filetype -> LSP languageId
        "root_markers": ["Cargo.toml", ".git"],   # optional: built-in markers used if absent
        # "env": {"RUST_LOG": "info"},            # optional: extra environment variables
        # "initialization_options": {...},        # optional: initializeOptions
        # "settings": {...},                      # optional: server settings
    },
]
```

Rules:

- The option is registered **after** extensions load: an entry with the same
  name replaces an extension registration (including the built-in Python
  server), so `"name": "python"` lets you customize the Python server command.
- As with scalar options, a later yaterc **replaces** the whole list rather
  than merging; a malformed entry is skipped with an error in the startup
  message bar while the remaining entries still register.
- `filetypes` / `args` / `root_markers` accept lists or tuples; leading dots
  on extensions are stripped (`".rs"` → `"rs"`, while dot-only values are an
  error); surrounding whitespace in `name` and `command` is trimmed. Unknown
  extra keys are ignored.
- Merely configuring servers spawns nothing; unnamed buffers and
  non-matching files are completely unaffected.

### 16.3 Registering servers from an extension

```python
def setup(api):
    api.lsp.register_server(
        "rust-analyzer",                       # server name (status bar)
        command="rust-analyzer",               # "" = known-missing, lazy fail
        args=[],
        filetypes=["rs"],                      # extensions without dot
        language_ids={"rs": "rust"},           # textDocument languageId
        root_markers=["Cargo.toml", ".git"],   # project-root probe files
        initialization_options=None,           # raw initializeOptions
        settings=None,                         # sent on didChangeConfiguration
        env=None,                              # extra environment variables
    )
```

`api.lsp.statuses()` returns `{name: "ready"|"starting"|"failed"|...}`.
Registering the same name twice replaces the previous config and drops its
cached process and diagnostics.

> For install commands and `register_server` recipes for mainstream
> languages (Rust, TypeScript, Go, C/C++, Bash, JSON, HTML/CSS, Lua, ...),
> see [`yate/docs/lsp.en.md`](../docs/lsp.en.md).

## 17. FAQ

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
discard, `:wq` to save and quit. `:q` / `:quit` quit the whole editor no
matter how many panes are open. To close just the active pane without
quitting, use `:close` / `:cl` or `Ctrl+W q` (the document stays open as a
tab and unsaved changes do not block).

**Which languages get syntax highlighting?**
The built-in highlighter recognizes by extension: Python (`py`/`pyi`/`pyw`),
C (`c`/`h`), C++ (`cpp`/`cc`/`cxx`/`c++`/`hpp`/`hxx`/`h++`/`hh`/`ino`),
Java (`java`), Rust (`rs`), Go (`go`), JavaScript (`js`/`mjs`/`cjs`/`jsx`),
TypeScript (`ts`/`tsx`/`mts`/`cts`), Shell (`sh`/`bash`/`zsh`/`fish`),
JSON (`json`/`jsonc`), Markdown (`md`/`markdown`/`mdx`), TOML (`toml`),
INI (`ini`/`cfg`/`conf`/`properties`), YAML (`yaml`/`yml`).
Everything else renders as plain text. With the optional tree-sitter
backend installed (`pip install yate[ts]`), Python and Shell are
highlighted through a real parser instead of word lists.

**How do I add highlighting for another language (or override one)?**
An extension can register a declarative `LangSpec` via
`api.highlight.register(spec, *extensions)` -- comment markers and word sets
for keywords/types/constants; the engine handles strings, numbers and
multiline state. Once registered it highlights automatically and works with
`:set filetype=`. The bundled `yate/extensions/csharp_highlight.py` provides
C# (`cs`/`csx`): it auto-loads at startup from any working directory (turn it
off with `disabled_extensions = ["csharp_highlight"]`), or load a modified
copy explicitly with `yate --ext csharp_highlight.py`. See section 4.7 of
[`yate/docs/extensions.en.md`](../docs/extensions.en.md) for the full field list.

For syntax-tree based highlighting of a custom language (e.g. your own
shell), an extension can bind a compiled tree-sitter grammar plus a
`highlights.scm` query via `api.syntax.register_tree_sitter(...)` --
requires `pip install yate[ts]`. See section 4.8 of
[`yate/docs/extensions.en.md`](../docs/extensions.en.md) and the template
`yate/extensions/yatesh_syntax.py.example`.

**How do I pick the syntax type manually (like VS Code's Change Language Mode / vim's `:set filetype`)?**
The type is normally detected from the file extension. For extension-less
files, misdetections or scratch buffers you can override it for the current
buffer only:

```
:set filetype=python   # language name or extension both work (python / .py / py)
:set ft=rs             # vim-style abbreviation; language/lang are synonyms
:filetype json         # standalone command with the same effect (aliases :ft, :language)
:filetype              # no argument: show the current type and all available types
:set filetype=auto     # clear the override, re-detect from the path extension
```

Highlighting and the type shown on the right of the status bar update
immediately; if a language server is registered for the type (section 16),
the document is re-bound to that server. In the command line, `Tab` cycles
through type names (`:set filetype=py<Tab>`, `:filetype r<Tab>`). An unknown
type is accepted (an LSP may still match it) but gets no built-in
highlighter; the message line says so.

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

## 18. Key Binding Cheat Sheet

vsc keymap (default):

| Key | Action | Key | Action |
|---|---|---|---|
| `Ctrl+S` | Save | `Ctrl+P` | Quick open file |
| `Ctrl+O` | Open file | `Alt+Shift+P` | Command palette |
| `Ctrl+N` | New buffer | `Ctrl+1` | Focus editor |
| `Ctrl+W` | Close tab | `Ctrl+F` | Find |
| `Ctrl+Q` | Quit | `F3` | Next match |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo | `F4` | Find & replace |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste | `Ctrl+B` | Toggle file tree |
| `Ctrl+A` | Select all | `Ctrl+E` | Focus file tree |
| `Ctrl+D` | Duplicate line/selection | `F2` / `F5` | Shell command / command line |
| `Ctrl+Shift+K` | Delete line | `Ctrl+/` | Toggle keymap |
| `Alt+↑` / `Alt+↓` | Move line | `Ctrl+PageUp`/`PageDown` | Switch tab |
| `Ctrl+]` / `Shift+Tab` | Indent / dedent | `F1` | Key help |
| `Ctrl+J` | Join lines | `F8` | User manual |
| `Ctrl+G` | Go to line (or `:42`) | `Ctrl+Home/End` | Document start / end |
| `Ctrl+Space` | Trigger autocomplete | palette `diagnostics` | List LSP diagnostics |
| `` Ctrl+` `` | Toggle integrated terminal | `Shift+PageUp/PageDown` | Terminal scrollback |

Inside the file tree: `j`/`k` move · `l`/`Enter` open/expand · `h` collapse ·
`a` new file · `A` new folder · `r` rename · `d`/`Del` delete (`y` confirms) ·
`H` toggle hidden files · `Esc` back to editor.

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
| `:` | ex command line (`:42` jumps to a line) | `Ctrl+W` / `Ctrl+U` (insert mode) | Delete word / to line start |
| `Ctrl+G` | Go to line | `` Ctrl+` `` | Toggle integrated terminal |
| `Ctrl+W` `s/v/q/o` | HSplit / vsplit / close pane / only | `Ctrl+W` `hjkl` | Move focus between panes |
| `Ctrl+W` `+-<>` | Resize pane height / width | `Ctrl+W` `=` / `Ctrl+W Ctrl+W` | Equalize / cycle focus |
| `Shift+PageUp/PageDown` | Terminal scrollback | | |

Command line cheat sheet: `:w` `:q` `:q!` `:wq` `:e` `:enew` `:welcome` `:sp` `:vs` `:only` `:42` `:+5` `:bn` `:bp` `:bd`
`:files` `:palette` `:manual` `:changelog` `:help` `:explorer` `:font` `:term` `:termclose`
`:set keymap=…` `:set theme=…` `:set shell=…` `:set terminal_height=…` `:set filetype=…` `:filetype …` `:vsc` `:vim` `:theme` `:colorscheme` `:!cmd`

## Appendix: Release & Bilingual Changelog Workflow

The root files `CHANGELOG.md` (English) and `CHANGELOG.zh.md` (Chinese) are
generated from git history by the `tools/changelog` module — **do not edit
them by hand**; human input only goes into the override table
`tools/changelog/zh_overrides.json`. The same content also ships inside the
package as `yate/resources/changelog.en.md` / `changelog.zh.md` (the pack
scripts refresh them with `generate --bundle-only` before building), for
runtime viewing. The single version source is `__version__` in
`yate/__init__.py`, which `pyproject.toml` reads dynamically via hatchling.

Three entry points show the changelog:

- browse the root `CHANGELOG*.md` on the repository web page;
- `yate --changelog [en|zh]` on the command line (prints and exits — no
  config is loaded, no UI is started);
- `:changelog [en|zh]` inside the TUI (document viewer screen; search works
  like `:manual`).

If a build lacks the changelog resources, every entry point shows a fixed
"no changelog is shipped" notice instead of failing.

Release workflow:

1. Edit `yate/__init__.py`: `__version__ = "0.2.0"` (single version source)
2. `git commit -m "chore(release): v0.2.0"`
3. `python -m tools.changelog zh-commit <hash> "中文摘要"` (add Chinese
   summaries for key entries as needed)
4. `python -m tools.changelog generate --online` (segment, classify, render
   all four outputs: the two root files plus the two bundled copies)
5. `git add CHANGELOG.md CHANGELOG.zh.md yate/resources/changelog.en.md
   yate/resources/changelog.zh.md tools/changelog/zh_overrides.json`
   then `git commit -m "docs: changelog for v0.2.0"`
6. `git tag -a v0.2.0 -m "v0.2.0"`; `git push --follow-tags`

Conventions: version segments are bounded by `vX.Y.Z` tags, falling back to
added `__version__` lines in `yate/__init__.py`; `chore(release)` commits act
as boundaries only and are not rendered as entries; breaking changes (`!:`
or `BREAKING CHANGE:`) are grouped at the top; entries without a Chinese
translation fall back to English with a `[缺中文]` marker and can be filled in
gradually via `zh-commit`; `python -m tools.changelog check` gates the
released sections in CI (the `[Unreleased]` section may lag and is refreshed
wholesale by `generate` at release time).

---

*yate 0.1.0 — MIT License — built with Textual*
