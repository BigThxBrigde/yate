# C 波：贪食蛇（`snake.lua`）

上级：[overview.md](overview.md) ｜ 依赖：[engine 契约](games-pack-engine-plan-b.md) §三 ｜ 独占文件：
`yate/extensions/snake.lua`、`tests/test_lua_game_snake.py`

## 一、目标

` :game snake ` 打开一个「绿色方块蛇 + 红色食物 + 顶部计分」的贪食蛇（参考图像：
绿色方块蛇、红色食物、`Score: 28`），支持转向、吃食增长加速、暂停、重开、
最高分（含创造者）跨会话保存。

## 二、画面（画布 62 x 22）

```
┌─ snake ──────────────────────────────────────────────────────┐   row 1
│ score 0   best 0 (player)   length 3                          │   row 2  HUD
│                                                              │   row 3..20  棋盘 18 行
│                                                              │
│ ... 30 格 x 18 行，每格 2 字符 ...                            │
│                                                              │
├─ help: arrows/hjkl/wasd turn  p pause  r restart ─────────────┤   row 21
└──────────────────────────────────────────────────────────────┘   row 22
```

- `cols = 62`、`rows = 22`；内宽 60；棋子区 `x = 1..30`、`y = 1..18`。
- 每格输出 **2 个相同字符**（单宽字形，禁止 emoji）：蛇身 `██`、蛇头 `▓▓`、食物 `●●`；空格两个空格。
- `palette = { ["█"]="#4caf50", ["▓"]="#c8e6c9", ["●"]="#e53935" }`（**不用** `"*"` 字形键；
  字形词表见 [overview §3.5](overview.md)：`█` = `block`、`▓` = `shade`、`●` = `big_dot`）。
- 边框用 `engine.box_top` / `box_bottom`（圆角 `╭─ snake ─...─╮`），标题行右侧 `★` 图标。
- 行拼装：`"│" .. line .. "│"`，`line` 必须恰好 60 字节（纯 ASCII，按字节补齐安全）。
- 死亡/暂停：把文本覆盖到棋盘中部行（`game over` / `press r` / `paused`），覆盖时保持 60 字节。
- 状态栏：`session:status("score " .. score .. "  best " .. best .. "  length " .. #snake)`（引擎自动加 `  escape quits`）。

## 三、规则

| 项 | 规定 |
|---|---|
| 初始 | 长度 3，头 `(3,9)`，身体 `(2,9) (1,9)`，方向右 |
| 逐步 | 每 `step_ticks` 个 tick 走一格；`step_ticks = max(3, 10 - floor(score / 50))` |
| 转向 | 方向键 / hjkl / wasd；**拒绝 180° 反向**与同向重复；其余在下一格生效 |
| 吃食 | 新头 == 食物：`score += 10`，不弹尾（增长），重新生成食物 |
| 食物生成 | `rng.int(30), rng.int(18)` 反复取直到不在蛇身；`mod.set_food_source(fn)` 可注入 |
| 死亡 | 撞墙（x<1 或 x>30 或 y<1 或 y>18）或撞自身（未增长时允许撞尾格） |
| 暂停 | `p` 切换；暂停时 tick 不走步、画面显示 `paused` |
| 重开 | `r` 任意时刻重置为新局（分数清零、速度回到 10 tick） |
| 死亡结算 | 一次 `scores("snake").add(score)`；`stats.games+1`、`stats.best_length = max(.., #snake)` 写回 |
| 关闭 | `on_close` 保存最高分与统计（失败静默） |

## 四、持久化（`games/snake.json`）

```json
{"version":1,"player":"alice",
 "high_scores":[{"score":28,"player":"alice","at":"2026-10-20T21:30:00"}],
 "stats":{"games":3,"best_length":12}}
```

读：启动时 `store.load()` 取 `high_scores[1].score` 作为 HUD 的 `best`，`high_scores[1].player` 显示在括号里。
坏 JSON / 缺字段 → `best = 0`、`player = engine.player()`，不报错。

## 五、模块表与测试缝

```lua
return {
  setup = function(api) ... end,     -- engine.register("snake", start)
  teardown = function(api) ... end,  -- 关闭遗留 canvas
  set_seed = function(n) ... end,    -- 固定 rng 种子
  set_food_source = function(fn) end,-- fn() -> {x=,y=}；nil 恢复随机
  snapshot = function() ... end,
}
```

`snapshot()` 字段（测试断言依据）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `score` | number | 当前分数 |
| `length` | number | `#snake` |
| `alive` | boolean | 存活 |
| `paused` | boolean | 暂停 |
| `head_x` / `head_y` | number | 1-based 棋盘坐标 |
| `dir_x` / `dir_y` | number | 当前方向 |
| `food_x` / `food_y` | number | 食物坐标 |
| `best` | number | 已加载的最高分 |
| `step_ticks` | number | 当前走一步所需 tick 数 |

## 六、测试 `tests/test_lua_game_snake.py`（用 `tests/lua_game_harness.py`）

| # | 用例 | given / when / then |
|---|---|---|
| 1 | `test_game_snake_opens_the_board_canvas` | `:game snake` → canvas 62x22、首帧含 `┌─ snake`、状态栏含 `score 0` |
| 2 | `test_initial_snake_and_food_are_inside_the_board` | snapshot：length 3、head (3,9)、food 在 1..30 / 1..18 内 |
| 3 | `test_reverse_direction_is_ignored` | 初始向右，按 `left` 后走一步 → head_x 4（未反向） |
| 4 | `test_up_key_moves_the_head_up_after_one_step` | 按 `up`，`tick(10)` → head `(3,8)` |
| 5 | `test_eating_food_scores_and_grows` | 食物注入到 `(4,9)`，走一步 → score 10、length 4、食物已换位 |
| 6 | `test_wall_collision_ends_the_game` | 连按 `up` 走到边界外 → `alive == false`，画面含 `game over` |
| 7 | `test_self_collision_ends_the_game` | 长到 ≥5 后绕回咬到身体 → `alive == false` |
| 8 | `test_pause_freezes_movement_and_overlays_text` | `p` 后 `tick(30)` → head 不变、画面含 `paused`；再 `p` 恢复 |
| 9 | `test_speed_increases_with_score` | score 50 后 `step_ticks == 9`（注入食物连吃 5 次） |
| 10 | `test_high_score_is_saved_with_the_player_name` | 死亡后 `snake.json` 的 `high_scores[0].score` 与玩家名正确 |
| 11 | `test_relaunch_shows_the_saved_best` | 重新 `setup` 后 HUD/状态栏含 `best <score>` |
| 12 | `test_restart_resets_score_and_length` | 死亡后 `r` → score 0、length 3、`alive == true` |
| 13 | `test_close_saves_and_deadens_the_session` | `close_cb()` → `snake.json` 存在；再 `tick` 不新增帧 |

## 七、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_game_snake.py -q
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/snake.lua
```

## 八、风险与约束

- 只改本节「独占文件」两个文件；`game_engine.lua` 缺功能时必须上报主代理，禁止自行改引擎。
- 食物生成必须有界（最多尝试 200 次，仍失败则取第一个空格），避免满屏时死循环。
- 所有注释英文；不得 `print` / `io`。
