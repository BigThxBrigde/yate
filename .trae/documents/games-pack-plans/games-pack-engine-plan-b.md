# B 波：公共引擎 `game_engine.lua` + 包入口 `games.lua` + 测试脚手架

上级：[overview.md](overview.md) ｜ 依赖：[A 波](games-pack-data-api-plan-a.md) ｜ 下游：C/D/E/F/G

## 一、目标与非目标

**目标**

1. `yate/extensions/lib/game_engine.lua`（下称 **engine**）：五款游戏共享的全部非玩法逻辑。
2. `yate/extensions/games.lua`：包入口扩展，只做一件事——注册 `:game` 命令并派发。
3. `tests/lua_game_harness.py`：录制型 fake API（canvas / data / actions），C-G 波复用。
4. `tests/test_lua_engine.py`：engine 全部公共面 + 派发文案 + 单实例守卫 + `lib/` 不被当扩展。

**非目标**

- engine 不含任何玩法规则（蛇怎么长、幽灵怎么追、关卡怎么算全是游戏文件的事）。
- engine 不做字体探测（nerd/ascii 由 nethack 决定）。
- engine 不注册除 `:game` 之外的命令。

## 二、文件与模块形态

### 2.1 `yate/extensions/lib/game_engine.lua`

- 位置：`lib/` 子目录 → **不被 loader 当扩展**（`loader.load_directory` 只 glob 顶层）。
- 形态：普通 Lua 模块，`local engine = {} ... return engine`；
  **不得**定义 `setup` / `teardown`（它不是扩展）。
- 顶部 `--[[ ... ]]` 英文头注释：职责、被谁 require、禁止事项（不得写文件 IO、不得 print）。
- 只用 `yate.*` 公共面：`yate.message` / `yate.ui.open_canvas` / `yate.data.*` /
  `yate.actions.*` / `yate.register_action`。禁止 `io` / `os.execute` / `print`。

### 2.2 `yate/extensions/games.lua`

```lua
--[[ yate bundled extension: games pack entry point ... ]]
local engine = require("game_engine")
local mod = {}

function mod.setup(_api)
  yate.register_command("game", engine.dispatch, "launch a bundled game")
end

function mod.teardown(_api) end

return mod
```

- `require("game_engine")` 在本 runtime 内编译 `lib/game_engine.lua` 得到**本 runtime 自己的** engine 表；
  `mod.setup` 不调用 engine 的 setup（engine 没有 setup）。
- 命令描述固定 `"launch a bundled game"`（测试断言）。

## 三、engine 公共面（逐函数契约）

### 3.1 JSON

```lua
engine.json.encode(value) -> string
engine.json.decode(text) -> value, nil | nil, string
```

`encode` 规则：

- `nil` → `"null"`；`boolean` → `true`/`false`；
- `number`：整数值用 `string.format("%d")`，否则 `string.format("%.14g")`；`nan`/`inf` → `"null"`；
- `string`：转义 `"` `\` 与 `\b \f \n \r \t`，其余 `\x00-\x1f` 用 `\u00XX`；
- `table`：`next(t) == nil` → `"[]"`；键集合恰为 `1..n` 连续整数 → 数组；否则对象
  （键强制 `tostring`，按 `pairs` 顺序；**不排序**——调用方要稳定就自己给数组）；
- 其它类型（function / userdata）→ `"null"`。

`decode` 规则：

- 递归下降，接受标准 JSON；`null` → `nil`（在数组里以 `false` 占位？**定案**：数组中的 `null`
  解码为 `engine.json.null` 哨兵表 `{}`，避免数组空洞）；
- 错误返回 `nil, "json: <reason> at <pos>"`；
- `\uXXXX` 支持 BMP + 代理对（`utf8.char` 可用时）；无 `utf8` 时 `\uXXXX` 原样保留为 `?`。

### 3.2 存档

```lua
engine.store(name) -> store
store.load() -> table | nil          -- 文件缺失/坏 JSON → nil
store.save(value) -> boolean         -- 写 "games/<name>.json"
store.clear() -> boolean
store.path                           -- "games/<name>.json"
```

- 内部 `pcall(yate.data.write, ...)`：失败返回 `false` + `yate.message("save failed: <name>")` 一次。
- `load` 对 `version` 不做强制校验（各游戏自己看 `version`）。

### 3.3 最高分

```lua
engine.scores(name) -> board
board.entries() -> {{score=number, player=string, at=string}, ...}   -- 前 5，降序
board.best() -> number                                                -- 无记录 0
board.add(score) -> rank | nil                                        -- 1..5；未上榜 nil
```

- `add` 读整份文件（保留未知字段）、插入 `{score=..., player=engine.player(), at=engine.now()}`、
  排序（同分先到先留：稳定插入）、截断 5、写回；
- 同时把文件顶层 `player` 更新为当前玩家名、`version` 置 1。

### 3.4 玩家名

```lua
engine.player() -> string      -- profile.json 的 player；否则 os.getenv("USERNAME") → os.getenv("USER") → "player"
engine.set_player(name) -> string   -- 去空白；空名忽略并返回原名；写 profile.json 后返回
```

### 3.5 注册与派发

```lua
engine.register(name, launch)  -- yate.register_action("game-"..name, launch, "launch the "..name.." game")
engine.games() -> {name, ...}  -- 由 yate.actions.names() 过滤 "game-" 前缀并排序
engine.available() -> string   -- table.concat(games(), " ")
engine.dispatch(args)          -- :game 的完整语义
```

`dispatch` 分支（顺序固定）：

1. `args` 去空白为空 → `yate.message("usage: :game <name> (games: " .. engine.available() .. ")")`；
2. 首词为 `player`：无第二词 → `yate.message("player: " .. engine.player())`；
   有 → `engine.set_player(word)` 后同样回 `"player: <name>"`；
3. `yate.actions.has("game-" .. word)` 为假 →
   `yate.message("unknown game: " .. word .. " (available: " .. engine.available() .. ")")`；
4. 否则 `yate.actions.run("game-" .. word)`。

`games()` 实现要点：`yate.actions.names()` 返回 **Python list（0-based）**，长度用
`python.builtins.len(list)`；`pcall` 包住，取不到时返回 `{}`。排序后返回 Lua 数组。

### 3.6 canvas 会话

```lua
engine.open(spec) -> session | nil
-- spec = {
--   name    = "snake",                  -- 必填，用于 "already running" 文案
--   cols    = 62, rows = 22,            -- 必填
--   draw    = function(session) -> grid, palette end,   -- 必填
--   on_key  = function(key, session) end,               -- 可选
--   on_tick = function(session) end,                    -- 可选
--   on_close= function(session) end,                    -- 可选
-- }
```

- 单实例：本模块内 `local active = nil`；已存在 → `yate.message(spec.name .. " is already running")`，
  返回 `nil`（这是**每游戏**守卫：每个游戏自己的 runtime 各有 `active`）。
- 创建 `session = {name=..., cols=..., rows=..., closed=false}`，方法（用 `:` 调用，纯 Lua 表）：
  - `session:paint()` → `local grid, palette = spec.draw(session)`；`handle.draw(grid, palette)`；
    若 `grid == nil` 则跳过（渲染失败不崩 canvas）。
  - `session:status(text)` → 追加后缀（若文本已以 `"  escape quits"` 结尾则不重复）。
  - `session:close()` → `handle.close()`；`active = nil`；`session.closed = true`。
  - `session:is_open()` → `active ~= nil and not session.closed`.
- 回调包装：`key` / `tick` 里先判 `session.closed`，再转调 spec 的同名钩子；
  `on_close` 里 `active = nil; session.closed = true; spec.on_close(session)`。
- 任何钩子抛错**不**在 engine 内 `pcall`（canvas 已统一兜底并提示）。

### 3.7 绘制助手（全部按**字节长度**计算，调用方只用 ASCII 文本）

```lua
engine.box_top(title, inner)   -- "┌─ " .. title .. " " .. rep("─", inner-#title-3) .. "┐"
engine.box_bottom(inner)       -- "└" .. rep("─", inner) .. "┘"
engine.center(text, width)     -- 左少右多
engine.pad(text, width)        -- " " .. text .. 余量（左对齐）；text 超宽则截断
engine.frame(title, inner, lines)  -- 返回 {box_top, "│"..line.."│"..., box_bottom}
engine.panel(title, width, lines)  -- 同 frame，参数名区分用途
engine.trim(s)                 -- 去首尾空白
engine.rep(s, n)               -- string.rep（n<=0 返回 ""）
engine.now()                   -- os.date("%Y-%m-%dT%H:%M:%S")
```

`frame` 对每行先 `engine.pad(line, inner)` 再套边框，因此行内容不足会自动补空格、超宽会截断，
保证整体对齐。

### 3.8 输入与随机

```lua
engine.direction(key) -> dx, dy | nil
-- left/h/a → -1,0 ; right/l/d → 1,0 ; up/k/w → 0,-1 ; down/j/s → 0,1
engine.rng(seed) -> rng
rng.int(n) -> 1..n          -- LCG: state = (state * 1103515245 + 12345) % 2147483648
rng.pick(t) -> t[rng.int(#t)]
rng.state() -> number
rng.set(n) -> number
```

- `engine.direction` 返回 `nil` 表示「不是方向键」，调用方必须 `if dx == nil then ... end`。
- `rng` 必须有明确初值（`seed` 为 nil 时用 `2147483647`），保证同 seed 同序列。

### 3.9 字形原语

```lua
engine.utf8_char(code) -> string | nil   -- utf8 库存在时返回 utf8.char(code)，否则 nil
```

NetHack 用它在 nerd/ascii 两套字形间切换（字形表归 nethack 自己）。

## 四、测试脚手架 `tests/lua_game_harness.py`

> 顶层 docstring 说明：录制型 fake API，**绝不触碰真实家目录**（data 走内存 dict）。

```python
requires_lupa = pytest.mark.skipif(...)     # 与 test_lua_tetris.py 同款

class FakeCanvas:      # draw/set_status/close + grids/statuses/closed/key/tick/close_cb
class FakeActions:     # registry: dict[str, Callable]; run(name)->bool; names()->list[str]; has(name)->bool
class FakeData:        # files: dict[str, str]; read/write/remove/list（list 按前缀过滤升序）
class FakeUi:          # open_canvas(...) -> FakeCanvas，记录 key/tick/close 回调
class FakeApi:         # message()/register_command()/register_action()/ui/data/actions
                       # 以及 keymaps/highlight/sprites/lsp/syntax = None（_yate.lua 装载需要）

def lua_to_python(value) -> object        # LuaTable → dict/list 递归转换
class GameRuntime:                        # 一次加载：create_runtime(api, lib_src, module_sources())
    runtime, api, module                  # 模块名由调用方给：GameRuntime(source, name="snake")
    def press(*keys); def tick(n=1); def canvas() -> FakeCanvas
    def snapshot() -> dict                # module.snapshot() → lua_to_python
    def launch(arg="") -> FakeCanvas      # api.commands["game"](arg) 需先加载 games.lua
```

要点：

- `FakeApi.register_action` 写入 `self.actions.registry`；`FakeActions.run` 以 `None` 作为 ctx 调用。
- `FakeActions.names()` 必须返回**真的 Python list**（engine 用 `python.builtins.len`）。
- `GameRuntime` 载入 `games.lua` 时用同一 `api`，从而 `:game` 派发与各游戏 action 共享注册表。
- `GameRuntime(source=..., name=...)`：`source` 优先从 `bundled_extensions_dir()` 读真实文件
  （测试跑的是**发布源码**，不是副本）。

## 五、`tests/test_lua_engine.py` 用例清单

| 用例 | 断言 |
|---|---|
| `test_games_extension_registers_the_game_command` | 命令名 `game`、描述 `launch a bundled game` |
| `test_dispatch_reports_usage_with_the_available_games` | 空参 → 冻结文案（用 harness 注册 5 个假游戏） |
| `test_dispatch_reports_unknown_game_and_lists_available` | `chess` → `unknown game: chess (available: ...)` |
| `test_dispatch_runs_the_registered_action` | 注册 `game-snake` 后 `:game snake` 触发它 |
| `test_player_query_and_set` | `:game player` → `player: <env>`；`:game player bob` → `player: bob` 且 profile.json 写入 |
| `test_second_open_reports_already_running` | 第二次 `engine.open` 返回 nil + 文案 |
| `test_close_callback_deadens_the_session` | `close_cb()` 后 `paint` 不新增帧、可再 open |
| `test_json_encode_decode_roundtrip` | 嵌套表、数组、转义、空表→`[]`、中文 |
| `test_json_decode_reports_errors` | 坏 JSON → `nil` + 含 `json:` 的错误串 |
| `test_store_roundtrip_and_bad_json_falls_back_to_nil` | 写读一致；写入 `"not json"` 后 `load()` 为 nil |
| `test_scores_keep_the_top_five_with_players` | 6 条记录 → 5 条、降序、`player`/`at` 存在 |
| `test_frame_and_panel_pad_every_line` | 边框行宽一致、短行被补齐 |
| `test_direction_maps_arrows_hjkl_and_wasd` | 8 个键映射 + 非方向键 nil |
| `test_rng_is_deterministic_for_a_seed` | 同 seed 同序列，不同 seed 不同 |
| `test_utf8_char_returns_a_glyph_or_nil` | 有 `utf8` 时返回非空串 |
| `test_lib_dir_is_not_loaded_as_an_extension` | `loader.load_directory(bundled)` 的记录里没有 `game_engine` |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lua_engine.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe tools/lint_lua.py yate/extensions/lib/game_engine.lua yate/extensions/games.lua
```

第三条在 H 波落地前会因工具不存在而跳过；H 波落地后必须复跑。

## 七、风险

| 风险 | 缓解 |
|---|---|
| `python.builtins.len` 在个别 lupa 版本不可用 | `pcall` + 回退：拿不到名字时 `available()` 返回空串并 `yate.message` 提示，游戏仍可直接 action 启动 |
| JSON 编码空表既可能是 `[]` 也可能是 `{}` | 定案「空表 → `[]`」并在文档写明；需要空对象时用 `{__object = true}`？**不引入哨兵**，本包无空对象需求 |
| `frame` 用字节长度对多字节字形会错位 | 契约限定：边框内的行只用 ASCII；nethack 的地图行不用 `frame`（自绘边框） |
| engine 与 games.lua 同 runtime 的 `active` 隔离 | 文档写明「单实例守卫是每游戏级的」；`:game` 派发时若已有 canvas，由目标游戏的守卫拒绝 |
