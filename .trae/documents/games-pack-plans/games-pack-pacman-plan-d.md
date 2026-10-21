# D 波：吃豆人（`pacman.lua`）

上级：[overview.md](overview.md) ｜ 依赖：[engine 契约](games-pack-engine-plan-b.md) §三 ｜ 独占文件：
`yate/extensions/pacman.lua`、`tests/test_lua_game_pacman.py`

## 一、目标

` :game pacman ` 打开一个「深蓝迷宫 + 豆子 + 4 只彩色幽灵」的吃豆人（参考图像：
深蓝墙、白/黄豆子、四色幽灵、底部黄色吃豆人），支持能量豆吃鬼、掉命、过关、
最高分（含创造者）保存。

## 二、画面（画布 21 x 23）

```
┌───────────────────┐   row 1   top border（21 宽）
│###################│   row 2   \
│#........#........#│          │ 迷宫 21 行 x 19 列
│...                │          │
│###################│   row 22 /
└───────────────────┘   row 23 bottom border
```

- `cols = 21`、`rows = 23`；迷宫 `M` 行数 21、列数 19，四周必须是 `#`。
- 网格：`"│" .. maze_row .. "│"`（迷宫行只用 **单字节** 字符 → 字节宽度 = 显示宽度 19）。
- 状态栏：`session:status("score " .. score .. "  lives " .. lives .. "  level " .. level .. "  best " .. best)`。
- 覆盖文本（死亡/过关）：写在迷宫中部行，宽度保持 19 字节（`game over` / `press r` / `level cleared`）。

### 调色板

画面字形（**渲染层**，非 ASCII；字形词表见 [overview §3.5](overview.md)）：

| 语义 | 字形 | 调色板 |
|---|---|---|
| 墙 | `█`（block） | `#1e3a8a` |
| 豆子 | `·`（dot） | `#f5f5dc` |
| 能量豆 | `●`（big_dot） | `#f5f5dc` |
| 鬼门 | `▒`（light） | `#f5f5dc` |
| 吃豆人 | `◉`（coin） | `#ffd54f` |
| 幽灵 1-4 | `▲`（tri） | `#e53935` / `#f06292` / `#4dd0e1` / `#ffb74d` |
| 惊恐幽灵 | `◆`（diamond） | `#64b5f6` |
| 被吃后的眼 | `◌`（ring） | `#f5f5dc` |

```lua
palette = {
  ["█"] = "#1e3a8a", ["·"] = "#f5f5dc", ["●"] = "#f5f5dc", ["▒"] = "#f5f5dc",
  ["◉"] = "#ffd54f", ["▲"] = "#e53935", ["◆"] = "#64b5f6", ["◌"] = "#f5f5dc",
}
```

> 幽灵颜色区分：四只幽灵共用 `▲` 字形，靠**渲染时的调色板切换**做不到（palette 是字形→色），
> 因此幽灵用 4 个不同字形：`▲`（红）/ `△`（粉）/ `▴`（青）/ `▵`（橙）；
> 惊恐统一 `◆`，眼 `◌`。渲染函数为每只幽灵按 `mode` 选字形。

迷宫字符集：`#` 墙、`.` 豆、`o` 能量豆、`-` 鬼门、` ` 空（不可走）、`P` 玩家出生点、
`G` 鬼屋内部空格（运行期转成空）。**除 `P`/`G` 外的可走字符只有 `. o ' '`**。

## 三、迷宫数据

`M` 必须是 21 行 x 19 列的字符串数组，且满足：

1. 第 1/21 行、每行第 1/19 列都是 `#`；
2. 吃豆人可达所有豆子（测试用 BFS 断言连通：从出生点可达的 `.`/`o` 数 == 全部 `.`/`o` 数）；
3. 恰有 1 个 `P`，至少 2 个能量豆 `o`；
4. 鬼屋用 `G` 围出 2x2 以上空间，门口是一个 `-`。

初版迷宫（可直接采用，但**必须**由测试校验上述 4 条；不满足就改迷宫而不是改测试）：

```
###################
#........#........#
#o##.###.#.###.##o#
#.................#
#.##.#.#####.#.##.#
#....#...#...#....#
####.###.#.###.####
#..#.....#.....#..#
#..#.##.....##..#.#
#....#..GGG..#....#
####.#.G-G.#.#####.#
#....#..GGG..#....#
#..#.##.....##..#.#
#..#.....#.....#..#
####.###.#.###.####
#....#...#...#....#
#.##.#.#####.#.##.#
#o...............o#
#.##.###.#.###.##.#
#.........P........#
###################
```

> 实现时先用脚本核对每行 19 字符、上述 4 条不变量全部成立，再落地。

## 四、规则

| 项 | 规定 |
|---|---|
| 速度 | 吃豆人每 `PAC_EVERY = 4` tick 走一格；幽灵每 `GHOST_EVERY = 5` tick 走一格；惊恐态幽灵每 `7` tick |
| 缓冲转向 | 到达新格时：请求方向可走则采用；否则当前方向可走则继续；否则停下 |
| 计分 | 豆 +10、能量豆 +50、幽灵 `200 * 2^n`（n = 本次惊恐已吃数，0..3）、过关 +500 |
| 能量豆 | `fright_ticks = 60`；期间所有幽灵 `mode = "fright"`，每只被吃过一次后转 `"eyes"` |
| 幽灵 AI（chase） | 在可走邻格中（禁反向）选到玩家曼哈顿距离最小者；并列按固定顺序 `up, left, down, right` |
| 幽灵 AI（fright） | 同上但取**距离最大**者（远离玩家） |
| 幽灵 AI（eyes） | 目标为鬼屋门口 `-` 格；到达后 `mode = "chase"` 并从屋内复活 |
| 掉命 | 吃豆人与 chase/fright 幽灵同格 → `lives-1`，重置双方位置（豆子保留），`fright_ticks = 0` |
| 过关 | 豆子 + 能量豆全清 → `level+1`、迷宫豆子恢复、`best` 更新、继续游戏 |
| 死亡 | `lives == 0` → 覆盖 `game over` / `press r`；`r` 从 level 1 重开 |
| 暂停 | `p` 冻结一切计时 |

## 五、持久化（`games/pacman.json`）

```json
{"version":1,"player":"alice",
 "high_scores":[{"score":1240,"player":"alice","at":"2026-10-20T21:40:00"}],
 "stats":{"games":4,"levels":2}}
```

- 局终（`lives == 0`）与 `on_close` 各写一次；`stats.levels` 累加本次通关数。

## 六、模块表与测试缝

```lua
setup / teardown / snapshot
set_seed(n)          -- 备用（本游戏 AI 无随机；仍需保证确定性）
set_maze(rows)       -- 测试注入小迷宫（nil 恢复内置）；注入后自动重新解析
set_state(t)         -- 测试注入局面：{score, lives, level, pac={x,y,dir}, ghosts={{x,y,mode}}}
```

`snapshot()` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `score` / `lives` / `level` | number | 局面 |
| `pellets` | number | 剩余豆子 + 能量豆总数 |
| `pac_x` / `pac_y` | number | 1-based 迷宫坐标 |
| `pac_dir_x` / `pac_dir_y` | number | 当前方向 |
| `fright_ticks` | number | 剩余惊恐 tick |
| `ghosts` | array | 每项 `{x, y, mode}`，顺序固定（红/粉/青/橙） |
| `alive` / `paused` | boolean | 状态 |
| `best` | number | 最高分 |

## 七、测试 `tests/test_lua_game_pacman.py`

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_game_pacman_opens_the_maze_canvas` | canvas 21x23；首帧含 `┌` 边框与 `#`；状态栏含 `score 0` |
| 2 | `test_builtin_maze_meets_the_contract` | 21x19、边框全墙、恰 1 个 `P`、`o` ≥ 2、豆子全连通 |
| 3 | `test_pacman_moves_one_tile_per_interval` | 按 `left`，`tick(4)` → `pac_x` 减 1 |
| 4 | `test_pellet_is_eaten_and_scored` | 第一步后 `pellets` 减 1、`score == 10` |
| 5 | `test_power_pellet_sets_fright_mode` | 用 `set_maze` 造 `o` 相邻 → `fright_ticks > 0` 且幽灵 `mode == "fright"` |
| 6 | `test_frightened_ghost_is_eaten_and_scored_200` | 幽灵贴脸 + 惊恐 → 吃鬼 `score += 200`、该鬼 `mode == "eyes"` |
| 7 | `test_ghost_collision_costs_a_life` | 幽灵贴脸（非惊恐）→ `lives == 2`、位置重置 |
| 8 | `test_last_life_ends_the_game_and_r_restarts` | `lives == 1` 再撞 → `alive == false` 且画面含 `press r`；`r` 后 `lives == 3`、`level == 1` |
| 9 | `test_clearing_all_pellets_advances_the_level` | 小迷宫 1 颗豆 → 吃到后 `level == 2`、`score` 含 +500 奖励 |
| 10 | `test_pause_freezes_every_clock` | `p` 后 `tick(40)` → `pac_x/pac_y` 不变 |
| 11 | `test_high_score_saved_with_player_and_games` | 局终后 `pacman.json` 的 `high_scores[0]`、`stats.games == 1` |
| 12 | `test_relaunch_shows_saved_best` | 重新 setup → `snapshot().best` 等于存档值 |

## 八、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_game_pacman.py -q
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/pacman.lua
```

## 九、风险与约束

- 迷宫行必须**纯 ASCII**（`engine.frame` 不参与，但字节宽度用于覆盖文本）。
- 幽灵移动必须严格确定性（禁 `math.random`），并列顺序固定，否则测试会抖。
- 只改两个独占文件；缺引擎能力上报主代理。
