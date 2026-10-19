# yate which-key

**English** · [中文](which-key.zh.md)

The which-key panel is yate's at-a-glance keymap reference. While a key
chord is still being typed it lists every valid next key with its
description; it can also be pinned as a full, category-grouped keymap
sheet. The panel floats on the right edge of the editor column as a
rounded box; the border title carries the current chord or keymap name,
both coloured by the active theme. It never takes focus and never swallows
keystrokes. Set `which_key = False` in your yaterc to hide it entirely.

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

**vim** -- the auto popup follows real chord state in NORMAL mode, and the
hard-coded dispatch branches list their continuations key by key:

* an armed operator (`d` `y` `c`) lists its whole pending vocabulary: the
  linewise repeat (`dd`), the `i`/`a` text-object scopes, the motions
  (`w` `b` `e` `h j k l` `0` `$` `G`), the completing prefixes (`g` `f` `F`
  `t` `T`) and, once a find has run, the `;` `,` repeats;
* after a scope key the header reads `di` / `da` and the grid lists the
  object targets (`w`, `'`, `"`, `t`, `( b`, `[ ]`, `{ B`, `< >`);
* an argument prefix shows its follower as a placeholder (`f`/`F`/`t`/`T`
  -> `{char}`, `r` -> `{char}`); the `g` prefix shows its `gg` completion;
  the register wait shows a single `a-z` row;
* a bare count (`2`) lists what may follow: operators, motions, prefixes
  and the `> <` indents. The header always reads back the full chord in
  typing order (count, operator, scope, prefix -- `2di`);
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
header `keymap: <name> -- N conflict(s) (D duplicate, R reserved)` is
followed by one `<key>  <reason>  action1 -> action2` line per conflict,
plus a closing note whenever the reserved class is non-empty.

On a stock vim keymap the scan reports eight reserved rows (`<esc>`,
`<ctrl-b>` / `<ctrl-d>` / `<ctrl-f>` / `<ctrl-u>`, `<ctrl-g>`,
`<ctrl-r>`, `<alt-c>`). Those rows are deliberate help mirrors: the
built-in vim branch runs the command, so the row itself never dispatches
-- exactly what the closing note says. The scan's real target is a
binding added later, by an extension for instance, on one of those keys:
such a binding would silently never fire.

---

## 4. Limitations

* **F9 terminal availability** -- in some terminals `<f9>` never reaches
  the editor because the terminal itself captures the function key, so
  the pinned-sheet toggle cannot be triggered there. The conflict report
  stays reachable from the command line via `:check-keys`, but there is
  no command-line fallback for the panel toggle itself.
* **Pinned state is not persisted** -- the pinned state lives in
  `WhichKeyFlows` only, so after a restart the sheet starts unpinned.
