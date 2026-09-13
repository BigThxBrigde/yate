# yate Themes

**English** · [中文](themes.zh.md)

A yate color theme has two parts: **UI colors** (backgrounds, status bar,
selection, borders, etc.) and the **syntax highlighting palette**. Both are
encapsulated in the `Theme` dataclass.

The four built-in themes are all [Catppuccin](https://catppuccin.com/)
flavors: `mocha` (default dark), `macchiato`, `frappe`, `latte` (light).

This file is the complete theme-customization reference; sections 10.3 / 11 of
the manual are a short introduction.

---

## 1. Selecting a theme

| Method | Action |
|---|---|
| Command | `:theme latte`, `:colorscheme latte` (no argument lists every registered theme) |
| Option | `:set theme=latte` |
| Config | `theme = "latte"` in yaterc |
| Startup flag | `yate --theme latte` (overrides yaterc's `theme`) |

Switching affects only the current session; write it into yaterc to make it
permanent. An unknown theme name errors out and lists the available themes.

---

## 2. Four ways to customize themes

### Option A: inline registration in yaterc

`Theme` and `register_theme()` are injected into the yaterc execution
namespace, so a handful of tweaks can live directly there:

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",
    label="My Mocha",
    accent="#89b4fa",
    accent2="#cba6f7",
))
theme = "my-mocha"
```

### Option B: theme directories/files via `theme_dirs`

Declare one or more paths in yaterc; every `*.py` inside loads at startup:

```python
theme_dirs = "~/.yate/themes"           # one directory
theme_dirs = [
    "~/.yate/themes",                   # ~ is expanded
    "./team-themes",                    # relative: resolves against this yaterc's directory
    "./extras/solarized.py",            # a single theme file also works
]
```

A theme file is ordinary Python with `Theme` and `register_theme()` already in
scope; regular `import` statements work as well.

### Option C: default directories (no configuration)

Without any configuration, yate automatically scans:

- `./themes/` in the working directory
- `~/.yate/themes/`

Just drop `*.py` theme files in (files starting with an underscore are
skipped).

### Option D: `--theme-dir` on the command line

For one-off use, repeatable:

```bash
yate --theme-dir ~/my-themes --theme-dir ./extras/solarized.py
```

`--theme-dir` accepts both directories and single `*.py` files.

---

## 3. Same-name override and load precedence

When the same theme name is registered multiple times, **the later load
overrides the earlier one**. Precedence from low to high:

1. Built-in themes (`mocha` / `macchiato` / `frappe` / `latte`)
2. Default directories `./themes`, `~/.yate/themes`
3. `theme_dirs` in yaterc (user rc first, project rc after)
4. `--theme-dir` on the command line

So a project-level yaterc's `theme_dirs` can override user-level themes, and
`--theme-dir` can temporarily override everything for a single launch.

A broken theme file never aborts startup: the error shows in the startup
message bar as `<path>: <problem>` while the remaining files load normally.

---

## 4. Writing a theme file

The simplest approach is to copy a built-in theme and override a few colors:

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

You can also build a `Theme` from scratch (every field is required except
`extra`):

```python
register_theme(Theme(
    name="solarized-dark",
    label="Solarized Dark",
    dark=True,
    bg="#002b36", panel="#073642", surface="#073642",
    gutter_bg="#002b36", border="#586e75",
    selection_bg="#073642", match_bg="#b58900", match_active_bg="#cb4b16",
    on_accent="#002b36",
    fg="#839496", fg_dim="#586e75", fg_muted="#657b83", fg_bright="#93a1a1",
    accent="#268bd2", accent2="#6c71c4",
    green="#859900", yellow="#b58900", red="#dc322f", orange="#cb4b16",
    mode_normal_bg="#268bd2", mode_insert_bg="#859900",
    mode_visual_bg="#6c71c4", mode_command_bg="#cb4b16",
    syn_keyword="#859900", syn_string="#2aa198", syn_number="#d33682",
    syn_comment="#586e75", syn_function="#268bd2", syn_type="#b58900",
    syn_constant="#cb4b16", syn_builtin="#dc322f", syn_decorator="#d33682",
    syn_operator="#93a1a1", syn_property="#6c71c4",
))
```

---

## 5. `Theme` field reference

All color values are `#RRGGBB` hex strings.

### Backgrounds

| Field | Purpose |
|---|---|
| `bg` | editor background |
| `panel` | tab bar / sidebar / status bar background |
| `surface` | current-line highlight / input background |
| `gutter_bg` | line-number gutter background |
| `border` | subtle separator lines |

### Overlays

| Field | Purpose |
|---|---|
| `selection_bg` | selection background |
| `match_bg` | search-match background |
| `match_active_bg` | current search-match background |
| `on_accent` | text color drawn on top of accent blocks (e.g. match highlight) |

### Foregrounds

| Field | Purpose |
|---|---|
| `fg` | body text |
| `fg_dim` | de-emphasized text such as comments |
| `fg_muted` | secondary text |
| `fg_bright` | emphasized text |

### Accents

| Field | Purpose |
|---|---|
| `accent` | primary (blue): status bar bg, active tab, selection |
| `accent2` | secondary (purple) |
| `green` / `yellow` / `red` / `orange` | status colors (success/warning/error, etc.) |

### Status bar mode chips

| Field | Purpose |
|---|---|
| `mode_normal_bg` | normal mode |
| `mode_insert_bg` | insert mode |
| `mode_visual_bg` | visual mode |
| `mode_command_bg` | command mode |

### Syntax palette

Maps to the token kinds produced by the `editor_syntax` layer (see
`yate/editor_syntax/tokens.py` for the full kind table):

| Field | Token kind |
|---|---|
| `syn_keyword` | keywords, headings |
| `syn_string` | strings |
| `syn_number` | numbers |
| `syn_comment` | comments (rendered italic) |
| `syn_function` | function names, links |
| `syn_type` | types |
| `syn_constant` | constants |
| `syn_builtin` | built-ins |
| `syn_decorator` | decorators |
| `syn_operator` | operators |
| `syn_property` | properties |

### Metadata

| Field | Description |
|---|---|
| `name` | unique name used by `:theme <name>` |
| `label` | display name |
| `dark` | whether it is a dark theme |
| `extra` | free-form metadata dict, reserved for user themes |

---

## 6. Listing registered themes

- At runtime: `:theme` without arguments lists every registered theme name in
  the message bar.
- Command palette: search for `theme` to find the `:theme` command and complete
  theme names with `Tab`.
