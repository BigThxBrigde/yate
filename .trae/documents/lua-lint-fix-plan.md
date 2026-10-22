# lua-lint-fix-plan（修复 IDE Lua 诊断的全部告警）

- 基线：`master` @ `b2ac11f`（v0.2.12），分支 `fix/lua-lint`，worktree `D:/Programming/yate-lua-lint`
- 触发：用户要求「修复所有 lua lint 的报错」
- 性质：非平凡任务（6 个文件、需先调研 IDE 诊断行为），走 `task-orchestration.md` §二 闭环

## 一、现状取证（2026-10-23 实测）

IDE「Lua 诊断」共 **321 条 WARNING**（`read_lints` 实测）：

| 文件 | 条数 | 构成 |
|---|---|---|
| `lib/game_engine.lua` | 3 | `undefined-global python`（261/261/262） |
| `lib/engine_json.lua` | 1 | `need-check-nil`（292） |
| `snake.lua` | 72 | `inject-field` + `need-check-nil` + `undefined-field`（`snake` / `int`） |
| `tetris.lua` | 79 | `inject-field` + `need-check-nil` + `undefined-field`（`best`） |
| `pacman.lua` | 79 | `inject-field` + `need-check-nil` |
| `nethack.lua` | 87 | `inject-field` + `need-check-nil` + `undefined-field`（`int` / `seed` / `state`） |

根因（读源码确认，逐条对应）：

1. 四个游戏用 `local state = nil`（snake:65 / tetris:126 / pacman:120 / nethack:114）作为
   「未开局」哨兵，LuaLS 因此把 `state` 推断成 **nil 类型**：赋值侧报 `inject-field`、
   读取侧报 `need-check-nil` / `undefined-field`；
2. `snake.lua:71` 的 `rng`、`nethack.lua:117` 的 `combat` 同为 `local X = nil` 后被赋成
   `engine.rng(...)`，读取 `int` / `state` 时报 `undefined-field`；
3. `game_engine.lua:261-262` 的 `python` 是 **lupa 注入的全局**（与 `yate` / `api` 同源），
   未登记进 `.luarc.json` 的 `diagnostics.globals`；
4. `engine_json.lua:292` 的 `out[key] = value`：`parse_string()` 失败时返回 `nil, err`，
   `key` 因此是 `string?`，用可空值做下标触发 `need-check-nil`。

仓库自带门禁与本次不是同一面：`python tools/lint_lua.py` → **0 issue(s)**，退出码 0。

## 二、探针结论（决定方案的关键事实）

三条探针结论均为实测，不是推断：

1. **`.luarc.json` 被 IDE 读取并生效**：把 `diagnostics.globals` 清空后，`game_engine.lua`
   立刻多出 14 条 `undefined-global yate`；加回 `python` 后 3 条 `python` 告警**归零**
   （配置生效有约 10–15 秒延迟，读取太早会拿到旧结果）。
2. **`require("game_engine")` 在 IDE 侧不解析**：`games.lua` 探针 `engine.nosuchfield = 1`
   与 `local r = engine.rng(1); r.nosuchfield = 1`（配合 `game_engine.lua` 上的
   `---@return EngineRng` 探针）**均零诊断**；追加 `runtime.path` 指向 `lib/?.lua` 后仍零诊断。
   → **共享类型无法跨文件传播**，只能在被诊断的文件内自声明。
3. **新建文件不进诊断集**：临时 `__probe.lua` 写未定义全局也零诊断；注解只对已进入
   诊断集的既有文件生效。

## 三、目标与非目标

**目标**：6 个文件的 Lua 诊断归零，且**不新增**任何告警；运行时行为零改动
（改动全部是 Lua 注释与 `.luarc.json` 配置，不含可执行语句）。

**非目标**：

- 不重构游戏逻辑、不改 `state` 的 nil 哨兵语义；
- 不改 `tools/lint_lua.py`（仓库门禁已绿）；
- 不动 `_yate.lua` / `_yate.d.lua`（`tests/test_lua_defs.py` 的漂移守卫面）；
- 不新增随包文件。

## 四、备选方案与否决理由

| 方案 | 结论 | 理由 |
|---|---|---|
| **A**：逐文件加 EmmyLua `---@class` / `---@type` 自声明 + `.luarc.json` 登记 `python` + `---@cast` | **采纳** | 纯注释、零运行时风险，同时把 `state` 的字段面固化成可检查的类型（拼错字段名会被抓） |
| B：把 `state` 改成「永不为 nil」（声明即 `reset()`） | 否决 | `snapshot()` 在开局前返回 `{}`、`set_food_source` 的 `state ~= nil` 分支被 `tests/test_lua_game_snake.py` 等钉住；改的是运行时行为，风险与收益不成比例 |
| C：`.luarc.json` 里 `diagnostics.disable` 关掉 `need-check-nil` / `inject-field` / `undefined-field` | **采纳（用户裁决，覆盖本表原判）** | 主代理原判「否决」（等同静音、会掩盖真实字段拼写错误）；2026-10-23 用户三选一裁决改走 C，Lua 源码一律不动 |
| D：新建 `_engine.d.lua` 元文件收口共享类型 | 否决 | 探针 2 证明 require 不解析，`workspace.library` 的 meta 可见性无法自证；为 2 个文件 6 条告警新增一个随包文件不划算 |

## 五、分步实施

| 波次 | 文件 | 改动 | 验收 |
|---|---|---|---|
| W1 | `.luarc.json` | `diagnostics.globals` 补 `"python"` | 已完成且实测：3 条 `python` 告警归零 |
| W2 | `lib/engine_json.lua` | `out[key] = value` 前加 `---@cast key string` | `engine_json.lua` 诊断 1 → 0 |
| W3 | `snake.lua` | `---@class SnakeCell` / `SnakeState`（13 字段）+ `---@type SnakeState` 挂 `state`；`---@type EngineRng` 挂 `rng` | 72 → 0 |
| W4 | `tetris.lua` | `---@class TetrisState`（15 字段）+ `---@type TetrisState` 挂 `state` | 79 → 0 |
| W5 | `pacman.lua` | `---@class PacmanState`（含 pellets/pac/pending/ghosts/fright_* 等）+ `---@type PacmanState` 挂 `state` | 79 → 0 |
| W6 | `nethack.lua` | `---@class NethackState`（含 floor/px/py/monsters/items/depth/hp/max_hp/gold/weapon/turn/seed/glyphs/alive）+ `---@type NethackState` 挂 `state`；`---@type EngineRng` 挂 `combat` | 87 → 0 |

W3–W6 互不重叠文件，可并行；每波内部先声明类、再挂注解、最后跑探针。

字段清单以各文件 `reset()` / `new_game()` 的构造式加后续赋值为准（snake:136-147+153/154、
tetris:321-337、pacman:308-320+301/302/303、nethack:355-365 / 476-491 + gen_floor 赋值段）。

`EngineRng` 类在 snake 与 nethack 各声明一次（探针 2 已证无法跨文件共享）；若 IDE 报重复
类名，退化为 `SnakeRng` / `NethackRng` 两个名字，不引入第三个方案。

## 六、验证方式（偏离登记，需批准）

Lua 诊断**只在 IDE 工作区内产生**：对 worktree `D:/Programming/yate-lua-lint` 实测
`read_lints` 恒返回 0 条（同一份源文件在主工作区有 321 条）。因此本任务采用探针法验证：

```mermaid
flowchart LR
    A["worktree 改 .lua / .luarc.json"] --> B["复制到主工作区同名文件"]
    B --> C["等待 10-15 秒（配置/索引延迟）"]
    C --> D["read_lints 该文件"]
    D -->|"归零"| E["下一波"]
    D -->|"仍有告警"| F["就地调整注解后复测"]
    E --> G["收尾 git restore 主工作区，恢复干净"]
```

- 主工作区（`d:/Programming/yate`）在任务期间只做**只读用途的临时覆盖**，收尾统一
  `git restore` 还原，最终 `git status` 必须干净；
- worktree 是唯一落盘与提交点，提交只发生在 `fix/lua-lint` 分支（只提交、不推送）。

## 七、门禁（主代理亲跑，全在 worktree 内）

```powershell
Set-Location D:/Programming/yate-lua-lint
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe tools/lint_lua.py
```

外加逐文件的 Lua 诊断归零复核（read_lints 六连查）。

## 八、风险与回滚

| 风险 | 处置 |
|---|---|
| 注解挂成非 nil 后 IDE 报「永远为真/假」类新告警 | 探针复测；出现则改为 `---@type XxxState|nil` 并在读取点补显式判空（仅注释面调整，不改语义） |
| `state = { ... }` 字面量缺字段触发赋值不匹配 | 在构造式上补 `---@type XxxState`，或把后赋值字段标为可选 `---@field best? integer` |
| 行宽超过 `tools/lint_lua.py` 的 100 字符 | 注解折行；每波结束跑一次 `tools/lint_lua.py` |
| 探针复制污染主工作区 | 收尾 `git restore` + `git status --short` 必须为空（`.luarc.json` 亦还原） |

回滚：单次提交 `chore(lua): quiet nil-shaped state diagnostics in .luarc`，`git revert` 即可；
唯一产物是 `.luarc.json`，无其它文件。

## 九、执行记录（2026-10-23）

**裁决**：用户三选一改走方案 C（静音配置），A 的逐文件注解**不执行**，Lua 源码零改动。
`python` 的 3 条属 `undefined-global`、不在 C 静音的三条规则内，仍按「登记真实全局」处理
（lupa 注入，与 `yate` / `api` 同源）——这是声明，不是静音。

**唯一落盘改动** `.luarc.json`：

```json
{
  "$schema": "https://raw.githubusercontent.com/LuaLS/vscode-lua/master/setting/schema.json",
  "runtime.version": "Lua 5.4",
  "workspace.library": ["yate/extensions"],
  "workspace.checkThirdParty": false,
  "diagnostics.globals": ["api", "yate", "python"],
  "diagnostics.disable": ["need-check-nil", "inject-field", "undefined-field"]
}
```

**诊断实测（前后对比）**：`yate/extensions` 全目录 **321 → 0 条** WARNING；逐文件复核
`game_engine.lua` / `engine_json.lua` / `snake.lua` / `tetris.lua` / `pacman.lua` /
`nethack.lua` 六连查全部 0 条，无新增告警。

**门禁（worktree 内亲跑，退出码全 0）**：

| 门禁 | 结果 |
|---|---|
| `tools/lint_lua.py` | `0 issue(s)` |
| pyright strict | `0 errors, 0 warnings, 0 informations` |
| `pytest tests/ -q -n auto` | exit 0 |
| `pytest tests/test_architecture.py -q` | 36 passed |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 总覆盖 **91.95%**（≥ 75 达标） |
| `tools.smoke_test run --jobs 4` | 112/112 场景、1354/1354 检查（83.72s） |

**偏离登记**：

1. §六 的探针法如实执行（复制 `.luarc.json` 到主工作区 → 等 16 秒 → `read_lints` →
   `git restore`）；收尾后主工作区 `git status --short` 仅剩一条与本次无关的新增未跟踪项
   `.trae/.ignore`（IDE 自身产物，未删除、未提交）。
2. 方案 A 的注解工作未做；`---@class` / `---@type` 的自声明需求随之取消。

**遗留提示（未处理，需用户定夺）**：`yate/docs/extensions.{en,zh}.md` §4.14 把仓库根
`.luarc.json` 作为「用户复制到自己项目」的配方 (a) 示例。如今它带上了
`diagnostics.disable` 三条与 `python` 全局，复制者会一并继承。双语手册本次未动
（改文档需双语同步，超出本任务范围）。
