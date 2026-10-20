# games-pack 视觉修复与扩展重构方案（第二轮）

- 分支：`feat/games-pack`（沿用，未合并）；基线上轮收尾 `b70dbdb`
- 触发：用户实测截图 + 6 条问题清单（对齐 / 尺寸 / 关卡数 / 可读性 / 扩展结构）
- 关联：[games-pack-plan.md](games-pack-plan.md)（首轮）｜[overview.md](games-pack-plans/overview.md)

## 一、问题清单（用户）与实测复现

| # | 用户描述 | 实测结论（可复现） |
|---|---|---|
| 1 | 俄罗斯方块 `next` 右边框没对齐 | **真 bug**：`engine.center()` 只补左侧空格、不补右侧，`"│" .. center(8,16) .. "│"` 实际只有 11~15 列；4 行预览行实测 **55 列**（期望 59），画布右侧补齐后右箱整体左移 4 列 |
| 2 | 贪食蛇画面乱七八糟、界面太小 | **真 bug**：`snake.lua:238` 用 `#label`（字节数）算边框填充，标题含 `★`（3 字节）→ 顶边少 2 列（实测 60 vs 62）；HUD/帮助行同源问题。尺寸 62×22 偏小 |
| 3 | pacman 界面太小 | 21×23，迷宫 19×21，实际可玩区域小 |
| 4 | sokoban 有错层、6 关太少、界面太小 | **真 bug**：`area_row` 用 `engine.pad` 补行，而 `pad` 按**字节**截断/补齐，行内含 `█ ▣ ☻ ◎`（3 字节）→ 行被截到 21 字节（≈7~10 个字形），`│` 落在错误列 → 错层。关卡 6 关、画布 23×17 |
| 5 | nethack 界面混乱看不清楚 | 结构层（墙/地板/走廊）也用 nerd 图标（`0xf0c8`/`0xf111`），整屏灰点噪声；配色对比不足；地图 50×18 |
| 6 | extensions 下需重构，不要白名单、不要破坏边界 | **用户裁定（2026-10-21）**：`lib/` 结构保持现状、不做迁移；本轮只把「共享模块经 `package.preload`、loader 不自动装载 `lib/`」的既有机制在文档中写清，不新增任何豁免/白名单 |

### 1.1 根因归纳（一条主因 + 三处放大）

**主因**：`engine_layout.lua` 的宽度函数全部按 **字节** 计算（`#value`、`value:sub`），
遇到多字节字形（`█ ╭ ★ ▲ ☻ •`、nerd 私用区）时：`pad` 截断切半个字形、`center` 不补右侧、
`box_top` 填充量偏小。三处放大：各游戏自行用 `#label` 算边距（snake）、
结构化内容与 ASCII 混排（sokoban/nethack）、画布尺寸偏小。

## 二、目标与非目标

**目标**

1. 布局层改为**显示宽度（码位）**语义：`width / pad / center / box_top / frame` 全部按码位计算，
   截断按码位（绝不切开字形）；新增行宽自检（`layout.assert_width` 供测试）。
2. 五款游戏画面全部**加宽加高**并消除错层；`next`/`feed`/侧栏边框逐列对齐。
3. sokoban **≥100 关**（可解性由构造保证），pacman 迷宫放大并保持不变量，nethack 视觉可读性重做。
4. extensions 结构重构：共享模块回到**顶层 `_*.lua`**（既有下划线约定），删除 `.gitignore` 例外与
   lint 的白名单常量，文档与测试同步。
5. 全部改动过 pyright / pytest / lint_lua / 覆盖率门禁。

**非目标**

- 不改玩法规则（tetris 手感、snake 速度公式、pacman 幽灵 AI、nethack 回合模型保持不变）。
- 不新增 Python 依赖、不改 canvas 渲染契约（`draw(grid, palette)` 与 `"*"` 语义）。
- 不做主题化配色（沿用现有调色板结构，只提高对比度）。

## 三、设计

### 3.1 布局层：显示宽度语义

`engine_layout.lua` 重写宽度相关函数（其余不变）：

```lua
-- Display width in codepoints; every glyph the pack uses is single width.
function layout.width(text)      -- ASCII fast path, else count UTF-8 leading bytes
function layout.truncate(text, width)   -- cut at codepoint boundary
function layout.pad(text, width)        -- left-align, pad/truncate by width
function layout.center(text, width)     -- BOTH sides padded, width-exact
function layout.box_top(title, inner)   -- fill = inner - width(title) - 3
function layout.frame(title, inner, lines)  -- pad each line by width
```

规则（写进模块头注释与文档）：

1. 只支持**单宽**字形（块、框线、几何符号、FA4 私用区）；emoji 禁用（宽度不可控）。
2. 所有 `#` 只用于表长度与纯 ASCII 计数；任何参与排版的数量必须走 `layout.width`。
3. 测试固化：`width("█")==1`、`width("★")==1`、`pad` 截断不切字形、`center` 结果恒等于目标宽度。

### 3.2 画布尺寸与布局（新）

| 游戏 | 旧 | 新 | 说明 |
|---|---|---|---|
| snake | 62×22 | **80×24** | 棋盘 36×20（每格 2 列 → 72 内宽 + 边框），HUD 一行 + 两行帮助 |
| pacman | 21×23 | **41×29** | 迷宫 39×27（约 2.2 倍面积），豆子/能量豆按新迷宫重排 |
| sokoban | 23×17 | **41×21** | 关卡区 37×17，HUD + 两行帮助 |
| nethack | 52×22 | **74×24** | 地图 72×20，HUD + 帮助各一行；结构用块/阴影，实体用 nerd 图标 |
| tetris | 59×22 | 59×22 | 尺寸不变，只修 `center` 造成的右箱错位（修完自然对齐） |

高度全部 ≤ 24，`YateApp.run_test(size=(100, 30))` 下可完整显示；终端更小时 canvas 裁剪逻辑不变。

### 3.3 sokoban 关卡：6 → 100+（构造保证可解）

- 第 1~6 关保留现有手写关（Microban 1-5 + 教学关）。
- 第 7~120 关由**逆向拉箱生成器**产生（`level_generator`）：
  1. `rng = engine.rng(9000 + index)`；
  2. 在 37×17 区域内生成房间（矩形去掉四角 + 内部随机柱子），保证连通；
  3. 选 `2 + (index % 4)` 个目标格（可行走、互不相邻），箱初始放在目标上（已解状态）；
  4. 执行 `40 + index % 20` 次**反向拉**（玩家站在箱子旁，向远离目标方向拉一格；拉不动就换方向），
     过程中校验玩家可达性；结束时若仍全在目标上则重试（最多 30 次，失败退回上一档参数）；
  5. 产出 `#`/` ` `$`/`.`/`@` 的 ASCII 关卡（视觉层再映射到 `█ ▣ ◎ ☻`）。
- **可解性论证**：每个生成关卡都是「从已解状态出发、只做合法拉动作」的逆向轨迹，
  把拉动作逐条反演即得到一条从当前状态到全箱归位的推箱子解，因此**必然可解**（方案里固化为测试注释）。
- 测试：
  - 关数 ≥ 100；每关：恰 1 玩家、箱数 == 目标数、尺寸 ≤ 37×17、玩家可达所有箱子邻格；
  - 抽样 10 关用**有界 BFS 求解器**（Python 侧，箱数 ≤ 3、状态上限 20 万）验证确实可解；
  - 存档 `level` 夹紧在 `1..#LEVELS`（120）。

### 3.4 pacman 大迷宫

- 迷宫 39×27（左右对称、单宽字符），保持既有不变量：边框全墙、恰 1 个出生点、≥4 能量豆、
  豆子全连通（BFS 断言）、鬼屋 2×3 带门 `-`。
- 幽灵/玩家速度按 tick 常量保持不变（视觉变大不改变节奏）；四鬼用 `▲ △ ▴ ▵` 区分颜色。
- 测试改尺寸断言，并加「迷宫行宽恒 39 / 行数 27 / 豆数 ≥ 180」。

### 3.5 nethack 可读性

- **结构**：墙 `█`（`#3a3a3a`）、地板 `·`（`#8a8a8a`）、走廊 `▒`（`#6b6b6b`）、楼梯 `▼`（白）；
  不再用私用区图标画地板/墙（消除满屏灰点噪声）。
- **实体**：玩家 `☻` 或 nerd `0xf007`、怪物 `▲`/`◆`、金币 `$`→nerd `0xf0d6`、药水 `0xf0fc`、
  武器 `0xf0e7`、食物 `0xf0f5`；`v` 键在 nerd / ascii 间切换（已有）。
- **HUD**：`depth 3  hp 8/12  gold 30  turn 210`，帮助行给出 `v glyphs`、`g grab`、`enter stairs`。
- 地图 72×20（房间 5-7 个），`>` 楼梯放最后房间；存档结构不变（只存语义字符）。

### 3.6 extensions 结构（用户裁定：保持 `lib/` 不动）

`yate/extensions/lib/*.lua` 维持现状（`.gitignore` 例外与 lint 的 `require` 推导均保留，
不再改动）。本轮补两件事即可：

1. `extensions.{en,zh}.md` 的「共享 Lua 模块」小节把机制写清：`lib/` 只经
   `package.preload` 预载、loader 永不把它当扩展、模块名 = 文件名主干；
2. `tests/test_lua_engine.py` 保留「`lib/` 不产生 LoadedExtension」断言（已有）。

不新增任何豁免或白名单，不触碰 R14 门面冻结清单。

## 四、分步实施（波次，含独占文件与验收）

> 波次标记：W1…W6（上一版方案的 V0/V1 结构波已按用户裁定取消）。

### W1 布局层：显示宽度语义（主代理）

- 文件：`yate/extensions/lib/engine_layout.lua`、`tests/test_lua_layout.py`（新）
- 内容：§3.1 全部函数 + 单测（含多字节宽度、截断不切字形、`center` 两侧补齐）。
- 验收：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_lua_layout.py tests/test_lua_engine.py -q
  ```

### W2 tetris + snake（主代理）

- 文件：`yate/extensions/tetris.lua`、`yate/extensions/snake.lua`、
  `tests/test_lua_tetris.py`、`tests/test_lua_game_snake.py`
- 内容：`center` 修复后 tetris 右箱自然对齐（必要时微调）；snake 放大 80×24 并改宽度语义渲染。
- 验收：`pytest tests/test_lua_tetris.py tests/test_lua_game_snake.py -q`

### W3 sokoban（执行子代理 A）

- 文件：`yate/extensions/sokoban.lua`、`tests/test_lua_game_sokoban.py`
- 内容：37×17 关卡区（画布 41×22）+ 逆向拉生成器（6 手写 + 114 生成 = 120 关）+ 宽度语义渲染。
- 验收：`pytest tests/test_lua_game_sokoban.py -q`

### W4 pacman（执行子代理 B）

- 文件：`yate/extensions/pacman.lua`、`tests/test_lua_game_pacman.py`
- 内容：39×27 新迷宫（画布 41×29）+ 尺寸/连通性测试。
- 验收：`pytest tests/test_lua_game_pacman.py -q`

### W5 nethack（执行子代理 C）

- 文件：`yate/extensions/nethack.lua`、`tests/test_lua_game_nethack.py`
- 内容：72×20 地图（画布 74×24）、结构与实体分层字形、对比度、HUD/帮助行。
- 验收：`pytest tests/test_lua_game_nethack.py -q`

### W6 画面自检 + 文档（主代理）

- 新增「画面自检」测试 `tests/test_lua_games_visual.py`：五款游戏首帧——
  1. 每行**显示宽度**（按码位）恰等于 canvas 列数；
  2. 首/末字符为对应边框字形（`╭ ╮ ╰ ╯`）且列位置一致；
  3. 侧栏（tetris `stats`/`next`/`help`）每行等宽；
  4. 不出现 ASCII 占位符（`#`、`@`、`$`、`.`）作为**视觉元素**（nethack ascii 回退模式除外）。
- 文件：`yate/docs/games.{en,zh}.md`、`extensions.{en,zh}.md`、`CHANGELOG*`（工具生成）
- 验收：全量门禁（见 §六）

## 五、文件独占矩阵

| 波次 | 独占文件 |
|---|---|
| W1 | `yate/extensions/lib/engine_layout.lua`、`tests/test_lua_layout.py` |
| W2 | `yate/extensions/tetris.lua`、`snake.lua`、`tests/test_lua_tetris.py`、`tests/test_lua_game_snake.py` |
| W3 | `yate/extensions/sokoban.lua`、`tests/test_lua_game_sokoban.py` |
| W4 | `yate/extensions/pacman.lua`、`tests/test_lua_game_pacman.py` |
| W5 | `yate/extensions/nethack.lua`、`tests/test_lua_game_nethack.py` |
| W6 | `tests/test_lua_games_visual.py`、`yate/docs/**`、`CHANGELOG*` |

## 六、门禁

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -o addopts=""
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-report=term --cov-fail-under=75 -o addopts="" -q
.venv\Scripts\python.exe tools/lint_lua.py
```

## 七、风险

| 风险 | 缓解 |
|---|---|
| 生成器产出「太简单/不可解」 | 只做合法拉动作（可解性构造保证）；抽样 BFS 求解测试；难度用拉数控制 |
| 100+ 关首帧加载变慢 | 关卡按需生成（进入关卡时生成一次并缓存），启动只解析第 1 关 |
| 大画布在小终端被裁剪 | 高度 ≤ 24；canvas 既有裁剪逻辑不变，文档写明推荐终端 ≥ 100×30 |
| 宽度语义改造引入新错位 | `tests/test_lua_layout.py` + `tests/test_lua_games_visual.py` 双侧守卫（逐行宽度断言） |
| 结构重构打断 `require` | 迁移与 `library.py`、lint、harness 同波提交，测试覆盖 `require("game_engine")` |
| nerd 图标在某些字体双宽 | 结构层不用私用区；实体图标可用 `v` 切 ASCII |

## 八、回滚

单一分支、按波次提交：V0/V1 各一笔、V2~V5 各一笔、V6 一笔；任一环节失败可
`git revert` 对应提交而不影响其余画面修复。
