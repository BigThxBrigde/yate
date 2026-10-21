# G 波：俄罗斯方块重构（`tetris.lua`）+ 最高分

上级：[overview.md](overview.md) ｜ 依赖：B 波引擎 + C/D/E/F 已注册（派发文案要求五款齐全）｜ 独占文件：
`yate/extensions/tetris.lua`、`tests/test_lua_tetris.py`

## 一、目标

把既有 `tetris.lua`（`yate/extensions/tetris.lua:1-587`）重构到 `game_engine` 上：
命令注册交给 `games.lua`，最高分（含创造者）持久化，暴露 `snapshot()`；
**玩法、布局、手感零变化**（既有断言除 3 条命令文案外必须原样通过）。

## 一·补、视觉升级（2026-10-20 追加）

按 [overview §3.5](overview.md) 的统一版式：三个箱的边框由 `┌─`/`└─` 升级为 `╭─`/`╰─`
（`engine.box_top` / `box_bottom`），统计箱标签行尾可加图标（`★` 标 best）；
**双宽实心方块（`IOTSZJL` + `"*"="█"`）保持不变**。测试里的边框断言
（`┌─ stats` / `┌─ next` / `┌─ help`）同步改为 `╭─`，属规格变更而非回归。

## 二、保持不动的部分（不得回归）

| 项 | 现值 | 证据 |
|---|---|---|
| 画布尺寸 | `(59, 22)` | `tests/test_lua_tetris.py:271` |
| 布局 | 左 stats 箱 / 中棋盘箱 / 右 next+help 箱，空格分隔 | `tetris.lua:331-386` |
| 字符语义 | 棋盘格用棋子字母 `IOTSZJL`，调色板含 `"*" = "█"` | `tetris.lua:61-70` |
| 计分 | NES 表 100/300/500/800 × level；`level = 1 + lines//10` | `tetris.lua:24-28` |
| 重力 | `max(2, 15 - level)` tick；committed 每 tick 一行 | `tetris.lua:299-306` |
| 键位 | `left/right/down`、`up/x`、`space`、`enter`、`p`、`r` | `tetris.lua:481-529` |
| 单实例 | 再次启动 → `tetris is already running` | `tests/test_lua_tetris.py:287-295` |
| 测试缝 | `set_piece_source(fn)` | `tetris.lua:565-568` |

## 三、改动清单

1. **命令注册**：删除 `launch(args)` 与 `yate.register_command("game", launch, "launch a game (tetris)")`；
   `mod.setup` 改为 `engine.register("tetris", start_game)`（action 名 `game-tetris`）。
2. **canvas 打开**：`start_game` 改用 `engine.open{name="tetris", cols=59, rows=22, draw=..., on_key=..., on_tick=..., on_close=...}`；
   引擎负责单实例守卫与 `session.status("…")` 后缀，`handle` 局部变量由 `session` 取代。
3. **绘制助手**：`box_top` / `box_bottom` / `center` 改用 `engine.*`；棋盘行与叠加文本逻辑保持原样
   （纯 ASCII 双宽格、字节切片安全）。
4. **持久化**：

```json
{"version":1,"player":"alice",
 "high_scores":[{"score":1500,"player":"alice","at":"2026-10-20T21:50:00"}],
 "stats":{"games":2,"lines":24}}
```

   - game over 时 `scores("tetris").add(score)`；`stats.games+1`、`stats.lines+lines` 写回；
   - `setup` 时读 `best`，stats 箱多一行 `best`（**新增一行**，见下）；
   - `on_close` / `teardown` 再保存一次。
5. **stats 箱新增一行**：`│ best          1500│`（`STAT_INNER = 15`，`" best%10d"`）；
   箱高从 4 行变 5 行，右侧 `next` 箱从 row 1 起、`help` 箱位置不变（help 从 row 8 起 → 改为 row 9 起，
   对应 `test_tetris_opens_the_three_box_layout` 中 `┌─ next` / `┌─ help` 断言仍成立）。
6. **`snapshot()`**：`{score, lines, level, over, paused, best}`。
7. **模块头注释**：更新为「引擎化 + `:game tetris` 由 games.lua 派发 + 最高分」；
   controls 段落保留，补 `best` 说明。

## 四、测试更新（`tests/test_lua_tetris.py`）

| 现有用例 | 处置 |
|---|---|
| `test_game_command_registered_with_description` | **删除**（命令归属移到 `tests/test_lua_engine.py`） |
| `test_empty_argument_reports_usage` | **删除**（同上） |
| `test_unknown_game_reports_available_games` | **删除**（同上） |
| `test_second_launch_reports_already_running` | 保留（断言 `tetris is already running`） |
| 其余 12 条（布局、移动、旋转、踢墙、硬降、commit、重力、暂停、消行、升级、game over、重开、close、teardown） | 保留，**逐条必须仍绿** |
| `test_game_tetris_opens_and_closes_in_the_real_app` | 保留（真实 app + 真实 loader） |

新增用例：

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_stats_box_shows_the_saved_best` | 预置 `tetris.json` 最高分 1500 → stats 箱含 `best       1500` |
| 2 | `test_game_over_saves_the_high_score_with_player` | 堆到顶后 `tetris.json.high_scores[0].score > 0`、`player` 存在 |
| 3 | `test_snapshot_reports_the_score_and_level` | 消两行后 `snapshot().lines == 2`、`level == 1` |
| 4 | `test_teardown_saves_stats` | `teardown` 后 `stats.games >= 1` |

- 测试 harness 从 `tests/lua_game_harness.py` 复用（`_FakeApi` / `_FakeCanvas` 与 tetris 原文件同形），
  就地删除本文件内的重复 fake 定义，保留 tetris 专用助手（`_board_cells` / `_stats` / `_right_boxes` / `_move_to`）。

## 五、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_tetris.py tests/test_lua_engine.py -q
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/tetris.lua
```

## 六、风险

| 风险 | 缓解 |
|---|---|
| 加 `best` 行导致右侧箱位置断言失败 | 先跑一次现状测试记录 `_right_boxes` 断言行号，再改布局；`next` 箱保持 row 1 |
| 引擎化后 `handle` 生命周期与既有 close 语义不一致 | `session:close()` / `on_close` 覆盖 tetris 原 `test_close_callback_invalidates_the_canvas` / `test_teardown_closes_the_open_canvas` |
| 删掉的 3 条命令测试遗漏覆盖 | 由 `tests/test_lua_engine.py` 的 dispatch 用例承接（usage / unknown / registered） |
