# yate which-key

**English** · [中文](which-key.zh.md)

The which-key panel is yate's at-a-glance keymap reference. While a key
chord is still being typed it lists every valid next key with its
description; it can also be pinned as a full, category-grouped keymap
sheet. The panel sits at the bottom of the window, directly above the
status bar, never takes focus, and never swallows keystrokes.

---

## 1. Overview

Two ways to read the panel:

* **Auto popup on pending chords** -- after every keypress the active
  keymap is asked for the chord typed so far; while a chord is pending,
  the panel shows a header with that chord plus a grid of next-key
  candidates and their descriptions. As soon as the chord resolves (or
  is cancelled), the panel hides again.
* **Pinned sheet via F9** -- `<f9>` runs the `toggle_whichkey` action and
  pins the whole binding table as a full sheet grouped by category (the
  key is bound in both the vim and the vsc keymap). While pinned, the
  sheet stays up regardless of what you type; press `<f9>` again to unpin.

Visibility is recomputed after every dispatch, with four mutually
exclusive branches (first hit wins): the pinned sheet, the vim `ctrl+w`
window chord, pending-chord candidates, otherwise hidden.

---

## 2. Keymap differences

**vim** -- the auto popup follows real chord state in NORMAL mode:

* pending registers (`"`), counts, operators (`d`, `c`, ...) and prefixes
  all show their continuation candidates as you type (in typing order:
  register, count, operator, prefix);
* the `ctrl+w` window chord gets its own fourteen-key table: `h` `j` `k`
  `l` move, `s` :split, `v` :vsplit, `q` close, `o` :only, `ctrl+w`
  cycle, `+` `-` `<` `>` `=` resize -- the same words as the hint posted
  on the message line;
* INSERT and VISUAL modes never hold chord state, so no popup appears
  there.

**vsc** -- the vsc keymap has no chord state (no counts, operators or
registers), so the auto popup never fires; there are no pseudo prefixes
to trigger it. Its way to browse bindings is the pinned sheet via
`<f9>`, where the full table is grouped by category.

---

## 3. Conflict checking

`:check-keys` scans the active keymap and prints the report on the
output screen titled "key conflicts". Two conflict classes are reported:

* `duplicate` -- the same key is bound more than once in the table; the
  later entry shadows the earlier one, so the earlier binding never
  dispatches;
* `reserved` -- the key is consumed before the table is consulted (e.g.
  vim's hard-coded branches), so the bound action can never run. The
  reserved set applies to the vim keymap only; every other keymap is
  scanned for duplicates alone.

A clean scan prints `keymap: <name> -- no conflicts`; otherwise the
header `keymap: <name> -- N conflict(s)` is followed by one
`<key>  <reason>  action1 -> action2` line per conflict.

---

## 4. Limitations

* **F9 terminal availability** -- in some terminals `<f9>` never reaches
  the editor because the terminal itself captures the function key, so
  the pinned-sheet toggle cannot be triggered there. The conflict report
  stays reachable from the command line via `:check-keys`, but there is
  no command-line fallback for the panel toggle itself.
* **No yaterc persistence yet** -- there is no yaterc option to configure
  the which-key panel, and the pinned state is not persisted: after a
  restart the sheet starts unpinned. Both are out of scope for now.
