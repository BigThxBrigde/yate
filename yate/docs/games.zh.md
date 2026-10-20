# 随身游戏包 / The game pack

> 站外权威文档：本指南讲随 yate 分发的游戏。扩展 API 本身见
> [extensions.zh.md](extensions.zh.md)；应用内手册（`:help`）是编辑功能的权威，
> 不重复描述游戏。

yate 内置一小包**纯 Lua 扩展**实现的游戏：它们跑在编辑器里，画到模态字符画布上，
进度存在 `~/.yate/data/games/`。除通用扩展 API 外，游戏没有任何 Python 侧实现，
所以它们同时也是「Lua 扩展能做什么」的最好样例。

## 1. 快速开始

```text
:game                 列出可用游戏
:game snake           启动贪食蛇
:game player alice    把高分署名改成 alice
escape                退出正在运行的游戏
```

游戏是模态的：运行期间所有按键都归它（含 `escape`，由画布自己消费并关闭）。
时钟是画布固定的 15 Hz tick，所以速度用 tick 表达，不受机器负载影响。

| 游戏 | 命令 | 一句话 |
|---|---|---|
| 贪食蛇 | `:game snake` | 吃、变长、别咬到自己 |
| 吃豆人 | `:game pacman` | 清空迷宫、躲开幽灵 |
| 推箱子 | `:game sokoban` | 把所有木箱推上目标点 |
| NetHack | `:game nethack` | 在程序生成的地牢里往下走 |
| 俄罗斯方块 | `:game tetris` | 堆满之前消行 |

## 2. `:game` 命令

| 形式 | 效果 |
|---|---|
| `:game` | 打印 `usage: :game <name> (games: nethack pacman snake sokoban tetris)` |
| `:game <名字>` | 启动该游戏；未知名字打印 `unknown game: chess (available: ...)` |
| `:game player` | 打印 `player: <名字>` |
| `:game player <名字>` | 修改 `games/profile.json` 里的玩家名 |

同一时刻只能有一个画布：请求已经在运行的游戏会打印 `<名字> is already running`，
并保留当前这局。

## 3. 各游戏

五款游戏共用同一套版式（圆角边框、标题、HUD 行、帮助行）、Unicode 框线与块字符，
以及同样三个键：`p` 暂停（有时间推进的游戏）、`r` 重开、`escape` 退出。

### 3.1 贪食蛇

```text
╭─ snake ──────────────────────────────────────────────────────╮
│ score 28   best 40 (alice)   length 7                        │
│                                                              │
│                    ██████                                    │
│                         ██                                   │
│              ●●          ██                                  │
│                                                              │
│ help: arrows/hjkl/wasd turn   p pause   r restart             │
╰──────────────────────────────────────────────────────────────╯
```

| 按键 | 作用 |
|---|---|
| `←` `→` `↑` `↓`、`hjkl`、`wasd` | 转向（180° 反向被忽略，转向在下一步生效） |
| `p` | 暂停 / 继续 |
| `r` | 重开（新棋盘，分数归零） |

规则：初始 3 格；吃到食物 +10 分并长一格；撞墙或撞到自己结束本局。
步进间隔 `max(3, 10 - 分数 // 50)` tick，所以越吃越快。

存档：前 5 名、局数、最长长度。

### 3.2 吃豆人

```text
╭───────────────────╮
│███████████████████│
│█········█········█│
│█·██·███·█·███·██·█│
│█●···············●█│
│████·███·█·███·████│
│     █  ▲△▴▵  █     │
│████·███·█·███·████│
│█········◉········█│
│███████████████████│
╰───────────────────╯
```

| 按键 | 作用 |
|---|---|
| 方向键 / `hjkl` / `wasd` | 请求方向（缓冲到下一格才生效） |
| `p` | 暂停 / 继续 |
| `r` | 从第 1 关重开 |

计分：豆子 10、能量豆 50、同一次惊恐内吃鬼 200 / 400 / 800 / 1600、过关 500。
共 3 条命；非惊恐状态下被幽灵碰到掉一条命。幽灵 AI 完全确定（不用随机数），
所以同一局可复现。

存档：前 5 名、局数、通关数。

### 3.3 推箱子

```text
╭─ sokoban ───────────╮
│     ██████          │
│     █ ▣  █          │
│     █ ☻ ◎█          │
│     ██████          │
│                     │
│ level 1/6  m0 p0 d0 │
│ u undo r rst n next p│
╰─────────────────────╯
```

| 按键 | 作用 |
|---|---|
| 方向键 / `hjkl` / `wasd` | 走动；箱子后方是空地时推动箱子 |
| `u` | 撤销一步（角色与它推过的箱子），最多 200 步 |
| `r` | 重开本关 |
| `n` | 下一关（仅本关完成后） |
| `p` | 暂停 |

规则：撞墙或推不动的箱子不算一步。所有目标点上都放上箱子即过关；
最后一关之后画面提示 `all levels cleared`，按 `r` 从第 1 关重开。
内置 6 关（5 关取自公开的 Microban 关卡集 + 1 关教学关）。

存档：当前关、已完成关列表、累计步数/推动数 —— 下次打开继续停下的那一关，
关卡本身从头开始。

### 3.4 NetHack

```text
╭─ nethack ─────────────────────────────────────────╮
│                                                  │
│               （50 x 18 地牢格）                  │
│                                                  │
│ depth 3   hp 8/12   gold 30   turn 210           │
│ move/attack  g grab  enter stairs  space wait  r new  v glyphs │
╰──────────────────────────────────────────────────╯
```

| 按键 | 作用 |
|---|---|
| 方向键 / `hjkl` / `wasd` | 走一步；撞向怪物即攻击 |
| `space` | 原地等待一回合 |
| `g` | 拾取脚下的所有物品（金币、药水、武器、食物） |
| `enter` | 站在楼梯（`>`）上时下楼，越深怪越强 |
| `r` | 死亡后开新局（清除存档） |
| `v` | 在 nerd 图标与 ASCII 回退之间切换（记入存档） |

楼层由 `depth` 与种子唯一决定，同一局可复现。**每回合自动存档**，所以中途关掉
编辑器再打开会接着上次的位置；死亡会清档。地图按语义字符（`#` 墙、`.` 地板、
`,` 走廊、`>` 楼梯）存储，切换字形不会污染存档。

### 3.5 俄罗斯方块

```text
╭─ stats ───────╮ ╭─ tetris ────────────╮ ╭─ next ─────────╮
│ score        0│ │                      │ │                │
│ level        1│ │        ████          │ │      ████      │
│ best      1500│ │        ████          │ │      ████      │
╰───────────────╯ │                      │ ╰────────────────╯
                  ╰──────────────────────╯ ╭─ help ─────────╮
                                           │ left     ←     │
                                           │ drop  space    │
                                           ╰────────────────╯
```

| 按键 | 作用 |
|---|---|
| `←` `→`、`↓` | 左右移动、软降 |
| `↑` / `x` | 顺时针旋转（带踢墙） |
| `space` | 硬降 |
| `enter` | 落定：方块全速下落且不再可控 |
| `p` / `r` | 暂停、重开 |

计分沿用 NES 表（消 1/2/3/4 行为 100 / 300 / 500 / 800，乘当前等级），
`等级 = 1 + 消行数 // 10`。存档：前 5 名、局数、消行总数。

## 4. 存档

全部位于 `~/.yate/data/games/`，每个游戏一个 JSON 文档。写入是原子的
（临时文件 + 重命名）；文档损坏时按「还没有存档」处理，并在消息行提示一次，
绝不让运行中的游戏崩掉。

| 文件 | 字段 |
|---|---|
| `profile.json` | `version`、`player` |
| `snake.json` | `version`、`player`、`high_scores[{score, player, at}]`、`stats{games, best_length}` |
| `pacman.json` | `version`、`player`、`high_scores[...]`、`stats{games, levels}` |
| `tetris.json` | `version`、`player`、`high_scores[...]`、`stats{games, lines}` |
| `sokoban.json` | `version`、`level`、`completed[...]`、`moves`、`pushes` |
| `nethack.json` | `version`、`player`、`glyphs`、`save{depth, turn, seed, hp, max_hp, gold, weapon, rng, player_pos, floor[], monsters[], items[]}` |

`high_scores` 最多保留 5 条，按分数降序，每条含分数、玩家名与本地时间
（`at`，形如 `YYYY-MM-DDTHH:MM:SS`）。

删除某个文件即重置该游戏进度；删除 `profile.json` 会退回 OS 用户名。
扩展里对应的通道是 `api.data`（见 [extensions.zh.md](extensions.zh.md) §4.15）。

## 5. 玩家名与高分署名

高分榜记录**是谁**创造的。名字优先取 `profile.json`，否则取 `USERNAME` / `USER`，
再否则 `player`。修改方式：

```text
:game player alice
```

名字立即写入，作用于下一条记录的分数。

## 6. 字形（NetHack）

NetHack 默认用 Nerd Font 图标：角色、墙、怪物、金币、药水、武器、楼梯都是
Font Awesome 4 码位，经 `utf8.char` 渲染。想要预期观感请安装任一 Nerd Font
补丁字体。

没有这类字体时这些码位会显示为空框。按 `v` 可切到 ASCII 回退
（`@ # . > r $ ! ) %`），选择随存档保存并在下次启动恢复。
其余游戏只用标准 Unicode 框线与几何符号，任何等宽字体都自带。

## 7. 写自己的游戏

一个游戏就是一个 Lua 文件：返回模块表，并在 `setup` 里调用
`engine.register(名字, 启动函数)`。随 yate 分发时放 `yate/extensions/`；
本地自用放 `~/.yate/extensions/`（或已信任的 `./extensions/`）——`:game` 派发器
会枚举已注册的 `game-*` action，自动把它列进可用列表。

`require("game_engine")` 提供公共的一半：

| 成员 | 用途 |
|---|---|
| `engine.json.encode(v)` / `.decode(text)` | 存档用的极简 JSON 编解码 |
| `engine.store(name)` → `{load, save, clear}` | `games/<name>.json` 一个文档 |
| `engine.scores(name)` → `{entries, best, add}` | 前 5 名榜（含玩家与时间） |
| `engine.player()` / `engine.set_player(name)` | 高分署名的玩家名 |
| `engine.register(name, launch)` | 注册 `game-<name>` action |
| `engine.open(spec)` → session | 画布会话（单实例守卫 + `paint` / `status` / `close`） |
| `engine.box_top` / `box_bottom` / `center` / `pad` / `frame` / `panel` | 圆角边框排版 |
| `engine.direction(key)` → `dx, dy` | 方向键 / `hjkl` / `wasd` 映射 |
| `engine.rng(seed)` → `{int, pick, state, set}` | 确定性随机数 |
| `engine.utf8_char(code)` | 码位转 UTF-8 字形，做图标集用 |
| `engine.glyph` | 共享字形词表（`block`、`shade`、`box`、`dot` …） |

一个完整的最小游戏（一个上下移动的点，带最高分）：

```lua
local engine = require("game_engine")

local G = engine.glyph
local mod = {}
local state = nil
local session = nil

local function reset()
  state = { row = 4, score = 0, best = engine.scores("mygame").best() }
end

local function frame(_session)
  local rows = { engine.box_top("mygame", 20) }
  for row = 1, 8 do
    local cell = row == state.row and G.big_dot or G.dot
    rows[#rows + 1] = G.v .. engine.center(cell, 20) .. G.v
  end
  rows[#rows + 1] = engine.box_bottom(20)
  return table.concat(rows, "\n"), { [G.big_dot] = "#e53935", [G.dot] = "#616161" }
end

local function paint()
  if session == nil then
    return
  end
  session.paint()
  session.status("score " .. state.score .. "  best " .. state.best)
end

local function on_key(key)
  local _dx, dy = engine.direction(key)
  if dy == nil then
    return
  end
  state.row = math.max(1, math.min(8, state.row + dy))
  state.score = state.score + 1
  paint()
end

local function start()
  reset()
  session = engine.open({
    name = "mygame",
    cols = 22,
    rows = 10,
    draw = frame,
    on_key = on_key,
    on_close = function()
      session = nil
    end,
  })
  paint()
end

function mod.setup(_api)
  engine.register("mygame", start)
end

function mod.teardown(_api)
  if session ~= nil then
    session.close()
  end
end

return mod
```

要点：

- `draw(session)` 返回「整幅画布（一个换行拼接的字符串）+ 调色板」，
  调色板是 `字形 -> "#rrggbb"`；`"*"` 条目是特殊键，表示「把所有有色格子都画成
  这个字形」（实心方块就用它）。
- 会话方法以点号调用：`session.paint()`、`session.status(text)`、`session.close()`。
- 游戏规则留在自己的文件里，引擎刻意不含规则。
- 想要确定性测试就暴露 `snapshot()`（纯标量表）；用 `engine.rng` 时再暴露 `set_seed(n)`。

## 8. Lua lint

随包的 Lua 脚本都通过仓库的 lint，你也可以自己跑：

```text
python tools/lint_lua.py                     # 校验全部随包 .lua
python tools/lint_lua.py path/to/x.lua
```

退出码：`0` 干净、`1` 有问题、`2` 缺少 `lupa` 包。规则包含一次**真正的 Lua 解析**
（走运行时同一个桥），外加：无 Tab、无行尾空白、行长 ≤ 100、LF 行尾、文件以单个
换行结尾、禁 `print` / `io.` / `os.execute` / `os.exit` / `dofile` / `loadfile`、
禁止裸全局赋值（只有 `yate`、`api`、`mod`、`setup`、`teardown` 可作全局）、
`require` 只允许 `yate` 与随包 `lib/*.lua` 模块。
