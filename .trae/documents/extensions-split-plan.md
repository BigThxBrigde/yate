# extensions-split-plan：拆分 services/extensions.py（A11 预防性拆分）

来源：用户指令「基于当前分支，新建分支和 worktree，对 extensions.py 做详细的拆分计划，
并走闭环任务执行」（2026-10-11）。
基线分支 `feat/lua-extensions`（4c71f07），分支 `ref/extensions-split`，worktree `../yate-ext-split`。
**批准记录**：用户已声明"无人值守，bypass 所有问题"（2026-10-11），闭环第 3 步【批准】按此放行；
方案随执行记录回填，不再阻塞等待。

## 一、需求与动机

- `yate/services/extensions.py` 现为 **798 行**（守卫口径 `splitlines()`），距 A11 阈值
  800 仅余 2 行——Lua 扩展落地后已顶到红线。
- A11 拆分判据成立：文件含 ≥2 个互不引用的职责块（**扩展可见 API 面**：
  `ExtensionContext` / 四座 `api.*` 桥 / `ExtensionAPI`；**装载编排**：
  `LoadedExtension` / `ExtensionLoader` / `load_startup_extensions`）。
- 扩展系统是活跃开发区（issue IKKS1D Lua 扩展刚落地），继续演进必超阈值；
  本轮为预防性拆分，不改任何运行时语义。

## 二、目标与非目标

**目标**

- G1 四文件拆分：桥、API、装载各自独立模块，全部低于 A11 阈值。
- G2 插件公共导入路径 `yate.services.extensions` **冻结不变**：手册明文示例
  与 7 个 `*.py.example` 模板均 `from yate.services.extensions import ExtensionAPI`，
  原文件保留为门面（theme.py wave-d 先例），全部既有公共名 re-export。
- G3 测试适配：monkeypatch 目标与 logger 名随代码归属迁移（共 3 个测试文件 5 处）。
- G4 规则同步：`architecture-boundaries.md` §一 L3 清单与 §三.7 已出名单登记。
- G5 全量门禁零回退：pyright 0 诊断、pytest 全绿、架构测试 29 passed、
  覆盖率 ≥75%（基线 91.58%）。

**非目标**

- 不改任何运行时语义（逐字迁移代码块，仅动 docstring 自引、import 归属、logger 名）。
- 不改插件手册 / `docs/extensions.*.md` / `*.py.example`（公共导入路径不变，零影响）。
- 不做 `services/extensions/` 包化（§三.5 ② services 包根禁止 re-export，包化
  需在 `__init__.py` re-export，与规则冲突；平铺模块 + 门面与 services 现状惯例一致）。
- 不动 `services/lua_extensions.py`（依赖方向不变：loader 单向引用它）。
- 不改 CHANGELOG（走发布专用提交）。

## 三、关键事实（调研取证）

- **行块分布**（`extensions.py` 798 行）：

  | 行 | 块 | 去向 |
  |---|---|---|
  | 1-34 | 模块 docstring | 门面（精简 + 布局地图） |
  | 36-75 | imports | 按归属重分 |
  | 77-78 | `log` + 注释 | 三模块各持 `tracing.get_logger(__name__)` |
  | 82-91 | `RollbackHook` / `CommandDecorator` / `AnyCallback` | extension_api |
  | 93-94 | `TeardownHook` | extension_loader |
  | 97-119 | `ExtensionContext` | extension_api |
  | 122-167 | `LspExtensionBridge` | extension_bridges |
  | 170-203 | `HighlightExtensionBridge` | extension_bridges |
  | 206-263 | `SyntaxExtensionBridge` | extension_bridges |
  | 266-308 | `SpriteExtensionBridge` | extension_bridges |
  | 311-540 | `ExtensionAPI` | extension_api |
  | 543-555 | `LoadedExtension` | extension_loader |
  | 558-707 | `ExtensionLoader` | extension_loader |
  | 710-798 | `load_startup_extensions` | extension_loader |

- **对外引用面**（全仓 grep 取证）：生产代码 `editor.py:65`（API/Context/Loader）、
  `flows/extension_flows.py:22`（API/Loader/load_startup_extensions）、
  `editor_view/statusbar.py:25`（Loader）；插件面 `extensions/python_lsp.py:34` +
  7 个 `*.py.example`（ExtensionAPI）；`config.py:57` docstring 引
  `LspExtensionBridge`（经门面仍有效）。
- **测试耦合点**（拆分后必须适配，否则红）：
  1. `tests/test_extensions.py:285` 捕获 logger `"yate.services.extensions"`——
     bind_key 未知键图警告现由 API 模块发出 → 改 `"yate.services.extension_api"`。
  2. `tests/test_lua_extensions.py:23,214` `setattr(ext_service, "is_lua_available", ...)`
     ——调用点随 `_load_lua` 迁入 loader → 改 patch `extension_loader`。
  3. `tests/test_ts_backend.py:28,427,445,961-1024` `ext_services.SyntaxExtensionBridge`
     与 `mock.patch.object(ext_services, "load_language_from_grammar")`（:970/:993/:1007）
     ——桥迁出 → 改引 `extension_bridges`。
- **依赖方向核验**：`extension_bridges`（editor_lsp/editor_syntax/editor_sprites/stdlib）
  ← `extension_api`（keymaps/registries/session/workspace/shell + 四桥）
  ← `extension_loader`（config/paths/trust/lua_extensions + API）← 门面。
  严格单向链，无环；`lua_extensions.py` 不反向引用 extensions（既有事实）。
- **守卫面**：`tests/test_architecture.py` 无 "extensions" 路径字面量；
  `UI_FREE_PACKAGES` 以 `services/*` 包 glob 覆盖新文件（R4 自动守卫，无需登记）；
  `SIZE_EXEMPT_FILES` 无需变更（四文件均低于阈值）。
- 命名合规：`*Bridge` / `*Loader` 不在禁用后缀清单（*Feature/*Host/*Ops/*Delegate/
  *Controller）；`ExtensionLoader` / `LspExtensionBridge` 为存量名，原样保留。
- 门禁命令：覆盖率 gate 在 CI（pyproject 注释明示），本地全量命令为
  `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75`。

## 四、拆分方案（逐文件）

### 4.1 新建 `yate/services/extension_bridges.py`（约 225 行）

- docstring：四座 `api.*` 子命名空间桥（lsp / highlight / syntax / sprites），
  一句话职责 + 与 ExtensionAPI 的构造关系（API 在 `__init__` 实例化它们）。
- 逐字迁入：L122-167 / L170-203 / L206-263 / L266-308（含各自 docstring 与
  `# noqa: Any` 注记，零改动）。
- imports：`pathlib.Path`、`collections.abc.Mapping/Sequence`、`typing.Any`、
  `editor_lsp.client`（`DEFAULT_ROOT_MARKERS` / `ServerConfig`）、
  `editor_lsp.manager`（`LspManager`）、`editor_sprites.characters`（三函数）、
  `editor_syntax`（`LangSpec` / `available_filetypes` / `prefer_regex` /
  `register_language`）、`editor_syntax.ts_backend`（`load_language_from_grammar`）、
  `logs.tracing`；`log = tracing.get_logger(__name__)`。

### 4.2 新建 `yate/services/extension_api.py`（约 310 行）

- docstring：扩展脚本可见的 API 契约（`ExtensionContext` 服务集 +
  `ExtensionAPI` 门面 + A13 回滚 scope）。
- 逐字迁入：L82-91（三别名）/ L97-119 / L311-540。
- **唯一语义中性编辑**：`ExtensionAPI.rollback_scope` docstring
  "the loader (:class:`ExtensionLoader`, a sibling class in this module)" →
  指向 `:mod:`yate.services.extension_loader``（同类迁移，跨模块引用改名）。
- imports：`collections.abc.Callable`、`dataclasses.dataclass`、`pathlib.Path`、
  `typing.Any`、`editor_lsp.manager`（`LspManager`）、`keymaps.base`
  （`KeyBinding` / `Keymap`）、`keymaps.registry`（`KeymapSet`）、
  `registries`（`Action` / `CommandFunc`）、`services.shell`（`ShellResult`）、
  `services.workspace`（`Workspace`）、`session`（`EditorSession`）、`logs.tracing`、
  `services.extension_bridges`（四桥）；`log = ...`。

### 4.3 新建 `yate/services/extension_loader.py`（约 290 行）

- docstring：发现 → 装载 → A13 回滚驱动 → teardown → 启动顺序编排。
- 逐字迁入：L93-94（`TeardownHook`）/ L543-555 / L558-707 / L710-798。
- imports：`importlib.util`、`sys`、`collections.abc.Callable/Sequence`、
  `dataclasses.dataclass/field`、`pathlib.Path`、`types.ModuleType`、
  `typing.Any/cast`、`config`（`YateConfig`）、`paths`（`bundled_extensions_dir`）、
  `services.extension_api`（`ExtensionAPI`）、`services.lua_extensions`
  （四函数）、`services.trust`（`is_trusted`）、`logs.tracing`；`log = ...`。

### 4.4 重写 `yate/services/extensions.py` 为门面（约 70 行）

- docstring：保留现 1-34 行的插件契约实质（setup/teardown 约定、A13 回滚、
  Lua 管线与 `require("yate")` 指引），末尾加布局地图段
  （三实现模块各管什么；门面仅 re-export，导入路径对插件冻结）。
- re-export（显式命名导入 + `__all__`，theme.py wave-d 先例）：
  - 自 `extension_api`：`ExtensionAPI` / `ExtensionContext` /
    `RollbackHook` / `CommandDecorator` / `AnyCallback`
  - 自 `extension_bridges`：`LspExtensionBridge` / `HighlightExtensionBridge` /
    `SyntaxExtensionBridge` / `SpriteExtensionBridge`
  - 自 `extension_loader`：`ExtensionLoader` / `LoadedExtension` /
    `TeardownHook` / `load_startup_extensions`
- 门面注释一行声明：公共导入路径被手册与模板冻结，不得改动。

### 4.5 测试适配（3 文件 5 处）

1. `tests/test_extensions.py:285`：logger 名 → `"yate.services.extension_api"`。
2. `tests/test_lua_extensions.py:23`：别名导入改
   `from yate.services import extension_loader as ext_loader`；`:214` setattr 目标同步。
3. `tests/test_ts_backend.py:28`：`from yate.services import extension_bridges as ext_bridges`；
   `:427` 局部导入改 `from yate.services.extension_bridges import SyntaxExtensionBridge`；
   `:445` / `:961-1024` 类型引用与 `:970` / `:993` / `:1007` patch 目标改 `ext_bridges`。

### 4.6 规则同步（`architecture-boundaries.md`）

- §一依赖图 L3 行：`services/extensions.py` → `services/extensions.py（门面）+ services/extension_{api,bridges,loader}.py`；
  插件条目「经 L3 services/extensions.py 装载」同步措辞。
- §三.7「已出名单」追加条目（2026-10-11 extensions-split：798 行临阈值预防性拆分，
  原文件保留门面再导出冻结插件导入路径，四文件均低于阈值）。

## 五、执行波次与独占文件清单

- **Wave A**（单执行者 plan-executor，文件互不重叠，一轮完成）：
  - 源码：`yate/services/extensions.py`（重写）、`yate/services/extension_api.py`（新）、
    `yate/services/extension_bridges.py`（新）、`yate/services/extension_loader.py`（新）
  - 测试：`tests/test_extensions.py`、`tests/test_lua_extensions.py`、`tests/test_ts_backend.py`
  - 规则：`.trae/rules/architecture-boundaries.md`
  - 验收命令：§六全部（退出码 0 为准）
- **Wave B**（code-review-expert）：评审全部改动 + 独立复跑门禁。
- **Wave C**（主代理）：回填本方案 + 分步提交。

**独占文件清单**（执行者不得触碰清单外文件）：
上列 8 个工作区文件 + 本方案文档。插件模板、手册、docs、pyproject、
`lua_extensions.py`、`services/__init__.py` 均不动。

## 六、验收命令（worktree 内，全部退出码 0）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q   # 29 passed
.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75
.venv\Scripts\python.exe -c "from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader, LoadedExtension, LspExtensionBridge, HighlightExtensionBridge, SyntaxExtensionBridge, SpriteExtensionBridge, load_startup_extensions, RollbackHook, CommandDecorator, AnyCallback, TeardownHook; print('facade surface OK')"
.venv\Scripts\python.exe -c "from pathlib import Path; [print(p, len(p.read_text(encoding='utf-8').splitlines())) for p in map(Path, ['yate/services/extensions.py', 'yate/services/extension_api.py', 'yate/services/extension_bridges.py', 'yate/services/extension_loader.py'])]"
```

行数复查须四文件均 < 800；冒烟须打印 `facade surface OK`。

## 七、提交序列（git-commit-message.md）

1. `docs(plan): add extensions-split plan` —— 方案落盘（本文件）。
2. `refactor(extensions): split service into api, bridges and loader modules` —— Wave A 产物（源码 + 测试 + 规则同属一个执行步骤，一并提交）。
3. `docs(plan): backfill extensions-split execution results` —— 回填。
只提交不推送；推送须用户显式要求。

## 八、风险与缓解

- **monkeypatch 漏改** → pytest 立即红；§4.5 已枚举全部 5 处（全仓 grep 双向核验过：
  `setattr(ext_service` 单行 1 处 + `mock.patch.object(ext_services` 多行 3 处 +
  logger 捕获 1 处）。
- **循环导入** → §三已核验严格单向链；执行后 pyright + pytest 复证。
- **门面被误判"薄委托"** → 门面非委托：零逻辑、仅 re-export，存在依据是插件
  导入路径契约（模板 + 手册），先例 theme.py wave-d。
- **docstring 陈旧引用** → `config.py:57` / `lua_extensions.py` 的
  `yate.services.extensions.X` 引用经门面仍成立，不改；仅 `rollback_scope`
  自引需跨模块改名（§4.2）。

## 九、执行记录（回填区）

- Wave A：待执行。
- Wave B：待评审。
- Wave C：待收尾。
