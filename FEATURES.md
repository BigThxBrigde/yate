# yate Features and Functionalities

**English** · [中文](FEATURES.zh.md)

*yate — yet another terminal editor*, a modern terminal text editor built on
[Textual](https://www.textualize.io/) (Python ≥ 3.12). This document is the
complete inventory of user-visible features in the current version; for a quick
start see [README.md](README.md), and for the full usage guide see the
[manual](yate/resources/manual.en.md) (`F8` / `:manual` inside the editor).

## 1. Editing Core

- Multi-buffer tabbed editing; the document session is decoupled from the UI
  (`editor_core` is pure logic, headlessly testable)
- Undo/redo; cut/copy/paste (synced to the system clipboard and internal registers)
- Multi-cursor editing (`add_cursor_below`, `Alt+C`) with cursor-aware line operations
- Auto-indent on newline, Tab / indent / dedent, delete word / line / join lines,
  move lines up/down
- Configurable `tab_width` (1–16) and `use_spaces`; readonly mode (editing and
  saving rejected)
- Vim-style named registers `"a-z` (the unnamed register mirrors the system clipboard)
- Count multipliers (e.g. `2d3w`), repeat find with `f/F/t/T` + `;`/`,`

## 2. UI and Layout

- VS Code-style layout: active tab bar, EXPLORER file-tree sidebar, breadcrumb
  path bar, flat status bar, welcome screen
- Status bar + command line / message bar; extensions can inject custom status
  segments and a modal character canvas (`api.ui`)
- which-key panel: live next-key candidates while a chord is pending, `F9` pins
  the full keymap table (`which_key` toggles it off)
- Nerd Font file-type icons (`--install-font` / `:font` installs the bundled font
  and configures Windows Terminal when possible)
- Slim scrollbar injection; theme colors owned by each component

## 3. Two Built-in Keymaps

- **vsc** (default, modeless): VS Code-style editing/selection/clipboard
  shortcuts; `:` is a plain character, `F5` opens the command line
- **vim** (modal): NORMAL/INSERT/VISUAL/VISUAL-LINE; motions
  (`hjkl w b e 0 $ gg G f t`), operators `d/y/c`, text objects (`iw aw i( i" it`
  …), `r` replace, `x`, `p/P`, `u/Ctrl+R`, `J`, indent operators `>/<`
- `Ctrl+/` toggles between them at runtime; in vim, the `Ctrl+W` pane chord
  (14 keys) with live chord hints; vim reserved keys cannot be overridden by
  extensions
- `:check-keys` reports keymap binding conflicts

## 4. Find and Replace

- In-file find `Ctrl+F` (live highlight, `[index/total]` counter), `F3`/`Enter`
  for the next match
- Two-step replace-all `F4` (recorded as a single undo entry)
- Project-wide find & replace `Ctrl+H` / `:project-replace`

## 5. Files and Workspace

- File-tree browsing (`Ctrl+B` toggles): `j/k/l/h` navigation, new file/folder,
  rename, delete (`y` to confirm); open tabs stay in sync
- Fuzzy quick open `Ctrl+P` (fzf-style subsequence matching with a live file
  preview pane, configurable via `file_preview`)
- Command palette `Alt+Shift+P` (every `:` command and named action)
- Workspace trust: `:trust` is required before `./extensions` and the project
  yaterc auto-load
- `show_hidden` reveals hidden files

## 6. Panes and Tabs

- Pane splits: `:split`/`:vsplit` (optional path), `:only`, `:close`; each pane
  has independent cursor, selection and scroll
- vim `Ctrl+W` chord: split/close/maximize/move/resize/equalize/cycle focus
- Tabs: `Ctrl+PageUp/Down`, `:bn`/`:bp`/`:bd`

## 7. Command Line (ex Commands)

- Full set: `:w` `:q` `:q!` `:wq` `:saveas` `:e` `:enew` `:welcome` `:files`
  `:palette` `:set` `:filetype` `:theme` `:vim/:vsc` `:help` `:manual`
  `:changelog` `:explorer` `:term/:termclose` `:diagnostics` `:font` `:diff`
  `:trust` `:project-replace` `:check-keys` `:game`, plus extension-registered
  commands
- `:!cmd` (`F2`) runs a shell command on a background thread; output shows in a
  scrollable overlay annotated with the exit code
- `:set` runtime options: `keymap`/`theme`/`shell`/`terminal_height`/`filetype`/
  `show_hidden`/`readonly`/`support_mouse`/`which_key`

## 8. Configuration (yaterc)

- Python-syntax config file (vimrc style), loaded user-level → project-level
  upward; `-u FILE` selects one, `-u NONE` skips all
- Full option set: `keymap` `theme` `tab_width` `use_spaces` `shell`
  `terminal_height` (3–40) `show_hidden` `support_mouse` `which_key`
  `key_protocol` `extensions` `disabled_extensions` `theme_dirs`
  `yate_trace`/`yate_trace_level` (runtime logging) + dicts `screen_saver`
  (enable/interval/switch/distance bounds/character whitelist), `file_preview`
  (enable/position/size/max_lines/max_size), `language_servers`
  (name/command/filetypes/args/language_ids/initialization_options/settings/env/
  root_markers)
- `register_theme()` registers a custom theme inline; `--setup-defaults` /
  `--cleanup-defaults` (with `--force`/`--include-data`) manage `~/.yate`

## 9. Themes

- 8 built-in themes: Catppuccin `mocha` (default)/`macchiato`/`frappe`/`latte`,
  One Dark/Light, Gruvbox dark/light
- Dracula and Ayu (dark/mirage/light) ship as copy-to-activate templates
- 5 customization paths: inline in yaterc / `theme_dirs` / default directory /
  `--theme-dir` / copy a bundled template

## 10. Syntax Highlighting

- Two backends over one shared language registry: the regex backend covers 30
  languages out of the box (C#/Rust/Go/HTML/CSS/YAML/SQL/Lua/Perl/PHP/Ruby/
  PowerShell/Zig …) with 60+ extension keys
- Optional tree-sitter backend (`pip install -e ".[ts]"`): 25 languages upgrade
  to real parse-tree highlighting
- `:filetype` inspects/overrides/`auto` re-detects; extensions can register
  custom lexical languages (`api.highlight`) and tree-sitter grammars (`api.syntax`)

## 11. LSP Language Servers

- Built-in zero-dependency LSP client (stdio JSON-RPC; lazily started per
  server × project root; full-text sync with 0.25s debounce)
- Completion popup (trigger characters + `Ctrl+Space`; falls back to open-buffer
  words/paths without a server)
- Diagnostics: underlines / gutter marks ✖▲ / status-bar counts / `:diagnostics`
- Two registration paths: declarative `language_servers` in yaterc; programmatic
  `api.lsp.register_server` in extensions
- The bundled Python LSP extension auto-discovers pyright / python-lsp-server
  (`YATE_PYTHON_LSP` overrides or disables with `off`)

## 12. Terminal and Shell

- Integrated terminal: `` Ctrl+` `` / `:term` / `:termclose` runs a real shell
  over a PTY (Windows ConPTY / POSIX pty); height via `terminal_height`
- The `shell` option accepts any shell command line

## 13. Diff View

- CLI `--diff F1 F2` (two-way), `--diff F1 F2 F3` (three-way base/local/remote),
  `--2way`/`--3way` to force a mode
- In-session `:diff [--3way] F1 F2 [F3]`

## 14. Extension System

- **Python extensions**: any script exposing `setup(api)`; loading paths: bundled
  `yate/extensions/`, auto-load from `./extensions/` and `~/.yate/extensions/`,
  yaterc `extensions`, `--ext`/`--ext-dir`
- **Lua extensions** (`pip install -e ".[lua]"`): `setup`/`teardown` +
  `require("yate")`
- **`.yxp` extension packages**: install/uninstall/list (both CLI and `:` commands)
- API surface: `command`/`register_command`, `bind_key`/`bind_action`/
  `unbind_key` (vsc/vim/both), `register_action`, `message`/`shell`/`open_path`/
  `save`, `buffer`/`doc`/`workspace`/`keymaps`/`lsp`/`highlight`/`syntax`/
  `sprites`/`ui`/`events`/`theme`/`clipboard`/`docs`/`actions`/`data`
  (persistence under `~/.yate/data`)
- A failing `setup` rolls back all registrations via snapshot-restore
- Bundled: `python_lsp.py` (built-in LSP) + `games.lua` (game pack) + several
  `.py.example` templates

## 15. Fun Subsystems

- **Screensaver**: auto-enters on idle / `Alt+Shift+S` toggles manually; 27
  original homage-style pixel characters; extensions can register characters
  (`api.sprites`)
- **Lua game pack**: `:game snake|pacman|nethack|tetris` with uniform
  pause/restart/exit; NetHack autosaves every turn (saves under
  `~/.yate/data/games/`)

## 16. Help and Documentation

- `F1` keymap help; `F8`/`:manual` opens the bilingual user manual in-session
- `:changelog [en|zh]` browses the release history; bilingual README and
  [yate/docs/](yate/docs/) (yaterc / extensions / LSP / themes / which-key /
  games, each × en/zh)
- `YATE_TRACE` runtime logging and crash reports (under `~/.yate/data/`)

## 17. Full CLI Options

`path`, `--readonly`, `--keymap vsc|vim|normal`, `-u/--yaterc`, `--ext`,
`--ext-dir`, `--theme-dir`, `--theme`, `--install-font`, `--install-extension`,
`--uninstall-extension`, `--list-extensions`, `--setup-defaults`,
`--cleanup-defaults`, `--force`, `--include-data`, `--version`, `--changelog`,
`--diag` (environment diagnostics report), `--diff`, `--2way`, `--3way`

## 18. Distribution and Packaging

- Wheel install + PyInstaller standalone executables (Windows `pack.ps1`/
  `pack.bat`, Linux `pack.sh`; one-dir and one-file layouts, bundling the
  tree-sitter backend and the Lua bridge)
- Maintenance toolchain: `tools.smoke_test` (end-to-end smoke tests with
  baseline comparison), `tools.changelog`/`tools.release` (automated changelog
  and releases), `tools.pack wiki` (bilingual wiki generation) + 36
  architecture-guard tests

## Appendix: Features Not Highlighted in the README

`.yxp` extension package management, Lua extensions and the four games, the
which-key panel, multi-cursor `Alt+C`, project-wide find & replace `Ctrl+H`,
`:check-keys`/`:trust`/`:font`, vim named registers, advanced extension APIs
(`syntax`/`sprites`/`ui` canvas/`events`/`data`/`clipboard`), and the yaterc
options `key_protocol`/`show_hidden`/`support_mouse`/`which_key`/`yate_trace`.
