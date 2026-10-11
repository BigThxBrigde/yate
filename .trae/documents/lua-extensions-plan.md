# lua-extensions-plan：扩展系统支持 Lua 脚本（issue IKKS1D）

来源：<https://gitee.com/jermaine/yate/issues/IKKS1D>（milestone：扩展系统增强）。
分支 `feat/lua-extensions`，worktree `../yate-lua-extensions`。
**批准记录**：用户已声明"无人值守，bypass 所有问题"（2026-10-11），闭环第 3 步【批准】按此放行。

## 一、需求原文与映射

1. 支持 lua 作为扩展脚本 → `ExtensionLoader` 加载 `.lua` 脚本
2. 推荐优先使用 lupa → Python-Lua 桥采用 lupa
3. 开放 extensions api，生成内置 lua api 库文件供用户导入调用 → `yate/extensions/_yate.lua`，以 `require("yate")` 导入
4. 编写简单 lua 扩展脚本存成 `lua.example` 并具详细注释 → `yate/extensions/lua.example`

## 二、目标与非目标

**目标**

- G1 `ExtensionLoader` 支持 `.lua`：与 `.py` 共用发现（目录扫描、排序、`_` 前缀跳过、
  `disabled_extensions` 排除、去重、trust 闸门）与加载（A13 回滚 scope、错误摘要、teardown）管线。
- G2 lupa 作为桥：新增可选 extra `lua = ["lupa>=2.0"]`（`dev` 同步包含）；lupa 缺失时
  加载 `.lua` 产生可操作错误信息（`pip install yate[lua]`），不影响 `.py` 扩展。
- G3 内置 Lua API 库 `yate/extensions/_yate.lua`：每个 `.lua` 扩展的独立 `LuaRuntime`
  中以 `package.preload["yate"]` + 全局 `yate` 双形态暴露（`_` 前缀保证不被自动加载）。
- G4 `yate/extensions/lua.example`：详细注释的示例（注册 `:` 命令、按键绑定、buffer 读取、
  `require("yate")` 用法）。
- G5 `--setup-defaults` 安装 `lua.example`（user_setup 模板 glob 对齐其 docstring 的
  `*.example` 口径）。
- G6 双语文档：`yate/docs/extensions.en.md` / `extensions.zh.md` 新增 Lua 章节；
  `yate/resources/manual.en.md` / `manual.zh.md` 简要段落；`yate/extensions/__init__.py`
  docstring 更新。
- G7 测试：`tests/test_lua_extensions.py` 覆盖加载/回滚/teardown/去重/缺 lupa 降级。

**非目标**

- 不改任何 Python 扩展的既有语义与 API 形态（bind_key 仅做非破坏性签名放宽，见 §四.3）。
- 不做 Lua REPL / 调试器 / 语法高亮注册（tree-sitter-lua 已随 `ts` extra 提供 `.lua` 高亮）。
- 不新增 lupa 以外依赖；不改 CHANGELOG（走发布专用提交）。
- 不支持 `.lua` 之外的新脚本后缀。

## 三、关键事实（调研取证）

- `yate/services/extensions.py` 现为 **753 行**（A11 阈值 800）→ Lua 逻辑必须独立模块，
  否则必超阈值（A11 硬规则）。
- `ExtensionLoader.load_directory` 只 `glob("*.py")`；`load_file` 要求 `setup(api)`
  callable（`yate/services/extensions.py:568`、`:610-612`）。
- A13 回滚 scope 由 loader 驱动（`start_scope` / `rollback_scope` / `end_scope`），
  `api.register_command` / `register_action` / `bind_key` 均自动记录 undo thunk。
- `ExtensionAPI.bind_key` 的 `keymap` / `description` / `category` 是 **keyword-only**
  （`*` 后参数，`extensions.py:434-442`）——Lua→Python 无法传 kwargs，需放宽为位置参数
  （非破坏：历史上第 3+ 参数不可位置传入，无存量调用可被改变行为）。
  其余 registrar（`register_command` / `register_action`）与 service 方法
  （`message` / `shell` / `open_path` / `save`）均为位置参数，Lua 可直呼。
- PyInstaller spec 以 `Tree` 整目录收集 `yate/extensions`（`pack/_common.py:165-167`）→
  `_yate.lua` 与 `lua.example` 自动随包，spec 无需改动。
- `yate/services/user_setup.py:104` 只 glob `*.py.example`，但其 docstring（`:123`）
  写的是"every bundled ``*.example`` template"——实现与文档口径不一致，本次对齐。
- 依赖现状：核心依赖仅 textual + pyperclip；tree-sitter 走可选 `ts` extra 的先例成立；
  lupa 未安装（主仓与 worktree venv 均无），CPython 3.13 + Windows 有官方 wheel
  （lupa 2.x，安装探针见步骤 0）。
- 架构红线：`services/*` 为 L0（不 import editor_view）；禁新增 Protocol / TYPE_CHECKING；
  包内绝对导入；开放 API（`ExtensionAPI` 及 bridge 公共成员）命名按
  `python-coding-style.md` §1.2（公共成员无下划线）。

## 四、备选方案与否决理由

| # | 决策点 | 选定 | 否决及理由 |
|---|---|---|---|
| 1 | Lua 代码归属 | 新模块 `yate/services/lua_extensions.py`，只依赖 lupa + paths；`ExtensionAPI` 以**具体对象**传入（不 import extensions.py，避免环；extensions.py 单向 import 它） | B: 全写进 extensions.py → 必超 800 行阈值（A11）；C: 双向顶层互引 → 循环导入 |
| 2 | lupa 依赖形态 | 可选 extra `lua`；dev 同含；缺失时 `.lua` 加载报可操作错误 | 硬依赖 → 核心安装增重一个 C 扩展；违背 `ts` extra 既有先例 |
| 3 | Lua 脚本形态 | **顶层 chunk 即 setup**（Lua 惯用法）：chunk 在 scope 保护下直接执行，可选全局 `teardown(api)` 在成功后捕获 | 强制 `setup(api)` 函数 → 反 Lua 习惯、增加样板 |
| 4 | API 库位置 | `yate/extensions/_yate.lua`（`_` 前缀=不被自动加载；spec Tree 自动随包） | B: `yate/resources/lua/` → 与扩展系统概念割裂且需新增 paths helper；C: 顶层 `yate.lua` 无前缀 → 会被 `*.lua` 扫描误当扩展加载 |
| 5 | Lua 传参方式 | `bind_key` 放宽 keyword-only → 位置参数；其余 API 全位置参数可直接调用；lupa kwargs 机制仅作探针备注，不作为依赖项 | B: 新建 `LuaApiFacade` 薄委托层 → 套娃式委托（用户明确拒绝）；C: 完全依赖 lupa `python.args`/kwargs 机制 → 行为随 lupa 版本变化，不稳 |
| 6 | 发现管线 | `load_directory` 合并 glob `*.py` + `*.lua` 后统一排序；`load_file` 按后缀分发到 Lua 分支；`LoadedExtension` / dedup / teardown_all 复用 | B: 独立 `LuaExtensionLoader` 类 → 双 loaded 列表破坏去重与 teardown 语义 |

## 五、分步实施计划

> 每步完成后按 `git-commit-message.md` 单独提交（提交纪律）；worktree 内执行。

### 步骤 0：lupa 探针（临时脚本，验证后删除）

- **输入**：worktree venv（已装 lupa）
- **动作**：写临时脚本 `tools/probes/` 外的临时文件（验证后删）验证：
  1. `import lupa` 是否携带类型信息（pyright strict 能否零诊断引用 `LuaRuntime`）；
  2. `LuaRuntime(unpack_returned_tuples=True)` 下 Python 对象属性访问 / 方法调用；
  3. Lua 函数回调 Python（含参数传递）与 `LuaError` 异常形态；
  4. LuaTable ↔ Python（`list(lua_table)` / 迭代语义）；
  5. lupa `python.args` / kwargs 机制可用性（仅记录结论，不作实现依赖）。
- **输出**：探针结论（pyright 是否需要额外处理；表转换的推荐写法）回填本计划 §七。
- **验收**：`.venv\Scripts\python.exe <probe>.py` 退出码 0，结论落盘。
- **改动文件**：无（临时脚本不入库）。

### 步骤 1：依赖声明

- **输入**：步骤 0 结论（lupa 版本下限）。
- **改动**：`pyproject.toml`——新增 `[project.optional-dependencies] lua = ["lupa>=2.0"]`；
  `dev` 列表加入 `"lupa>=2.0"`（保证 pyright / pytest 沙箱可用）。
- **输出**：`pip install -e ".[dev,lua]"` 成功。
- **验收**：`.venv\Scripts\python.exe -c "import lupa; print(lupa.__version__)"`。
- **提交**：`chore(deps): add optional lua extra with lupa`

### 步骤 2：Lua 运行时模块 `yate/services/lua_extensions.py`

- **输入**：步骤 0 探针结论。
- **改动**（新文件，预计 <200 行，遵守 python-coding-style 全部硬规则）：
  - 模块级惰性 lupa 导入探测：`is_lua_available() -> bool`（`importlib.util.find_spec`
    判存在；import 失败返回 False，不抛出）。lupa 符号获取走
    `importlib.import_module("lupa")`（探针结论 1 的落地：**动态导入天然绕开
    reportMissingTypeStubs**，配合边界处显式 `Any` 注解 + `# noqa: Any - lupa
    ships no stubs` 理由注释——`pack/_common.py` 同款先例——**全文件零
    pyright ignore**）。模块顶层不静态 import lupa——保证未装 lupa 的安装
    `import yate.services.extensions` 仍零负担。
  - `create_runtime(api: object, library_source: str) -> LuaRuntime`：每扩展一个
    `LuaRuntime`（脚本间隔离），`unpack_returned_tuples=True`；设全局 `api`
    （具体 `ExtensionAPI` 对象，lupa 包装）、以 Lua 原生 `assert(load(src, chunkname))`
    编译并执行 `_yate.lua` 库源，把返回的模块表注册为 `package.preload["yate"]`
    与全局 `yate`（探针结论 6/7）。
  - `run_extension(runtime: LuaRuntime, source: str) -> Callable[[object], None] | None`：
    执行用户 chunk（顶层即 setup），从 chunk 全局提取可调用 `teardown`（无则 None）。
    `LuaError` 直接上抛（由 extensions.py 统一记入 record.error）。
  - `lua_api_library_source() -> str`：经 `yate.paths.bundled_extensions_dir()` 读取
    `_yate.lua`（只读一次；读失败抛 RuntimeError，fail-fast 与 `load_tcss` 同风格）。
  - 参数 `api: object` 的口径：本模块**不调用**其任何方法（Lua 侧消费），
    `object` 是"不透明移交"的精确表达，非 Any 掩盖；文件头注释说明。
- **输出**：可独立测试的 lupa 桥模块。
- **验收**：`python -m pyright yate/services/lua_extensions.py` 零诊断。
- **提交**：`feat(services): add lupa-backed lua runtime bridge`

### 步骤 3：加载管线接线 `yate/services/extensions.py`

- **输入**：步骤 2 模块。
- **改动**：
  1. `load_directory`：`sorted([*directory.glob("*.py"), *directory.glob("*.lua")])`
     （统一按路径排序，`.py`/`.lua` 交错顺序确定）；`_` 前缀与 exclude 逻辑不变
     （`path.name.startswith("_")` 对两类文件同效）。
  2. `load_file`：去重检查后按后缀分发——`.lua` 走新私有方法 `_load_lua(path)`；
     `.py` 走原路径不变。
  3. `_load_lua(path) -> LoadedExtension`：镜像 Python 分支语义——
     lupa 缺失 → `record.error = "lua extensions require the lupa package; install with: pip install yate[lua]"`；
     成功路径：`start_scope()` → `create_runtime` + `run_extension`（chunk 执行即 setup，
     失败 `rollback_scope()`）→ 捕获 `teardown`；错误统一
     `record.error = f"{type(exc).__name__}: {exc}"` + `log.exception`。
  4. `bind_key` 签名放宽：`def bind_key(self, key_spec, callback=None, keymap="vsc",
     description="extension binding", category="extension")`（移除 `*`；
     docstring 注明位置传参形态供 Lua FFI 使用；Python 调用方零影响）。
  5. 模块 docstring 补一段 Lua 扩展说明（含 `require("yate")` 指引）。
- **输出**：`.lua` 扩展可被发现、加载、回滚、teardown。
- **验收**：`python -m pyright yate/services/extensions.py` 零诊断；
  既有 `pytest tests/test_extensions.py -q` 全绿（语义未变）。
- **提交**：`feat(extensions): discover and load .lua extension scripts`

### 步骤 4：内置 Lua API 库与示例

- **输入**：步骤 2/3。
- **改动**：
  1. `yate/extensions/_yate.lua`（新文件，Lua 源，详细注释）：
     - 读全局 `api`（Python `ExtensionAPI`）；
     - 返回（并被 loader 赋给全局）模块 `yate`：
       `message` / `register_command(name, fn, desc?)` /
       `register_action(name, fn, desc?)` / `bind_key(spec, fn, keymap?)` /
       `shell(cmd)` / `open_path(p)` / `save()` / `buffer()` / `doc()` / `workspace()` /
       原始桥直通 `api` / `highlight` / `sprites` / `lsp` / `syntax`；
     - 头部注释说明：每脚本独立 LuaRuntime、`require("yate")`、
       Python 对象 0 基索引等 lupa 语义要点。
  2. `yate/extensions/lua.example`（新文件，按 issue 命名；头部注明
     "复制为 `<name>.lua` 到扩展目录激活"，含完整注释的示例：
     `:lua-hello` 命令 + `<alt-h>` 绑定（vsc+vim 双键图）+ buffer 行数汇报 +
     `require("yate")` 用法演示）。
  3. `yate/extensions/__init__.py` docstring：补 `lua.example` 与 `_yate.lua` 条目。
- **输出**：随包 Lua API 库 + 可参考示例。
- **验收**：`.venv\Scripts\python.exe -c` 冒烟：构造最小 `ExtensionAPI`（同
  `tests/test_extensions.py::_extension_api` 模式）+ 加载把 `lua.example` 改名
  `hello.lua` 的临时副本 → 注册成功、命令回调可执行。
- **提交**：`feat(extensions): ship lua api library and lua.example template`

### 步骤 5：`--setup-defaults` 安装 Lua 示例

- **输入**：`yate/services/user_setup.py:92-106`。
- **改动**：`_template_sources()` 中扩展模板 glob 由 `*.py.example` 改为
  `*.example`（对齐该函数 docstring 与 `setup_defaults` docstring 的既有口径，
  `lua.example` 随之安装）。
- **输出**：`--setup-defaults` 把 `lua.example` 放进 `~/.yate/extensions/`。
- **验收**：`pytest tests/test_user_setup.py -q`（若该文件存在；以实际测试文件为准）
  + 手工 `--setup-defaults --base-dir <tmp>` 冒烟确认 lua.example 在列。
- **提交**：`fix(user_setup): install all bundled *.example templates`

### 步骤 6：测试 `tests/test_lua_extensions.py`

- **输入**：步骤 1-5 产物；`tests/test_extensions.py` 的 fixture 模式
  （`_extension_api()` 最小上下文构造，MagicMock session/keymaps 等）。
- **改动**（新测试文件，测试命名 `test_<behavior>_<condition>_<expected>`）：
  1. lupa 在场：加载合法 `.lua` → command 注册进 `CommandRegistry`（用真
     `CommandRegistry`/`ActionRegistry` 替代 MagicMock 以断言注册结果）、
     Lua 回调被 Python 调用（含 `args` 字符串参数）、`api.message` 收到 Lua 文本。
  2. 顶层 chunk 抛错（`error("boom")`）→ `record.error` 含 `LuaError`，
     scope 回滚（注册过的 command 被撤销）。
  3. `teardown` 全局 → `teardown_all()` 调用它。
  4. 同路径去重（`load_file` 两次 → 同一 record）。
  5. `load_directory` 混合 `.py`/`.lua` → 全部加载；`_` 前缀 `.lua` 跳过；
     `disabled_extensions` 对 `.lua` stem 生效。
  6. lupa 缺失降级：monkeypatch `lua_extensions.is_lua_available`（或等价注入点）
     → `record.error` 含 `pip install yate[lua]`，无异常上抛。
  7. `_yate.lua` 与 `lua.example` 资源存在性 + 库源可被 `load` 编译。
  8. `bind_key` 位置传参形态回归（放宽后 Python 位置调用等价）。
- **输出**：新增测试全绿；lupa 缺失环境测试可跳过（`pytest.importorskip` 或
  等价守卫，标注哪组是 live-lua 组）。
- **验收**：`python -m pytest tests/test_lua_extensions.py -q` 全绿。
- **提交**：`test(extensions): cover lua extension loading`

### 步骤 7：双语文档

- **输入**：最终 API 面。
- **改动**：
  1. `yate/docs/extensions.en.md` / `extensions.zh.md`：新增 "Lua extensions" /
     "Lua 扩展" 章节（双语同步为硬约束）：加载管线、`require("yate")` API 表、
     lupa 语义注意（0 基索引、Python 属性访问、每脚本独立运行时）、
     `lua.example` 安装方式、`yate[lua]` extra。
  2. `yate/resources/manual.en.md` / `manual.zh.md`：扩展章节加 Lua 简段 +
     指向 extensions 手册；`--setup-defaults` 行说明提及 lua.example（如有该表格行）。
  3. `yaterc.example`：若 `disabled_extensions` 注释处列举示例，补 lua 提示（可选，最小改动）。
- **输出**：双语手册覆盖 Lua 扩展。
- **验收**：人工核对双语同步；纯文档步骤按 misc-rules §三豁免测试。
- **提交**：`docs(extensions): document lua extension support (bilingual)`

### 步骤 8：审核与收尾（闭环 5-7）

- 派 `code-review-expert`：pyright 全仓零诊断 / `pytest tests/ -q` 全绿 /
  `tests/test_architecture.py` 28 用例 / 覆盖率 `--cov-fail-under=75` /
  冒烟（步骤 4 的临时冒烟脚本复用）。
- blocker/major → 回到方案迭代；minor → 登记待办。
- 主代理复跑全量门禁 → 回填本计划 §七（真实结果、探针结论、偏离记录）→
  `docs(plan): backfill lua-extensions execution results`。

## 六、风险清单与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| lupa 无类型信息 → pyright strict 报缺失 stub | 步骤 2 阻塞 | 步骤 0 先探针；若缺失：在 lua_extensions 内以最小包装函数收口 lupa 类型（import 面只在一处），必要时按 §4.2 极特殊场景申请评审批准的窄化 ignore 并附理由 | 独立 commit revert |
| LuaTable ↔ Python 容器转换语义偏差（如 sprites palette） | 步骤 4 API 库正确性 | 探针先行；API 库首批只暴露位置参数可直呼的面，容器转换写成显式 Lua 循环 | 库文件独立，收敛容易 |
| lupa cp313 Windows wheel 不可用 | 步骤 1 阻塞 | 安装探针已发起；若不可用 → 方案迭代（评估 lupa 版本上限或源码构建，回填计划） | — |
| `.lua` 加入 glob 影响 `--diag` / trust 提示文案 | 用户可见行为变化 | `.lua` 与 `.py` 同目录同策略，提示文案不区分后缀；既有测试护住 `.py` 路径 | 单 commit revert |
| bind_key 放宽 keyword-only 被误用 | 极低 | 位置参数语义与原 kwargs 一一对应，行为等价；测试 8 护住 | 单 commit revert |
| Lua 扩展性能（每脚本一个 LuaRuntime） | 启动延迟 | 仅在有 `.lua` 扩展时创建；数量级小（用户脚本个位数） | — |

## 七、执行记录（收尾回填）

### 步骤 0 探针结论（lupa 2.8 / Lua 5.5 / cp313 Windows wheel，2026-10-11 实测）

1. **lupa 2.8 无 `py.typed`、无 `.pyi` stubs** → pyright strict 在 import 与使用处报
   missing-stubs / unknown 诊断。处置：lupa import 与类型边界**收口在
   `lua_extensions.py` 单文件**，边界行使用带理由注释的窄化
   `# pyright: ignore[...]`（§4.2 极特殊场景：上游不发布 stub；仓库已有
   `pack/_common.py` 对 PyInstaller 的 `# noqa: Any - no type stubs` 先例），
   由闭环【审核】步骤显式批准；其余模块只见 `Callable[[object], None] | None`
   等精确类型，永不接触 lupa 符号。
2. 默认运行时为 **Lua 5.5**（非 5.4）；`LuaRuntime(unpack_returned_tuples=True)` 正常。
3. Python 对象从 Lua：属性读写、方法调用、列表元素变更（`buf.lines[1] = ...`）全部可用；
   Lua→Python 字符串为 `str`，中文/符号双向无损。
4. **LuaTable 的 Python 迭代产出 keys**（`pairs` 语义，`list({10,20,30})` → `[1,2,3]`）；
   容器转换必须显式走 `.values()` / `.items()`（`dict(tbl.items())` 可用）；
   嵌套表 `[list(row.values()) for row in tbl.values()]`。
5. `python.args` 存在，**`python.kwargs` 不存在**（lupa 2.8）→ kwargs 从 Lua 不可行，
   确认选型 5：`bind_key` 放宽为位置参数；API 库全部函数面向位置传参设计。
6. `LuaRuntime.load()` 方法不存在（2.8 移除）→ 库源编译用 Lua 原生
   `assert(load(src, chunkname))` 后调用（实测可用），返回 `_LuaTable` 模块。
7. `package.preload["yate"]` + 全局 `yate` 双暴露可用；**每 LuaRuntime 全局隔离**确认。
8. chunk 全局 `teardown` 提取为 `_LuaFunction`（callable），Python 侧带参调用正常。
9. `lupa.LuaError` 顶层可导入、可 catch（`str(exc)` 含消息 + stack traceback，
   作为 `record.error` 摘要可接受）。
10. Python 函数默认参数支持 Lua 位置子集调用（`reg('n', fn)` → 第 3 参取默认值）。
11. cp313 Windows wheel 安装顺畅（lupa 2.8），风险表中"wheel 不可用"解除。

### 实测门禁结果（2026-10-11，worktree `D:\Programming\yate-lua-extensions` venv）

- `python -m pyright yate/ tests/ tools/` → `0 errors, 0 warnings, 0 informations`，
  退出码 0；
- `python -m pytest tests/ -q` → 全绿，退出码 0（skip 均为既有平台/可选依赖标记）；
- `python -m pytest tests/test_architecture.py -q` → **29 passed**，退出码 0
  （规则文档 "28 passed" 为 2026-10-09 快照；本分支未改动
  `tests/test_architecture.py`，第 29 个用例来自基线演进）。

各步骤独立验收（pyright 对应文件零诊断 + 对应测试文件全绿）均通过后才提交，
提交链：`43c5578` → `7e19678` → `50244e1` → `929e743` → `8ebe7ee` →
`92dd3e1` → `ef38198`（docs）→ `bd59115`（test 守卫对齐）。

### 偏离记录

1. **执行期 Lua 5.5 / lupa 2.8 语义**（步骤 4 实测，实现按实测调整）：
   - `package.preload` 条目必须是**可调用 loader**（直接放模块表
     require 报 "attempt to call a table value"）→ `create_runtime` 把编译后的
     库 chunk 本身注册为 preload，再 `require("yate")` 一次；
   - Lua 5.5 `require` 返回两个值（module + stop），经
     `unpack_returned_tuples=True` 到 Python 是 tuple → 以 Lua 括号截断赋值
     `yate = (require("yate"))`；
   - 同 runtime 上 stale `teardown` 全局会泄漏 → `run_extension` 执行 chunk 前
     先 `teardown = nil`；
   - Lua 长度操作符 `#` 不支持 Python 对象（"attempt to get length of a
     POBJECT value"）→ 示例与文档改用 `python.builtins.len(list)`。
   - 探针结论 1 的旧措辞为 `# pyright: ignore[...]`；任务书定案为
     `# noqa: Any - lupa ships no stubs` + importlib 动态导入
     （动态导入天然绕开 reportMissingTypeStubs，全文件零 pyright ignore），
     实现以任务书为准。
2. **`tests/test_user_setup.py`**（步骤 5 计划外，随 `8ebe7ee` 提交）：
   `TEMPLATE_RELS` 追加 `"extensions/lua.example"`（真实资源版测试
   `test_creates_layout_from_scratch_with_real_resources` 否则失败）；
   `format_setup_report` 激活提示补 "(or *.lua)"。
3. **`tests/test_pack_spec.py`**（步骤 8 全量门禁暴露，计划外，`bd59115`）：
   - `_yate_sources()` 原以 `*.example` 通配收集并 Python `ast.parse`，其前提
     "所有 `.example` 模板都是 Python 源"被 `lua.example` 打破（SyntaxError）
     → 收集改为 Python 语义白名单（`*.py.example` + `yaterc.example` +
     `theme_examples/*.example`），docstring 说明 `lua.example` 是 Lua chunk、
     永不经 Python compile/exec，Python import 扫描不适用；
   - `_REVIEWED_DYNAMIC_IMPORTS` 登记
     `services/lua_extensions.py:importlib.import_module('lupa')`（该守卫的
     正规评审流程；理由：lupa-less 安装零导入负担 + pyright 零 stub 依赖）。
4. **文档最小一致性修正**（步骤 7，`ef38198`，超出计划字面清单）：
   manual.en/zh 的 `--ext` / `--ext-dir` 命令行表格行与 10.4 示例注释原写
   Python-only / `*.py`，与 loader 实际行为（单文件与目录均接受 `.lua`）不符，
   同步改为 `*.py`/`*.lua`，避免文档自相矛盾。

### 评审与迭代（闭环步骤 5-6，2026-10-11）

- code-review-expert 评审（范围 `135747a..bd59115` + 未提交回填）：**1 blocker +
  2 minor + 2 nit**；门禁五项实测通过（pyright 0 诊断 / pytest 全绿 /
  覆盖率 91.58% ≥ 75 / 定向 85 passed / 冒烟）。
- **blocker F1**（`090eaea` 修复）：`_yate.lua` 的 `bind_key` 包装把缺省 keymap
  以 Lua `nil` → Python `None` 原样转发，`keymaps.get(None)` 静默不绑定（与
  S34 同类）。修复为 `keymap or "vsc"` + 回归用例
  `test_lua_bind_key_two_args_defaults_to_vsc`；`register_command` /
  `register_action` 因 Python 侧 `description or ...` 兜底经实证安全。
- **minor**：test_pack_spec 白名单补完备性断言（`b0f4791`，新 `.example` 模板
  未入扫描即失败）；`LoadedExtension` docstring 净零行补 `.lua` 形态
  （`85cb918`，extensions.py 最终 **798 行** < 800）。
- **nit 登记（未改）**：lua_extensions.py 两条防御性错误路径未覆盖
  （覆盖率 91%：`find_spec` 异常分支 / `_yate.lua` 不可读 fail-fast 分支）；
  extensions.py 距 A11 阈值仅 2 行余量，下次特性改动前宜先做低成本拆分
  （如 `load_startup_extensions` 迁出姊妹模块）。
- **复测（主代理亲跑，2026-10-11）**：pyright `0 errors, 0 warnings,
  0 informations`（退出码 0）；`pytest tests/ -q` 全绿（退出码 0）；
  `pytest tests/test_architecture.py -q` 全绿（29 用例）。评审迭代后
  无 blocker / major，达到收尾标准。

---

## 十、2026-10-11 追加轮：Lua 注释英文化 + 评审修复（issue 后续，用户指令）

**任务**：① `_yate.lua` / `lua.example` 注释与示例文案英文化；② 新增规则
「代码注释与代码内注解文档一律英文」（misc-rules.md §四）；③ code-review-expert
审核结构 / 潜在 bug / 文档完整性。

**提交**：`eeb6134` docs(rules) → `3966fed` docs(extensions) 翻译 →
本轮修复提交（见下）。

**评审结论（首轮）**：0 blocker / 2 major / 1 minor，门禁全绿。

- **major-1**：lua.example 声明"任何错误不会崩溃编辑器"仅在加载期成立——
  运行期命令/按键/动作回调异常经 `editor.py:891` / `commandline.py:369` /
  `keymaps/base.py:316` 裸派发，LuaError 直透 Textual 会崩溃整个 app。
  **修复**（取评审给出的方案 a，收口在 ExtensionAPI 注册面而非改派发层）：
  `extension_api.py` 新增 `_guarded_callback(what, func)`，四个注册点
  （`register_action` / `command` 装饰器 / `register_command` / `bind_key`）
  统一包装——运行期异常按 loader 同款格式 `extension <what>: <Exc>: <msg>`
  上消息栏并 `log.exception` 留全栈；内置命令不走 ExtensionAPI，零影响。
  新增 3 个护栏用例（action / command / binding 各一）。
- **major-2**：`buf.lines[0] or ""` 空值守卫无效——lupa 2.8 实测空 Python
  list 索引抛 `IndexError` 而非返回 nil。**修复**：示例加 `if total > 0 then`
  守卫并把该语义写进注释。
- **minor**：`extension_api.py` bind_key docstring 称 Lua 库五参调用，实际
  `_yate.lua` 三参——改为 `bind_key(spec, fn, keymap)`。
- **文档同步**：`extensions.en.md` / `extensions.zh.md` 错误契约段补运行期
  回调护栏一句（双语镜像）；`_yate.lua` 头注补同款声明。

**复测（主代理亲跑，2026-10-11）**：pyright `0 errors`（退出码 0）；
`pytest tests -q` 全绿 **2129 passed, 9 skipped**（退出码 0）；
覆盖率 **91.59%** ≥ 75（退出码 0）。

**遗留登记**：评审 minor 之外无遗留；`ref/extensions-split` 轮已提前消化
"extensions.py 临阈值" nit（见 extensions-split-plan.md）。

**复评（code-review-expert，同日）**：PASS（0 blocker / 0 major / 0 minor）——
major-1/2 与 minor 均确认消除，无新问题；复测门禁全绿（覆盖率 91.62%）。
本轮新增 4 提交：`eeb6134` / `3966fed` / `9c10332` / `43d8b15`，未推送。
