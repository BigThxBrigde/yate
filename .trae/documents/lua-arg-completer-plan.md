# Lua 扩展注册参数补全器（issue IKRZ61）

## 一、背景与现状

命令行 Tab 补全分两段：命令名补全（`flows/prompt_completion.py::_command_completions`）
与命令参数补全（注册元数据 `arg_completer`）。内置命令已有参数补全（如 `commands.py`
中的文件路径补全），扩展命令的 Python 侧 API 也已支持 `arg_completer` 关键字参数
（`yate/services/extensions/api.py::register_command` 第 4 参数，行 554-569），但
Lua 桥一层未转发该参数，导致 Lua 扩展无法接入参数补全。

**现状证据**：

- `yate/extensions/_yate.lua` 行 109-111：`yate.register_command(name, fn, description)`
  只转发 3 个位置参数到 `api.register_command(name, fn, description)`；
- `yate/extensions/_yate.d.lua` 行 33：镜像声明同样只有 3 个参数；
- `yate/services/extensions/api.py` 行 554-569：`register_command` 已支持第 4 参数
  `arg_completer: ArgCompleter | None = None`；
- `yate/extensions/games.lua` 行 26：`yate.register_command("game", engine.dispatch, ...)`
  只传 3 参；
- `yate/extensions/lib/game_engine.lua` 行 252-275：`engine.games()` 已返回排序后的
  游戏名 Lua 表（来自已注册 `game-*` action）；行 283-305：`engine.dispatch(args)` 支持
  `:game <name>` / `:game player [name]` 两种子命令；
- `yate/services/extensions/api.py` 行 362-379：`_guarded_completer` 已实现异常隔离
  （completer 抛错 → log.exception + 返回 []），Lua completer 抛 `LuaError` 同样被捕获。

**能力缺口**：仅在 Lua 桥一层（`_yate.lua` / `_yate.d.lua`），以及 Lua 表 → Python
list[str] 的返回值适配（`_guarded_completer` 内）。

## 二、目标与非目标

### 目标

1. `yate.register_command(name, fn, description, completer)` 第 4 参数接受 Lua 回调函数，
   经桥接转发为 Python `arg_completer`（与 `fn` 同路，复用既有 Lua→Python callable 转发）；
2. Lua completer 返回 Lua 表（1-based）时，Python 侧收敛为 `list[str]`（与内置补全语义一致：
   返回相对 `rest` 的延伸值）；
3. `:game` + Tab 列出游戏名候选（候选来自 `engine.games()` 结果 + `"player"` 子命令词，
   按前缀过滤后排序输出）；
4. Lua completer 抛错 → 静默降级为 `[]` + tracing 日志（issue 验收标准 2，由既有
   `_guarded_completer` 免费满足）；
5. 扩展手册双语（`yate/docs/extensions.en.md` / `extensions.zh.md`）补 `completer` 参数
   说明与一个简短 Lua 示例。

### 非目标

- 不改命令名补全唯一匹配静默套用行为（`flows/prompt_completion.py` 不动）；
- 不新增 `:games` 并列命令（只在 `:game` 上挂 completer）；
- Python 扩展 API 的 `arg_completer` 语义不变（`api.py::register_command` 签名不动，
  只在 `_guarded_completer` 内做返回值收敛）。

## 三、备选方案与否决理由

### 方案 A（采纳）：在 `_guarded_completer` 内做 Lua 表 → list[str] 收敛

- **改动点**：`api.py::_guarded_completer` 的 `guarded` 内层函数，在 `completer(prefix)`
  返回后做 duck-type 收敛（Python list 原样通过；lupa 表按 1-based 索引取元素 str() 化；
  None/其它 → []）；
- **否决理由**：无。这是最小改动点，复用既有异常隔离，不引入新模块，不触碰 `lupa`
  （`api.py` 不 import `lupa`，duck-type 用 `hasattr(obj, "keys") and callable(obj.keys)`
  判定 Lua 表）；
- **Any 使用**：`_guarded_completer` 的 `guarded` 返回值收敛需要 `Any`（lupa 表无静态类型），
  附 reason 注释（`api.py` 已有 `AnyCallback = Callable[..., Any]` 先例，行 68）。

### 方案 B（否决）：在 Lua 侧 `_yate.lua` 做表 → Python list 转换

- **改动点**：`_yate.lua::register_command` 内用 `python.eval` 或 `python.builtins.list`
  把 Lua 表转为 Python list 再传给 `api.register_command`；
- **否决理由**：Lua 侧无法简洁地构造 Python list（需 `python.eval("[]")` 再逐个 append），
  且把"Lua 表 → Python list"的适配逻辑散落在每个扩展的 completer 里，违背"桥层统一收敛"
  原则；Python 侧收敛只需一处，Lua 侧零感知。

### 方案 C（否决）：新增 `api.register_command_with_completer` 独立方法

- **否决理由**：`api.py::register_command` 已支持 `arg_completer` 关键字参数，新增独立方法
  会造成 API 膨胀；Lua 不能传 kwargs，但位置参数第 4 参已够用（`description` 与 `completer`
  都是可选，留 nil 即得 Python 侧默认值）。

## 四、分步实施

### 步骤 1：Python 侧返回值收敛（`api.py::_guarded_completer`）

**输入**：`_guarded_completer` 当前实现（行 362-379）。

**改动文件**：`yate/services/extensions/api.py`

**具体修改**：

1. 行 372-377 的 `guarded` 内层函数，在 `completer(prefix)` 返回后做收敛：

   ```python
   def guarded(prefix: str) -> list[str]:
       try:
           raw = completer(prefix)
       except Exception:  # noqa: BLE001 - user code, never crash the app
           log.exception("extension command %s arg_completer raised", name)
           return []
       return _coerce_completer_result(raw)
   ```

2. 新增模块级辅助函数 `_coerce_completer_result`（放在 `_guarded_completer` 之前，
   约行 360 附近）：

   ```python
   def _coerce_completer_result(raw: object) -> list[str]:
       """Coerce an arg_completer return value to list[str].

       Python list passes through; a Lua table (duck-typed as a non-list
       object with a callable ``keys`` method) is walked by 1-based index
       up to ``len``; non-string elements are skipped (no ``tostring``
       coercion -- ``"table: 0x..."`` would pollute candidates); anything
       else (None, str, number) degrades to ``[]``.
       """
       if raw is None:
           return []
       if isinstance(raw, list):
           return [s for s in raw if isinstance(s, str)]
       # Lua table via lupa: duck-typed by callable .keys() + __len__.
       if hasattr(raw, "keys") and callable(getattr(raw, "keys", None)):
           length_fn = getattr(raw, "__len__", None)
           if callable(length_fn):
               try:
                   length = int(length_fn())
               except (TypeError, ValueError):
                   return []
           else:
               return []
           out: list[str] = []
           for index in range(1, length + 1):
               try:
                   value = raw[index]
               except (KeyError, IndexError):
                   break
               if isinstance(value, str):
                   out.append(value)
           return out
       return []
   ```

3. 函数 docstring 与模块 docstring 不触碰（保持既有）；新函数附 `Any` 注释：
   `raw: object`（不用 `Any`，因为 `object` 更精确——completer 返回值可能是任何类型）。

**输出**：`_guarded_completer` 对 Lua 表返回值自动收敛为 `list[str]`。

**验收命令**：

```bash
python -m pytest tests/test_lua_extensions.py -q -n auto
python -m pyright yate/services/extensions/api.py
```

**通过判定**：既有测试全绿 + pyright 零诊断。

---

### 步骤 2：Lua 桥转发第 4 参数（`_yate.lua` + `_yate.d.lua`）

**输入**：`_yate.lua` 行 109-111，`_yate.d.lua` 行 33。

**改动文件**：

- `yate/extensions/_yate.lua`
- `yate/extensions/_yate.d.lua`

**具体修改**：

1. `_yate.lua` 行 101-111：

   ```lua
   -- Register a ``:`` command.  fn receives the raw argument string after
   -- the command name (may be empty).  Commands appear in the command
   -- palette (Alt+Shift+P) and the :help list, with Tab completion.
   -- description is optional (default "extension command"); completer is
   -- an optional Lua callback receiving the raw argument prefix and
   -- returning a table of candidate strings (1-based; non-string elements
   -- are skipped).
   ---@param name string
   ---@param fn fun(args: string)
   ---@param description string|nil
   ---@param completer fun(prefix: string): string[]|nil
   ---@return nil
   function yate.register_command(name, fn, description, completer)
     api.register_command(name, fn, description, completer)
   end
   ```

2. `_yate.d.lua` 行 26-33：

   ```lua
   -- Register a ``:`` command.  fn receives the raw argument string after
   -- the command name (may be empty).  description is optional
   -- (default "extension command"); completer is an optional Lua callback
   -- returning candidate strings for Tab completion.
   ---@param name string
   ---@param fn fun(args: string)
   ---@param description string|nil
   ---@param completer fun(prefix: string): string[]|nil
   ---@return nil
   function yate.register_command(name, fn, description, completer) end
   ```

3. `_yate.lua` 头部导出清单行 67：

   ```lua
     register_command(name, fn, desc?, completer?)  register a ``:`` command
   ```

**输出**：Lua 扩展可传第 4 参 completer，经桥接转发为 Python `arg_completer`。

**验收命令**：

```bash
python -m pytest tests/test_lua_defs.py -q
```

**通过判定**：`test_lua_defs.py` 的 `LUA_SURFACE` 锁步测试不受影响（函数名未变，
只改签名注解），全绿。

---

### 步骤 3：game_engine 提供 completer（`game_engine.lua`）

**输入**：`game_engine.lua` 行 252-275（`engine.games()`），行 283-305（`engine.dispatch`）。

**改动文件**：`yate/extensions/lib/game_engine.lua`

**具体修改**：

在 `engine.dispatch` 之后（约行 306）新增 `engine.completer`：

```lua
-- The ":game" arg_completer: candidate game names + the "player"
-- subcommand, filtered by prefix and sorted.
function engine.completer(prefix)
  local raw = engine.trim(prefix or "")
  local candidates = {}
  -- Subcommand "player" completes when the prefix matches.
  if "player":sub(1, #raw) == "player" or raw == "" then
    candidates[#candidates + 1] = "player"
  end
  -- Registered game names from engine.games() (already sorted).
  local games = engine.games()
  for _, name in ipairs(games) do
    if raw == "" or name:sub(1, #raw) == name:sub(1, #raw) then
      -- Filter: the game name must start with the prefix.
      if name:sub(1, #raw) == raw then
        candidates[#candidates + 1] = name
      end
    end
  end
  table.sort(candidates)
  return candidates
end
```

**简化版**（上面有冗余判断，修正为）：

```lua
-- The ":game" arg_completer: candidate game names + the "player"
-- subcommand, filtered by prefix and sorted.
function engine.completer(prefix)
  local raw = engine.trim(prefix or "")
  local candidates = {}
  -- Subcommand "player" completes when the prefix is empty or matches.
  if raw == "" or "player":sub(1, #raw) == raw then
    candidates[#candidates + 1] = "player"
  end
  -- Registered game names from engine.games() (already sorted).
  for _, name in ipairs(engine.games()) do
    if raw == "" or name:sub(1, #raw) == raw then
      candidates[#candidates + 1] = name
    end
  end
  table.sort(candidates)
  return candidates
end
```

**输出**：`engine.completer(prefix)` 返回 Lua 表（1-based），含 `"player"` + 匹配的游戏名。

**验收命令**：

```bash
python -m pytest tests/test_lua_engine.py -q -n auto
```

**通过判定**：既有 dispatch 测试全绿（新增函数不影响既有行为）。

---

### 步骤 4：games.lua 注册时挂 completer

**输入**：`games.lua` 行 26。

**改动文件**：`yate/extensions/games.lua`

**具体修改**：

行 26：

```lua
yate.register_command("game", engine.dispatch, "launch a bundled game", engine.completer)
```

**输出**：`:game` 命令注册时挂接 `engine.completer` 作为参数补全器。

**验收命令**：

```bash
python -m pytest tests/test_lua_engine.py -q -n auto
```

**通过判定**：既有测试全绿。

---

### 步骤 5：测试——桥接层（`tests/test_lua_extensions.py`）

**输入**：`_ApiBundle` fixture（行 77-115），`requires_lupa` 标记（行 32-34）。

**改动文件**：`tests/test_lua_extensions.py`

**新增测试用例**（4 条，覆盖正常流 + 边界 + 异常 + 未提供 completer）：

1. `test_lua_completer_returns_table_coerced_to_list`：

   - **前置**：`_ApiBundle` + `requires_lupa`；
   - **Lua 脚本**：`yate.register_command('lua-cmd', function() end, 'desc', function(prefix) return {prefix .. 'a', prefix .. 'b'} end)`；
   - **操作**：加载脚本 → 取 `bundle.commands.get('lua-cmd').arg_completer` → 调用 `('test')`；
   - **断言**：返回 `['testa', 'testb']`（Python list[str]）。

2. `test_lua_completer_returns_nil_coerced_to_empty`：

   - **Lua 脚本**：completer 返回 `nil`；
   - **断言**：`arg_completer('any')` 返回 `[]`。

3. `test_lua_completer_raises_degrades_to_empty`：

   - **Lua 脚本**：completer 内 `error('boom')`；
   - **断言**：`arg_completer('any')` 返回 `[]`（不抛错）。

4. `test_lua_completer_absent_means_no_completion`：

   - **Lua 脚本**：`yate.register_command('lua-no-comp', function() end, 'desc')`（3 参，无 completer）；
   - **断言**：`bundle.commands.get('lua-no-comp').arg_completer` 为 `None`。

**验收命令**：

```bash
python -m pytest tests/test_lua_extensions.py -q -n auto -k "completer"
```

**通过判定**：4 条新用例全绿（无 lupa 时跳过）。

---

### 步骤 6：测试——端到端（`tests/test_lua_engine.py`）

**输入**：`_dispatcher()` fixture（行 44-54），`_with_games()` fixture（行 57-）。

**改动文件**：`tests/test_lua_engine.py`

**新增测试用例**（2 条）：

1. `test_game_completer_lists_registered_games`：

   - **前置**：`_dispatcher()` + `_with_games(api)`（注册 4 个 game-* action）；
   - **操作**：取 `:game` 命令的 `arg_completer` → 调用 `('')`；
   - **断言**：返回包含 `'player'` + `('nethack', 'pacman', 'snake', 'tetris')` 的排序列表。

2. `test_game_completer_filters_by_prefix`：

   - **前置**：同上；
   - **操作**：`arg_completer('sn')`；
   - **断言**：返回 `['snake']`（`'player'` 不匹配前缀 `'sn'`，被过滤）。

**验收命令**：

```bash
python -m pytest tests/test_lua_engine.py -q -n auto -k "completer"
```

**通过判定**：2 条新用例全绿（无 lupa 时跳过）。

---

### 步骤 7：扩展手册双语更新

**输入**：`yate/docs/extensions.en.md` 行 984（`register_command` 速查表行），
行 190（命令注册示例代码块）；`extensions.zh.md` 行 900 / 168 镜像位置。

**改动文件**：

- `yate/docs/extensions.en.md`
- `yate/docs/extensions.zh.md`

**具体修改**：

1. **速查表行**（en 行 984，zh 行 900）：

   - 原文：`| yate.register_command(name, fn, desc?) | register a : command; fn receives the raw argument string |`
   - 改为：`| yate.register_command(name, fn, desc?, completer?) | register a : command; fn receives the raw argument string; completer(prefix) returns candidate strings for Tab |`

2. **命令注册示例代码块**（en 行 187-193，zh 行 165-171）：

   在既有 `api.register_command("name", func, "description")` 之后追加一段 completer 示例：

   ```lua
   -- with Tab completion
   api.register_command("name", func, "description", function(prefix)
     return {"candidate1", "candidate2"}
   end)
   ```

3. **完整示例小节**（en 行 951-956，zh 行 869-874）：

   在既有 `yate.register_command("lua-hello", ...)` 示例之后追加一段注释说明 completer 用法。

**输出**：手册文档补全 completer 参数说明。

**验收命令**：

```bash
python -m pytest tests/ -q -n auto --collect-only 2>&1 | grep -i "no errors"
```

**通过判定**：文档为 Markdown，无自动化测试；手工检查格式正确、双语一致。

---

## 五、测试清单（汇总）

| # | 测试文件 | 用例名 | 验证目标 |
|---|---|---|---|
| 1 | `tests/test_lua_extensions.py` | `test_lua_completer_returns_table_coerced_to_list` | Lua 表 → Python list[str] 收敛 |
| 2 | `tests/test_lua_extensions.py` | `test_lua_completer_returns_nil_coerced_to_empty` | nil → [] 容错 |
| 3 | `tests/test_lua_extensions.py` | `test_lua_completer_raises_degrades_to_empty` | 抛错 → [] + tracing 日志 |
| 4 | `tests/test_lua_extensions.py` | `test_lua_completer_absent_means_no_completion` | 未提供 completer → arg_completer 为 None |
| 5 | `tests/test_lua_engine.py` | `test_game_completer_lists_registered_games` | :game 端到端补全候选 |
| 6 | `tests/test_lua_engine.py` | `test_game_completer_filters_by_prefix` | 前缀过滤 |

**回归范围**：

```bash
python -m pytest tests/test_lua_extensions.py tests/test_lua_engine.py tests/test_lua_defs.py -q -n auto
python -m pyright yate/ tests/ tools/
python -m pytest tests/test_architecture.py -q
```

**通过判定**：全绿 + pyright 零诊断 + 架构守护无违规。

## 六、文档清单

| 文件 | 改动 |
|---|---|
| `yate/docs/extensions.en.md` | 速查表行 + 示例代码块补 completer 参数 |
| `yate/docs/extensions.zh.md` | 镜像英文改动 |

CHANGELOG 由 `python -m tools.changelog` 从 commit 自动生成，不手动编辑。

## 七、风险与回滚

### 风险

1. **lupa 表 duck-type 误判**：若用户 Python 扩展的 completer 返回自定义对象（有 `keys` 方法），
   可能被误判为 Lua 表。缓解：先 `isinstance(raw, list)` 排除 Python list，再 duck-type；
   自定义对象极罕见（`ArgCompleter` 签名明确返回 `list[str]`）。
2. **Lua 表 `__len__` 不可用**：lupa 旧版本可能不暴露 `__len__`。缓解：`callable(length_fn)`
   判定，不可用则返回 `[]`（不抛错）。
3. **`engine.completer` 前缀过滤逻辑错误**：空前缀时应返回全部候选，非空前缀时按 `name:sub(1, #raw) == raw` 过滤。缓解：步骤 6 的端到端测试覆盖空/非空前缀。

### 回滚路径

本任务改动相互独立，回滚按文件粒度：

1. `api.py::_coerce_completer_result` + `_guarded_completer` 改动 → git revert 单文件；
2. `_yate.lua` / `_yate.d.lua` 签名改动 → git revert；
3. `game_engine.lua` / `games.lua` → git revert；
4. 测试 / 文档 → git revert。

既有的 `_guarded_completer` 异常隔离逻辑不变，回滚后 Lua 扩展仍可正常注册命令
（只是没有参数补全）。

## 八、执行波次

本任务为中等体量，不拆分子计划目录，但按依赖关系分两波执行：

**Wave 1（基础层，可并行）**：

- 步骤 1（`api.py` 返回值收敛）
- 步骤 2（`_yate.lua` / `_yate.d.lua` Lua 桥转发）

**Wave 2（依赖 Wave 1，可并行）**：

- 步骤 3（`game_engine.lua` completer）
- 步骤 4（`games.lua` 挂 completer）
- 步骤 5（桥接层测试）
- 步骤 6（端到端测试）
- 步骤 7（文档）

**Wave 3（收尾）**：

- 全量回归（pyright + pytest + 架构守护）

## 九、架构边界触碰标注

本任务触碰的架构边界条款：

- **R4**（UI-free）：`api.py` 在 L0 `services/*`，不 import `editor_view`（维持）；
- **R12**（日志）：`_guarded_completer` 已用模块级 `log`（tracing），新增 `_coerce_completer_result`
  不引入新日志调用（维持）；
- **R14**（扩展机件子包化）：`api.py` 在 `services/extensions/` 包内，改动不触碰门面冻结
  （维持）。

无需新增 `tests/test_architecture.py` 守卫用例（本任务不引入新架构边界）。

## 十、评审记录

### 评审轮 1（python-code-review，code-review-expert 执行）

针对分支上 5 笔提交（8cfe8bf..b746729）的评审发现与处置：

| 编号 | 级别 | 位置 | 发现 | 处置 |
|---|---|---|---|---|
| M1 | major | `yate/services/extensions/api.py` 的 `guarded` 内层函数（`_guarded_completer` 内） | `_coerce_completer_result(raw)` 在 try 块之外调用；该函数自身可抛 TypeError（Python 侧 completer 返回带 keys + 整型 `__len__` 但 `__getitem__` 抛 TypeError 的对象时异常逃逸），违背包装器 docstring "a raise degrades to none" 的契约 | 已修复：收敛调用挪进 try 块，异常统一记日志并返回 `[]` |
| m1 | minor | `yate/services/extensions/api.py` 的 `_coerce_completer_result` 防御分支 | 覆盖率缺失行 107、110-111、114、118、122-123、127 零覆盖 | 已修复：补纯函数单元测试（见下），全部缺失行消除 |
| s1 | suggestion | `api.py` duck-type 判定行 | `hasattr(raw, "keys") and callable(getattr(raw, "keys", None))` 的 hasattr 冗余 | 已清理：只留 getattr + callable 判定，行为不变 |
| s2 | suggestion | `_coerce_completer_result` | dict 会被 duck-type 分支收出整型键值 | 不处置：输入违反 ArgCompleter 契约、不崩溃，计划风险 1 已登记同类误判 |

m1 补充的测试（`tests/test_lua_extensions.py`，普通测试、不依赖 lupa，以 duck-type 桩类
模拟 Lua 表）：`test_coerce_completer_list_passthrough_filters_non_strings`（list 直通 +
非字符串过滤）、`test_coerce_completer_none_degrades_to_empty`（None → `[]`）、
`test_coerce_completer_duck_typed_table_walked_in_order`（1-based 顺序收出）、
`test_coerce_completer_malformed_tables_degrade_to_empty`（参数化：`__len__` 抛
TypeError / 返回非 int / 不可调用、无 `__getitem__`、纯 str/number 兜底）、
`test_coerce_completer_stops_walk_at_missing_index`（`__getitem__` 抛 KeyError 中途
break、保留已收出项）、`test_guarded_completer_swallows_coercion_type_error`
（M1 回归：收敛期 TypeError 经 guarded 包装器降级为 `[]`，不再逃逸）。

### 评审轮 1 门禁实测数字（评审时点）

- `python -m pyright yate/ tests/ tools/`：0 errors / 0 warnings；
- `pytest tests/ -q -n auto`：全绿（1 skip 为存量平台标记）；
- 架构测试：37 passed；
- 覆盖率：92.75%；
- 冒烟：121/121 场景、1463 checks；
- lupa 2.8 已装，completer 相关 6 测试 LIVE passed、0 skipped。

### 评审修复轮实测数字（本轮）

验收命令（venv 解释器）实测：

- `pytest tests/test_lua_extensions.py -q -n auto`：49 passed，退出码 0；
- `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`：退出码 0，
  总覆盖率 92.82%；`yate/services/extensions/api.py` 行覆盖 97%，m1 清单缺失行
  （107、110-111、114、118、122-123、127）全部消除，仅剩 `124->119` 部分分支标记
  （非缺失行）与 469/527/554/563/622/626/630 等与本轮无关的存量缺失行；
- `pyright yate/ tests/ tools/`：0 errors, 0 warnings, 0 informations，退出码 0。

### 收尾全量门禁（主代理亲测，空闲环境）

- `python -m pyright yate/ tests/ tools/`：0 errors / 0 warnings / 0 informations，退出码 0；
- `pytest tests/ -q -n auto`：全绿，退出码 0（首轮与冒烟/覆盖率并行时
  `test_pack_wiki_parallel.py::test_interrupt_leaves_the_queued_batches_untranslated`
  墙钟断言被负载膨胀击穿（1.79s 对 1.6s 上限，xdist 工作进程实测膨胀约 3.5x）；
  按「时序 flake 必须修用例」纪律，把该断言余量从 8 倍放宽到 15 倍并注释负载依据，
  修复后单文件 `-n 4` 与全量 `-n auto` 空闲复跑均全绿）；
- `pytest tests/test_architecture.py -q`：37 passed，退出码 0；
- `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`：总覆盖率 92.88%，
  退出码 0；
- `python -m tools.smoke_test run --jobs 4`：121/121 场景、1463/1463 checks，退出码 0
  （首轮与 pytest/覆盖率并行时 `vim_registers_text_objects` 的 `ciw_back_to_normal`
  单项失败（期望 NORMAL 实得 INSERT）；单场景复跑定位为并行门禁 CPU 争抢导致的
  时序 flake（空闲 0.97s 对负载 4.1s），master 对照通过、空闲复跑通过、空闲全量
  复跑 1463/1463 全过，非本分支代码回归）。

### 评审轮 2（pr-review 终审，code-review-expert 执行）

针对修复后全分支（8cfe8bf..65aedf2）的 PR 级预审结论：**APPROVE，0 blocker**。

- 四维结论：功能 PASS（coercion 对 None/list/Lua 表/畸形形状四路降级完备，M1 回归测试在场）、
  安全 PASS、性能 PASS、可维护性 PASS；
- 门禁实测：pyright 0 errors / 0 warnings / 0 informations；pytest 全量全绿；
  架构测试全绿；
- 唯一 minor（非阻塞，登记待办）：`tests/test_lua_extensions.py` 头部的文件级
  `# pyright: reportPrivateUsage=false` 覆盖面偏宽（理由注释在场，规则字面不禁止）；
  建议后续窄化为逐处 ignore 或在编码风格规则中登记该惯例，不阻塞本分支合并。
