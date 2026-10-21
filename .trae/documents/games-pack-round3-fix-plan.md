# games-pack 第三轮修复方案（滚动条 / 穿越 / 蛇渲染 / 细线围栏 / 通道对比 / 图例 / 保存失败）

- 分支：`feat/games-pack`（沿用）；基线 `9483f47`
- 触发：用户第二轮实测截图 + 7 条问题
- 上轮：[games-pack-visual-fix-plan.md](games-pack-visual-fix-plan.md)

## 一、问题与根因（实测）

| # | 用户描述 | 根因（文件:行） |
|---|---|---|
| 1 | pacman 太高出现滚动条；外面边框去掉只留蓝色 | ① `yate/resources/canvas.tcss` 的 `.grid` 画了 `border: round`（那圈细框）且 Screen 无 `overflow: hidden`（内容超高时整屏滚动）；② 游戏自身 41×29 偏高 |
| 2 | pacman 穿越边缘 | 迷宫边界全墙、移动无回绕逻辑 |
| 3 | snake 一大列、食物应为方块 | `snake.lua:258 board_cells(by)` **漏了按行过滤**（`part.y == by`），每行都画整条蛇+食物；食物 `●●` 非方块 |
| 4 | sokoban 围栏粗线遮人 | 双因：墙用 `█` 实心块；玩家 `☻`（U+263B）在 Windows Terminal 呈 **emoji 双宽**，压住右邻格 |
| 5 | nethack 通道不明显 | 走廊 `▒`(#6b6b6b) 与地板 `·`(#9e9e9e) 亮度接近 |
| 6 | 显示「保存失败」 | `data_store.write_text` 的临时文件+replace 在 Windows 上偶发被锁（AV/同步盘），失败直接上报无回退 |
| 7 | 空白处显示图例 | 各游戏无图例（nethack/sokoban/pacman/snake） |

## 二、修复设计

1. **canvas.tcss**：删 `.grid` 的 `border: round`（外框归游戏自己画）；`CanvasScreen` 加 `overflow: hidden`（永不滚动，超出即裁剪，与文档口径一致）。
2. **pacman**：去掉自身 `╭─╮` 外框（画布=迷宫 39×23，重新生成：街道 [1,5,9,13,17,21]、鬼屋 11..15、门 (19,15)、**隧道行 y=13**——边界格 (1,13)/(39,13) 开放为 `.`）；移动回绕 `wrap_x`（pacman、幽灵、eyes 距离 BFS 三处）；状态栏加短图例 `◉ you ▲ ghost ◆ fear ● power · dot`。
3. **snake**：`board_cells` 按 `part.y == by` / `food.y == by` 过滤；食物 `●●`→`▒▒`（红，同族方块）；状态栏加 `█ body ▓ head ▒ food`。
4. **sokoban**：墙渲染改**邻居感知细线**（`─│╭╮╰╯├┤┬┴┼`，孤立柱 `·`，越界视为非墙，颜色不变蓝色）；玩家 `☻`→`▲`（单宽几何符号）；图例行画在关卡区第 13 行（手写关 ≤8 行、生成关 ≤9 行，该行恒空白）：`walls = blue lines  ▣ crate  ▩ done  ◎ goal  ▲ you`。
5. **nethack**：亮度反转——地板 `·` #6a6a6a（暗）、走廊 `▒` #a8a8a8（亮）、墙 `█` #4a4a4a；地图 72×20→**72×19**，画布 74×24→74×23，腾出一行画**图例**（结构 + 当前模式的实体图标：`█ wall · floor ▒ path ▼ stairs  <p> you <m> monster <g> gold <!> potion <f> food`，随 `v` 切换刷新）；`floor_is_valid` 随 MAP_H 收紧（旧 20 行存档作废重开，登记为破坏性变更）。
6. **data_store**：原子写失败（OSError）时**回退为直接整文件写**，仍失败才抛出（桥保持一次提示）；消除 Windows 锁/AV 抖动导致的「保存失败」。
7. **测试与文档**：几何断言更新（pacman 39×23、nethack 74×23）；pacman 边框断言改为「首末行全墙 + 隧道行两端开口」；新增穿越回绕用例、snake 行过滤用例（食物/蛇只出现在自己的行）、sokoban 细线/图例用例、nethack 图例/对比用例；双语文档同步。

## 三、波次与独占文件

| 波次 | 执行者 | 独占文件 |
|---|---|---|
| R1 | 主代理 | `yate/resources/canvas.tcss`、`yate/extensions/snake.lua`、`tests/test_lua_game_snake.py`、`tests/test_lua_games_visual.py`、`tests/test_lua_games_app.py`、`yate/services/data_store.py`、`tests/test_data_store.py` |
| R2 | 子代理 A | `yate/extensions/pacman.lua`、`tests/test_lua_game_pacman.py` |
| R3 | 子代理 B | `yate/extensions/sokoban.lua`、`tests/test_lua_game_sokoban.py` |
| R4 | 子代理 C | `yate/extensions/nethack.lua`、`tests/test_lua_game_nethack.py` |
| R5 | 主代理 | `yate/docs/games.{en,zh}.md`、CHANGELOG（工具生成）、方案回填 |

验收（每波）：各自测试文件全绿 + `tools/lint_lua.py <自己的 lua>` 0 issue；收尾全量门禁
（pyright / pytest / 覆盖率 / lint）由主代理执行。

## 四、风险

| 风险 | 缓解 |
|---|---|
| pacman 迷宫重生成不满足不变量 | 生成脚本逐 seed 校验（边界、对称、连通、豆数、隧道行）后才嵌入 |
| 隧道破坏幽灵 AI/eyes 回家 | wrap 同时接入移动与距离 BFS；eyes 到门的最短路含隧道段 |
| 细线墙在 T 形/十字处字形选错 | 邻居位表驱动 + 视觉测试逐行宽度不变；截图人工复核 |
| 旧 nethack 存档作废 | 登记为破坏性变更（floor_is_valid 按 19 行校验） |
| 画布 39×23 在更小终端仍可能裁剪 | overflow hidden 已保证永不滚动；文档写明推荐终端高度 |

## 〇、实施结果（2026-10-21 回填）

**状态**：全部完成。R2/R3/R4（pacman / sokoban / nethack）由三个执行子代理并行完成
（各自独占两个文件、套件全绿后主代理复核收编；sokoban 关卡行留白由主代理补齐），
R1/R5 主代理完成。

**过程中的重大发现（已修复）**：用户实测的「保存失败」根因不在文件层——
**lupa 2.8 默认的 Lua 5.5 运行时其分代 GC 会在 Lua 回调仍持有 Python 包装对象时将其提前回收**，
实测表现为 `api.data` 在 on_tick 回调链中偶发变成同一画布的 `draw` 绑定方法，
导致每次按回合保存都报 `save failed`。修复：`create_runtime` 固定使用
`lupa.lua54.LuaRuntime`（Lua 5.4 无此缺陷）；修复后同一测试连续 5 次全绿。
另按原计划保留 `data_store` 的直接写回退（Windows 文件锁兜底）。

**门禁实测（退出码全 0）**：pyright `0 errors`；pytest 全量 **2779 passed / 9 skipped**；
`tools/lint_lua.py` **0 issue(s)**；覆盖率 ≥ 75。

**逐条对照**：① 外框 = canvas.tcss 的 `border: round`，已删，Screen 加 `overflow: hidden` 永不滚动；
② pacman 39×23 贴满画布 + 第 14 行隧道穿越（pacman/幽灵/eyes BFS 三处回绕）；
③ snake `board_cells` 行过滤修复 + 食物改块字形 + 状态栏图例；
④ sokoban 细线围栏（邻居感知框线字符）+ 玩家 `▲` 单宽字形 + 框内图例行；
⑤ nethack 走廊提亮/地板压暗 + 72×19 地图 + 图例行（随 `v` 切换）；
⑥ 保存失败 = Lua 5.5 GC 问题 + 直接写回退；
⑦ 图例：pacman 状态栏、sokoban 框内行、nethack 图例行、snake 状态栏。
