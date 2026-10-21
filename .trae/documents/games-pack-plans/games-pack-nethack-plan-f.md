# F 波：NetHack（`nethack.lua`，nerd 图标）

上级：[overview.md](overview.md) ｜ 依赖：[engine 契约](games-pack-engine-plan-b.md) §三 ｜ 独占文件：
`yate/extensions/nethack.lua`、`tests/test_lua_game_nethack.py`

## 一、目标

` :game nethack ` 打开一个**回合制地牢**：用 **nerd font 图标**替代简单 ASCII（默认），
可切 ASCII 回退；房间+走廊程序生成、战斗、拾取、下楼、死亡与**楼层存档续玩**。

## 二、画面（画布 52 x 22）

```
┌─ nethack ─────────────────────────────────────────┐   row 1
│                                                  │   row 2..19  地图 18 行 x 50 列
│                  (50x18 tiles)                   │
│                                                  │
│ depth 3   hp 8/12   gold 30   turn 210           │   row 20  HUD
│ move/attack arrows  g grab  enter stairs  space wait  r new  v glyphs │  row 21  help
└──────────────────────────────────────────────────┘   row 22
```

- `cols = 52`、`rows = 22`；地图固定 **50 x 18**（1 字形/格，四周为墙）。
- 地图行由 `table.concat(cells)` 拼出（**多字节字形**），因此**不得**用 `engine.frame`：
  自己拼 `"│" .. row .. "│"`，`row` 的字符数固定 50（显示宽度由字形保证，见 §三）。
- 状态栏：`session:status("depth " .. depth .. "  hp " .. hp .. "/" .. max_hp .. "  gold " .. gold)`。

## 三、字形表（nerd 默认 / ascii 回退）

`engine.utf8_char(code)` 可用且 `glyphs == "nerd"` 时用 nerd 列，否则用 ascii 列。
**所有码位必须落在 Nerd Fonts 的 Font Awesome 4 段**（这些码位在主流 Nerd Font 中通用）：

| 语义 | nerd 码位 | nerd 字形 | ascii |
|---|---|---|---|
| 玩家 | `0xf007` | user | `@` |
| 墙 | `0xf0c8` | square | `#` |
| 地板 | `0xf111` | circle（暗） | `.` |
| 走廊 | `0x00b7` | middle dot | `#` |
| 楼梯 | `0xf0ab` | angle-double-down | `>` |
| 怪物（近战） | `0xf1e4` | paw | `r` |
| 怪物（强） | `0xf06d` | fire | `Z` |
| 金币 | `0xf0d6` | money | `$` |
| 药水 | `0xf0fc` | flask | `!` |
| 武器 | `0xf0e7` | bolt | `)` |
| 食物 | `0xf0f5` | cutlery | `%` |
| 墓碑 | `0xf0f3` | bell（近似） | `+` |

调色板按**字形字符串**给色（`palette[glyph] = "#rrggbb"`）：玩家 `#ffd54f`、墙 `#616161`、
地板 `#9e9e9e`、楼梯 `#ffffff`、怪物 `#e53935`、金币 `#ffd54f`、药水 `#64b5f6`、武器 `#bdbdbd`、
食物 `#7bd88f`、墓碑 `#bdbdbd`。

> `v` 键在 nerd / ascii 之间切换，并把选择写回存档（`"glyphs"` 字段）。

## 四、世界生成（确定性）

`depth` 与 `seed` 唯一决定一层：

1. `rng = engine.rng(seed)`；房间数 `4 + rng.int(2)`（4..5）；
2. 房间：在 50x18 内按网格放置（每格 12x8 的区域随机取宽 4..7、高 3..5 的房间），**不可重叠**，
   房间之间至少隔 1 格；放不下就放弃该房间（至少 3 个）；
3. 走廊：按房间顺序把中心点用「先横后竖」两段挖通，连接相邻房间；
4. 楼梯 `>` 放在**最后一个房间**的随机地板格；玩家出生在第 1 个房间；
5. 怪物：`2 + depth` 只，随机地板格（不在玩家半屏内）；种类按 `rng.int`：
   `paw`（hp `2 + depth`，atk 1）、`fire`（hp `4 + depth*2`，atk 2），强度随深度上升；
6. 物品：`1 + rng.int(3)` 个，随机地板格；种类 `gold`（金额 `5 + rng.int(20)`）、
   `potion`（+3 HP）、`weapon`（攻击 +1，可重复拾取叠加，上限 +5）、`food`（+2 HP）。

## 五、回合与战斗

| 动作 | 键 | 规则 |
|---|---|---|
| 移动 | 方向键 / hjkl / wasd | 目标格是墙 → 无操作（不消耗回合）；是怪物 → **攻击**；否则移动 |
| 攻击 | 同上（撞怪） | 伤害 `1 + rng.int(3) + weapon`；怪物 hp ≤ 0 → 死亡、`rng.int(2)==1` 掉金币 |
| 等待 | `space` | 消耗一回合 |
| 拾取 | `g` | 拾取脚下所有物品（金币累加；药水/食物回血；武器 +1 攻击） |
| 下楼 | `enter` | 仅在楼梯格：`depth+1`、`max_hp+2`、`hp = min(max_hp, hp + 5)`、生成新层 |
| 新开局 | `r` | 死亡后可用；清存档，`depth=1`、`hp=max_hp=10`、`gold=0`、`new seed` |
| 字形切换 | `v` | nerd ↔ ascii，写回存档 |

怪物行动（玩家动作后）：邻格玩家 → 攻击 `1 + rng.int(2)`（`fire` 为 `2 + rng.int(2)`）；
否则朝玩家走一格（曼哈顿距离贪心，撞墙则沿另一轴绕行，全部受阻则不动）。

死亡：`hp <= 0` → 清除存档、画面覆盖 `rest in peace` / `press r`，回合停止。

## 六、持久化（`games/nethack.json`）

```json
{"version":1,"player":"alice","glyphs":"nerd",
 "save":{"depth":3,"turn":210,"seed":123456,"hp":8,"max_hp":12,"gold":30,"weapon":1,
         "rng":123456789,
         "player_pos":[10,5],
         "floor":["####...", "..."],
         "monsters":[{"x":3,"y":4,"kind":"paw","hp":3}],
         "items":[{"x":5,"y":6,"kind":"gold","amount":12}]}}
```

- **每回合保存一次**（文件 < 4 KB，原子写）；`on_close` / `teardown` 再存一次兜底；
- 启动时若有合法 `save` → 直接恢复（`floor` 是字形无关的**语义字符**行：用 `#`/`.`/`>` 等
  ASCII 语义集存储，渲染时才映射到 nerd 字形 —— 这样 `v` 切换不会污染存档，也不会因字体缺字读不回）；
- 死亡 / `r` → `store.clear()`；
- 坏 JSON → 新开局并 `yate.message` 一次提示。

> 关键定案：**存档只存语义地图（ASCII 语义字符），字形是纯渲染层**。

## 七、模块表与测试缝

```lua
setup / teardown / snapshot
set_seed(n)          -- 固定本局随机种子（生成 + 战斗）
load_state(t)        -- 直接注入局面（同存档 save 结构），用于确定性测试
snapshot()
```

`snapshot()` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `depth` / `turn` | number | 深度 / 回合 |
| `hp` / `max_hp` / `gold` / `weapon` | number | 属性 |
| `player_x` / `player_y` | number | 地图 1-based 坐标 |
| `glyphs` | string | `"nerd"` / `"ascii"` |
| `monsters` | array | `{x, y, kind, hp}` |
| `items` | array | `{x, y, kind}` |
| `alive` | boolean | 是否存活 |
| `on_stairs` | boolean | 是否站在楼梯格 |
| `depth_saved` | boolean | 是否存在可续存档 |

## 八、测试 `tests/test_lua_game_nethack.py`

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_game_nethack_opens_the_map_canvas` | canvas 52x22；首帧含 `nethack`；HUD 含 `depth 1`、`hp 10/10` |
| 2 | `test_map_is_deterministic_for_a_seed` | 两个 harness 同 seed → `snapshot()` 的 `player_x/player_y` 与怪物列表一致 |
| 3 | `test_player_moves_onto_floor` | `load_state` 造空地 → 按 `right` → `player_x+1`、`turn+1` |
| 4 | `test_wall_blocks_movement_without_a_turn` | 墙在右 → 按 `right` → 位置与 `turn` 不变 |
| 5 | `test_bumping_a_monster_attacks_it` | 怪物贴右侧、hp=1 → 按 `right` → 怪物消失/数量减 1 |
| 6 | `test_monster_attacks_back_and_can_kill_the_player` | hp=1 + 怪物贴脸 + `space` → `alive == false`、画面含 `rest in peace` |
| 7 | `test_grab_collects_gold_potion_and_weapon` | 脚下三件物品 → `g` → `gold` 增加、`hp` 上升、`weapon` +1 |
| 8 | `test_enter_on_stairs_descends_and_heals` | 站在 `>` → `enter` → `depth == 2`、`max_hp == 12` |
| 9 | `test_enter_off_stairs_does_nothing` | 非楼梯格 `enter` → `depth` 不变、`turn` 不变 |
| 10 | `test_default_glyphs_are_nerd_icons` | `snapshot().glyphs == "nerd"` 且首帧含任一私用区字形（字节 > 0x7f） |
| 11 | `test_v_toggles_ascii_glyphs_and_persists` | `v` → `glyphs == "ascii"`、帧内出现 `@`；存档 `glyphs == "ascii"` |
| 12 | `test_turn_state_is_saved_and_resumed` | 走两步后关闭 → `nethack.json` 有 `save`；重新 setup → `turn`/`depth`/坐标一致 |
| 13 | `test_death_clears_the_save` | 死亡后 `nethack.json` 无 `save`；`r` 后 `depth == 1`、`alive == true` |

## 九、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_game_nethack.py -q
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/nethack.lua
```

## 十、风险与约束

- **字形宽度**：只用单宽私用区码位；`v` 回退 ASCII 是兜底；不得在需要字节对齐的行里混排字形。
- 存档只存语义字符；`load_state` 与存档结构必须同构（同一份 `from_state` 代码路径）。
- 每回合写盘必须 `pcall`：写失败不能打断游戏（`engine.store.save` 已兜底返回 `false`）。
- 只改两个独占文件；缺引擎能力上报主代理。
