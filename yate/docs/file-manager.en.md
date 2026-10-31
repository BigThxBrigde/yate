# yate file manager

**English** · [中文](file-manager.zh.md)

yate ships an lf-style terminal file manager: three panes (parent
directory | current directory | preview) over a status bar, in two
forms. As an overlay it floats over the editor and closes without
touching your editing state; started from the command line it takes the
whole screen and hands the selection to the editor when you choose an
entry. Unsaved buffers are never dropped silently.

---

## 1. Overview

The screen has three panes and a status bar:

* **Parent directory** (left) -- the listing of the current directory's
  parent. At the file-system root on Windows this becomes the
  drive-letter virtual level (`C:` `D:` …); on POSIX it shows an empty
  placeholder.
* **Current directory** (middle) -- the browsable list: file icons,
  accent-colored directory names, child-count badges (`(12)`, `999+`
  once capped), right-aligned file sizes; marked rows carry a `* `
  prefix.
* **Preview** (right) -- follows the cursor: a syntax-highlighted text
  preview for files, the first 100 child entries for directories (see
  section 5).
* **Status bar** (bottom) -- lf-style layout: `mode nlink owner group
  size mtime · n/total · sort hint`, plus `filter: <query>` while a
  filter is active and `marked: N` while marks exist. Owner / group
  fall back to `-` when the platform does not report them (Windows).

Two forms, one component:

* **Overlay** -- a modal floating layer (90% width / 80% height) pushed
  over the editor. `Esc` / `q` dismisses it; the editor underneath is
  restored exactly as it was.
* **Fullscreen** -- `yate --file-manager` starts yate directly in the
  file browser (same component with a `.fullscreen` class). Selecting
  an entry switches into the editor UI; `q` exits the process.

The file manager shares one `Workspace` with the file tree
(`:explorer` / `Ctrl+B`): hidden-file, `.gitignore` and `.yateignore`
filtering and the `show_hidden` toggle are the same state, and icons,
theme colors and slim scrollbars follow the active theme in both.

---

## 2. Opening

| Entry point | Effect |
|---|---|
| `Alt+Shift+F` | Open the overlay (bound in both the vsc and the vim keymap) |
| `:file-manager` | Same overlay from the command line / command palette |
| `yate --file-manager [PATH]` | Start fullscreen at `PATH` (default: the current directory); mutually exclusive with a positional `PATH` on the same command line |

---

## 3. Keys

**Navigation**

| Key | Action |
|---|---|
| `j` / `Down`, `k` / `Up` | Move the cursor down / up |
| `h` / `Left` / `Backspace` | Go to the parent directory (the cursor lands on the entry of the directory you came from) |
| `l` / `Enter` / `Right` | Enter a directory / open the selection (see section 4) |
| `g` `g` / `Home` | Jump to the top (the second `g` must follow within a second) |
| `G` / `End` | Jump to the bottom |
| `Ctrl+D` / `Ctrl+U` | Half page down / up |

**Filter and view**

| Key | Action |
|---|---|
| `/` or `f` | Incremental name filter (the bottom input narrows the list live; `Esc` clears it) |
| `H` or `.` | Toggle hidden files (the same toggle the file tree uses) |
| `s` | Cycle the sort key: name → size → mtime (directories always sort first; the status bar shows the current key and `asc`/`desc`) |
| `r` / `F5` | Force a refresh (invalidate the cache and re-list) |

**Multi-select**

| Key | Action |
|---|---|
| `Space` | Toggle the mark on the cursor entry (the cursor does not move) |
| `v` | Invert all marks |
| `l` / `Enter` | Open the marked set (see section 4) |
| `Esc` | Two-level exit: with an input or filter active it closes that first, then clears the marks, and finally closes |

**File operations**

| Key | Action |
|---|---|
| `a` | New file (name on the bottom input) |
| `A` | New directory |
| `R` | Rename the cursor entry (current name prefilled) |
| `d` | Delete the cursor entry (confirm with `y`; directories are confirmed as "directory (recursive)") |
| `y` / `x` | Copy (yank) / cut the cursor entry into the paste buffer |
| `p` | Paste into the current directory (a cut is consumed by the move, a copy survives; a name conflict asks on the input line and is never silently overwritten) |

**Exit**

| Key | Action |
|---|---|
| `q` / `Esc` | Overlay: close and restore the editor · Fullscreen: `q` exits the process |

Mouse: a single click moves the cursor, a second click on the same row
within 300 ms opens it, and the wheel scrolls the panes.

---

## 4. Selection and switching

Opening the selection (`l` / `Enter` / double click) hands the marked
set to the workspace switch:

* **No marks** -- the cursor entry acts alone.
* **Pure file set** -- the workspace root becomes the first file's
  parent directory and every file opens as a tab, the first one in
  front.
* **A set containing directories** (pure or mixed) -- only the first
  directory in alphabetical order is entered (a workspace has a single
  root); the report line notes
  `multiple entries selected - entering the first directory only`.
* **Unsaved buffers** -- the switch is refused outright with the
  warning `N unsaved changes - save or discard first` on the message
  line. Nothing is discarded silently: save or close the modified
  buffers first, then select again.

---

## 5. Preview

* **Text files** are syntax-highlighted with the same pipeline as the
  Ctrl+P palette. The `file_preview` limits apply (`max_lines`,
  `max_size`; the other keys of that section shape the palette pane
  only), and content past the line cap is truncated.
* **Directories** show their first 100 child entries.
* **Degradations** appear as a dim note instead of content:
  `(binary file)` for binary data, `file too large (> N bytes)` over
  the size cap, `cannot read: ...` for unreadable entries.
* **Cache** -- the last 16 previews are kept (FIFO) and shared with the
  palette, so revisiting an entry is instant; `r` re-reads anyway.

---

## 6. Limitations

* **The forms differ in what closing means** -- in the overlay `q` /
  `Esc` pops back into your editor session; in the fullscreen form `q`
  exits the yate process entirely.
* **Unsaved buffers block switching** -- the warning is the whole
  interaction: no overwrite, no discard prompt. Save or close the
  buffers, then repeat the selection.
* **Windows attribute columns degrade** -- owner / group read `-` (the
  hard-link count and the permission-mode string still display).
* **Double click is a timing window** -- two clicks on the same row
  within 300 ms count as "open"; slower sequences just move the cursor.
* **Same-volume transfers only** -- copy / cut / paste refuse to move
  entries across drive boundaries.
* **Not implemented (P2)** -- hex preview, a `?` key cheat-sheet
  overlay, yaterc-configurable defaults (sort key, overlay size ratio)
  and click-to-sort on the status bar.
