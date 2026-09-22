---
name: "textual-pilot-smoke"
description: "Ad-hoc Textual TUI verification harness for yate: drive the app under pilot.run_test (key sequences, state assertions, SVG screenshot text checks), then delete the temp script. Invoke when verifying screens/modals/keybindings visually or end-to-end, or when a bug needs runtime evidence in the Textual event loop."
---

# Textual pilot smoke / screenshot verification (yate)

Use this when static checks are not enough: new screens/modals (palette, help,
welcome), keybinding wiring, theme rendering, or end-to-end user journeys.
Permanent coverage goes in `tests/`; this skill is for **throwaway** harnesses
that produce immediate evidence.

## Harness pattern

Create a temp script at the **repo root** (e.g. `_shot.py`, `_smoke.py` — never
inside `tests/` or `yate/`), run it, then **delete it and its `.svg` output**.

```python
from __future__ import annotations
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from yate.app import YateApp
from yate.editor_view import theme

async def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "notes.txt").write_text("hello\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(110, 32)) as pilot:
            await pilot.pause()                       # after mount
            await pilot.press("ctrl+p")               # named/composed keys
            await pilot.pause()
            for ch in "note":                         # typing: one key per char
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # 业务状态在调度层 app.editor（Editor）上，YateApp 只是外壳
            assert app.editor.session.doc.name == "notes.txt"
            app.save_screenshot("_shot.svg")          # optional visual check
            app.exit()

asyncio.run(main())
```

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv\Scripts\python.exe _shot.py
```

## Critical gotchas (all hit in this repo)

- **`pilot.press("world")` does NOT type "world"** — the whole string is treated
  as a single key name and silently dropped. Type text with
  `await pilot.press(*list("world"))` or a per-char loop. Named keys are fine:
  `"enter"`, `"escape"`, `"end"`, `"down"`, `"up"`, `"colon"`, `"ctrl+s"`,
  `"ctrl+p"`, `"ctrl+shift+p"`.
- **`await pilot.pause()` is required after mount and after every key sequence**
  before asserting, or messages have not been processed.
- **Composed keys** (`ctrl+shift+p`) have no ANSI sequence; they are reported by
  Textual as event key names — assert via `pilot.press("ctrl+shift+p")`.
- **Modals**: after opening, `app.screen` is the modal; `escape`/ctrl+c
  dismisses; assert `len(app.screen_stack) == 1` on return. For widget types
  on `app.screen`, use `assert isinstance(app.screen, PaletteScreen)` (plain
  `assert`, not `assertIsInstance`) if the script were ever type-checked.
- **Theme is process-global**: if the smoke switches theme (`:theme latte`),
  restore with `theme.set_theme("mocha")` before exiting.
- **Windows**: the real TUI cannot run with piped stdin — pilot is the only
  reliable smoke path. Use the venv python, not system python.

## State worth asserting

外壳 `YateApp` 只负责生命周期与主题桥；**业务状态一律走 `app.editor`（`Editor`）**：

- 会话：`app.editor.session.doc.name`、`app.editor.session.buffer.lines` / `.cursor`、
  `app.editor.session.docs` / `.index` / `.search`
- 配置与键：`app.editor.keymaps.name`、`app.editor.config`
- 注册表与扩展：`app.editor.commands.names()`、`app.editor.extension_loader.loaded`
  （每条记录含 `.name` / `.error`）
- 界面状态：`app.editor.explorer_visible`、`app.editor.panes.leaf_count()`、
  `app.editor.prompt_bar.active_mode`（空闲为 `None`）/ `.owner`
- Textual 原生（不要改写成 `app.editor.*`）：`app.screen`、`app.screen_stack`、
  `theme.active().name`、`app.is_running`、`app.return_code`

## Verifying rendered pixels without eyes

`save_screenshot()` writes SVG. Extract text rows to assert what the user sees
(Nerd Font glyphs appear as private-use chars like `\uf0f6`):

```python
import re
svg = Path("_shot.svg").read_text(encoding="utf-8")
rows: dict[int, str] = {}
for m in re.finditer(r'<text[^>]*y="([\d.]+)"[^>]*>(.*?)</text>', svg, re.S):
    y = int(float(m.group(1)))
    text = "".join(re.findall(r">([^<]+)<", ">" + m.group(2) + "<"))
    rows[y] = rows.get(y, "") + text
for y in sorted(rows)[:12]:
    print(y, repr(rows[y][:118]))
```

## Permanent runner: `tools.smoke_test`

For repeated smoke checks (CI gate, regression evidence), prefer the bundled
runner over one-shot scripts. It drives the same `pilot.run_test` pattern,
captures `Check(label, expected, actual)` assertions plus extracted SVG rows,
and diffs against stored JSON baselines.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'

# run all scenarios, print PASS/FAIL table
 .venv\Scripts\python.exe -m tools.smoke_test run

# also capture and show the top SVG text rows
 .venv\Scripts\python.exe -m tools.smoke_test run --svg

# write JSON baselines (checks + SVG rows) to tools/smoke_baselines/
 .venv\Scripts\python.exe -m tools.smoke_test snapshot

# run and diff against baselines (exit 1 on drift — CI gate)
 .venv\Scripts\python.exe -m tools.smoke_test compare
```

Scenarios live in the `tools/smoke_test/scenarios/` package, grouped by area
(`core` / `edit` / `search` / `files` / `panes` / `explorer` / `view` /
`integration` / `regression` / `stress` / `aliases`); every submodule exposes
`SCENARIOS`, and `tools/smoke_test/scenarios/__init__.py` concatenates them.
Pick a subset with `--scenario NAME` or `--tag TAG` (both repeatable); skip the
slow group with `--skip-slow`; `--seed N` pins the fuzz scenarios;
`--fail-only` / `--json PATH` / `--report PATH` help when triaging.

Add a new scenario by appending an `async def(tmp: Path) -> ScenarioResult` to
the right submodule's `SCENARIOS` — follow the harness pattern above (type
per-char, `await pilot.pause()` after every step, assert via `Check`), and use
the helpers re-exported from `.scenarios`: `new_app`, `type_text`,
`run_command`, `goto`, `wait_until`, `snapshot_svg`.
Baselines live under `tools/smoke_test/smoke_baselines/*.json` and should be
re-snapshotted after intentional UI changes.

## Cleanup and final gate

1. Delete the temp `.py` and all `.svg` files.
2. Run the permanent gates (pyright needs the node PATH prefix):

```powershell
# pyright-python caches its bundled node runtime under the user cache dir;
# prepend that nodeenv's Scripts so the bundled node is on PATH:
#   $env:PATH = "$env:LOCALAPPDATA\pyright-python\nodeenv\Scripts;$env:PATH"
$env:PYTHONDONTWRITEBYTECODE='1'
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests -q
```

If a smoke check proves durable behavior, add it as a real
`unittest.IsolatedAsyncioTestCase` in `tests/test_app_textual.py` using the
same `run_test` pattern.
