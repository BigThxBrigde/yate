# E 波：推箱子（`sokoban.lua`）

上级：[overview.md](overview.md) ｜ 依赖：[engine 契约](games-pack-engine-plan-b.md) §三 ｜ 独占文件：
`yate/extensions/sokoban.lua`、`tests/test_lua_game_sokoban.py`

## 一、目标

` :game sokoban ` 打开一个「蓝墙 + 棕木箱 + 黄色玩家」的推箱子（参考图像：
蓝色方块墙、棕色箱子、黄色角色），内置多关，支持撤销、重开、过关推进；
**关数与完成列表持久化**，重开编辑器可继续。

## 二、画面（画布 23 x 18）

```
┌─ sokoban ───────────┐   row 1
│                     │   row 2..13  关卡区 12 行 x 21 列（不足补空格）
│     ██████          │
│     █ ▣  █          │
│     █ @  █          │
│     ██████          │
│                     │
│                     │
│                     │
│                     │
│                     │
│                     │
│                     │
│ level 1/6  moves 0  │   row 14  HUD
│ u undo  r restart  n next  p pause │   row 15 help
└─────────────────────┘   row 16? -> 定稿：rows = 16
```

**定稿尺寸**：`cols = 23`、`rows = 16`；内宽 21；关卡区固定 **21 x 12**（左上角对齐，
不足补空格，超出视为关卡数据错误）。行 14 = HUD，行 15 = help，行 16 = 底边框。

### 字形与颜色（1 字符/格）

| 语义 | 字符 | 调色板 |
|---|---|---|
| 墙 | `█` | `#4a90d9`（蓝） |
| 箱 | `▣` | `#8d5524`（棕） |
| 箱在目标 | `▩` | `#7bd88f`（绿） |
| 目标 | `◎` | `#bdbdbd`（灰） |
| 玩家 | `☻` | `#ffd54f`（黄） |
| 玩家在目标 | `☻` | `#7bd88f`（绿） |
| 地板 | ` ` | — |

> 字形词表见 [overview §3.5](overview.md)；走廊/地板底纹可用 `░` 表示目标格底（可选美化，
> 但必须保证 1 字符/格不破坏网格）。

> 关卡区含 `█ ▣ ▩ · @` 等多字节字符，**不要**用 `engine.frame`（按字节补齐会错位）；
> 用 `engine.box_top` / `engine.box_bottom` 拼上下边框，行内容按 `#row`（字符数）自己补空格。

## 三、关卡数据（内置 6 关）

`LEVELS` 为字符串数组的数组；字符集 `#` 墙、` ` 地、`$` 箱、`.` 目标、`@` 玩家、
`*` 箱在目标、`+` 玩家在目标。**每关必须满足**：恰 1 个玩家、箱数 == 目标数、外层可越界读取视为墙。

关卡 1-5 取自公开 Microban 关卡集（1-5，逐字照抄），第 6 关为单步可解的教学关：

```lua
local LEVELS = {
  { -- 1
    "####",
    "# .#",
    "#  ###",
    "#*@  #",
    "#  $ #",
    "#  ###",
    "####",
  },
  { -- 2
    "######",
    "#    #",
    "# #@ #",
    "# $* #",
    "# .* #",
    "#    #",
    "######",
  },
  { -- 3
    "  ####",
    "###  ####",
    "#     $ #",
    "# #  #$ #",
    "# . .#@ #",
    "#########",
  },
  { -- 4
    "########",
    "#      #",
    "# .**$@#",
    "#      #",
    "#####  #",
    "    ####",
  },
  { -- 5
    " #######",
    " #     #",
    " # .$. #",
    "## $@$ #",
    "#  .$. #",
    "#      #",
    "########",
  },
  { -- 6（教学关：向右推两格）
    "#######",
    "#     #",
    "#     #",
    "# @$. #",
    "#     #",
    "#######",
  },
}
```

> 相对主计划的偏离：主计划写「8 个内置关卡」，本子计划定稿 **6 关**（5 关公开关卡 + 1 关教学关），
> 理由：只收录可确认可解的关卡，宁少不烂；`LEVELS` 长度即关数，后续可增补。

## 四、规则

| 项 | 规定 |
|---|---|
| 移动 | 方向键 / hjkl / wasd；目标格是墙或箱（推不动）→ 无操作，**不计步** |
| 推箱 | 玩家前方是箱、箱前方是地/目标 → 玩家进箱格、箱前移一格；计 `moves+1`、`pushes+1` |
| 撤销 | `u` 回退一步（玩家位置 + 被推箱子位置）；栈上限 200，超出丢最旧 |
| 重开 | `r` 重置当前关（步数清零、撤销栈清空、读取关卡初始布局） |
| 过关判定 | 所有目标格上都有箱 → `solved = true`，HUD 提示 `solved!  n next` |
| 下一关 | `n` 仅当 `solved`；最后一关再按 `n` → 画面提示 `all levels cleared`，`r` 从第 1 关重开 |
| 暂停 | `p` 冻结输入（只允许 `p` / `r` / `escape`），画面提示 `paused` |

## 五、持久化（`games/sokoban.json`）

```json
{"version":1,"level":3,"completed":[1,2],"moves":120,"pushes":30}
```

- 写入时机：过关推进、`on_close`、`teardown`；
- 读取时机：`setup` / 启动时；`level` 夹在 `1..#LEVELS`；`completed` 去重升序；
- 读到坏 JSON → `level = 1`、`completed = {}`、累计步数归零，并 `yate.message` 一次提示；
- HUD 显示 `completed` 的数量（`done 2`）。

## 六、模块表与测试缝

```lua
setup / teardown / snapshot
load_level(n)        -- 跳过第 n 关（越界夹紧），保留 completed
snapshot()
```

`snapshot()` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `level` | number | 当前关（1-based） |
| `total` | number | 关卡总数 |
| `moves` / `pushes` | number | 本关步数 / 推动数 |
| `solved` | boolean | 本关是否完成 |
| `paused` | boolean | 暂停 |
| `player_x` / `player_y` | number | 关卡区内 1-based 坐标 |
| `boxes` | array | `{x, y, on_goal}` 数组 |
| `goals` | number | 目标总数 |
| `completed` | array | 已通过关卡号 |
| `undo_depth` | number | 撤销栈深度 |

## 七、测试 `tests/test_lua_game_sokoban.py`

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_game_sokoban_opens_the_level_canvas` | canvas 23x16；帧内首行含 `sokoban`；HUD 含 `level 1/6` |
| 2 | `test_builtin_levels_are_well_formed` | 每关：恰 1 玩家、箱数 == 目标数、行宽 ≤ 21、行数 ≤ 12 |
| 3 | `test_walk_moves_the_player_once` | 第 6 关向左一步 → `player_x` 减 1、`moves == 1` |
| 4 | `test_pushing_a_box_onto_a_goal_marks_it_solved` | 第 6 关连按 `right` 两次 → `solved == true`、`pushes == 2` |
| 5 | `test_box_against_a_wall_does_not_move` | 造死角（第 1 关）推箱撞墙 → 箱子与玩家都不动、`moves` 不增 |
| 6 | `test_undo_restores_the_previous_position` | 推一步后 `u` → 玩家/箱子位置复原、`moves` 回退 |
| 7 | `test_undo_at_start_is_a_no_op` | 开局 `u` → 局面不变、`undo_depth == 0` |
| 8 | `test_restart_restores_the_level_layout` | 走几步后 `r` → `moves == 0`、箱子回初始格 |
| 9 | `test_next_level_only_after_solving` | 未解时按 `n` → 仍是第 1 关；解后按 `n` → `level == 2` |
| 10 | `test_progress_is_saved_and_resumed` | 解第 1 关后关闭 → `sokoban.json` `{level:2, completed:[1]}`；重新 setup → 第 2 关 |
| 11 | `test_last_level_cleared_reports_and_restarts` | `load_level(6)` 解关后 `n` → 画面含 `all levels cleared`；`r` → `level == 1` |
| 12 | `test_moves_and_pushes_accumulate_across_levels` | 解第 1 关进第 2 关后存档 `moves` 等于两关之和 |

## 八、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_game_sokoban.py -q
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/sokoban.lua
```

## 九、风险与约束

- 多字节字形禁止参与字节切片：行拼装一律 `table.concat(cells)`，补齐用 `#cells` 计数。
- 撤销必须同时保存「玩家旧格 + 箱子旧格」，否则推箱撤销会错位。
- 只改两个独占文件；缺引擎能力上报主代理。
