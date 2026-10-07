# Callable 别名化方案（issue IKJUWP）

> 来源 issue：<https://gitee.com/jermaine/yate/issues/IKJUWP> —
> "ENHANCE - 使用 TYPE 定义适当的 CALLABLE 别名"，诉求三条：可读性更好、语义更容易理解、符合 PEP 规范。
>
> 分支 `ref/callable-aliases`，worktree `../yate-callable-aliases`（独立 `.venv` 已重建并自证指向本worktree）。

## 一、目标与非目标

### 目标

1. 把`yate/` 中语义明确的回调形态收敛为**具名 `type` 别名**（PEP 695），消灭裸写
   `Callable[...]` 的噪声，重点是**跨模块复用**与**位置不可自解释**两类；
2. 存量 8 个普通赋值别名（`ClosedHook` / `CommandFunc` / `ActionFunc` / `PromptCompleter` /
   `OutputFn` / `ExitFn` / `ConnectFn` / `NotificationFn`）统一改为 `type` 语句
   （`python-coding-style.md` §3.5 已规定"类型别名用 `type` 语句"）；
3. 新增架构守护用例：模块级 / 类级的 `Callable[...]` 赋值别名一律禁止（必须 `type`），
   并禁`typing.TypeAlias` / `TypeAliasType`，防回归；
4. pyright strict 零诊断 + 全量 pytest 全绿，覆盖率不低于现有水平。

### 非目标

- **不**引入 `Protocol`、**不**建中央接口 / 公共类型层（`architecture-boundaries.md` R2、§三.1）；
- **不**改动任何运行时行为（本方案是纯类型注解重构，字节码语义不变）；
- **不**统一"所有"回调形态：一次性、参数名已自解释的形态（`open_path: Callable[[Path], None]`）
  保持内联，理由见§三；
- **不**改测试里的通用局部可调用标注（`_wait_for(predicate: Callable[[], bool])`、桩对象
  `Callable[..., None]`），仅在能直接复用产品别名时替换。

## 二、调研事实（每条带 `文件:行号`）

| # | 事实 | 取证 |
|---|---|---|
| F1 | 全仓 `Callable[...]` 共 **166 行 / 47 个文件**（`yate/` 33、`tests/` 12、`tools/` 2），清单见 `_callable_inventory.txt`（临时产物，收尾删除） | 探针 `rglob("*.py")` 扫描 `yate/ tests/ tools/` |
| F2 | 已有 11 处别名，其中 8 处是**普通赋值**（违反 §3.5），3 处已用 `type`（`yaterc.py` 的 `ThemeRegistrar` / `ThemeDirLoader`、`editor_term/emulator.py` 的 `RGB`、`editor_sprites/render.py` 的 `Frame` / `Palette`） | `yate/session.py:37`、`yate/registries.py:25`、`yate/keymaps/base.py:182`、`yate/editor_view/commandline.py:31`、`yate/editor_term/pty_proc.py:26-27`、`yate/editor_lsp/client.py:36-37`、`yate/yaterc.py:119,124` |
| F3 | `ActionFunc = Callable[["ActionContext"], None]` 用字符串前引号（因定义在 `ActionContext` 之前）；`type` 语句惰性求值后可去掉引号 | `yate/keymaps/base.py:182` vs `:217` |
| F4 | 形态 `Callable[[], None] | None`（主题退订钩子）横跨 **7 个** `editor_view` 模块 | `chrome.py:102,219,240`、`commandline.py:234`、`diffview.py:251`、`editor.py:137`、`explorer.py:42`、`statusbar.py:79`、`terminal.py:417` |
| F5 | 这 7 个模块**已经** `from . import theme`，因此从 `theme` 取别名不新增任何依赖边 | grep `^(from\|import).*theme`：`terminal/statusbar/scrollbars/explorer/palette/modals/editor/diffview/commandline/chrome/completion` |
| F6 | 形态 `Callable[[str, str], None]`（`message(severity, text)`）横跨 **7 个** flows 模块 | `flows/window_flows.py:51`、`shell_flows.py:38`、`prompt_flows.py:27`、`overlay_flows.py:47`、`lsp_sync.py:40`、`document_flows.py:56`、`extension_flows.py:40` |
| F7 | 形态 `Callable[..., Worker[object]]`（注入的 `App.run_worker`）横跨 5 个 flows 模块；`Callable[[Screen[Any]], None]`（`push_overlay`）横跨 3 个 | `flows/*.py:45/34/50/34/45`、`flows/shell_flows.py:42`、`lsp_sync.py:42`、`overlay_flows.py:38-40` |
| F8 | `yate/flows/__init__.py` 目前只有 docstring、无导入、无再导出，并显式声明"保持惰性" | `yate/flows/__init__.py:1-9` |
| F9 | `flows/*` 的 `editor_view` 导入已冻结在 `UI_FROZEN_FILES`（键为 `flows/<name>.py`），**新增** `editor_view` 导入需先登记 | `tests/test_architecture.py:115-166` |
| F10 | `yate/editor_view/terminal.py` 已依赖 `yate.editor_term` 包根（可再向下import `pty_proc`），方向合法 | `yate/editor_view/terminal.py:24-31` |
| F11 | 命名守卫禁用的后缀为 `Feature/Host/Ops/Delegate/Controller`，白名单 `PaneHost`；`*Manager` 允许 | `tests/test_architecture.py:178-179` |
| F12 | `flows/*` 与 `services/*` 可向下import `keymaps.base`（`overlay_flows.py` 已import `yate.keymaps.registry.KeymapSet`；`keymaps/base.py` 不import `editor_view`） | `flows/window_flows.py:24`、`architecture-boundaries.md` R4 守卫面 |
| F13 | `editor_term/pty_proc.py` 另有普通赋值别名 `ExitState = int \| Literal[...]`（同属 §3.5 违规，一并迁移） | `yate/editor_term/pty_proc.py:32` |
| F14 | 覆盖率门禁在 CI 命令行（`--cov-fail-under=75`），`addopts` 不含 `--cov`，本地须显式复现 | `pyproject.toml:114-153` |

## 三、决策规则：何时引入别名

| 规则 | 内容 |
|---|---|
| **R-A** | **跨模块复用**（同一形态出现在 ≥2 个模块）→ 必须具名，别名落在**拥有该概念的模块**，消费者沿合法依赖方向import |
| **R-B** | **位置不可自解释**（多参数、参数含义靠文档而非名字，如 `Callable[[str, str], None]` 的 severity/text、`Callable[..., Worker[object]]`）→ 必须具名 |
| **R-C** | 一次性且参数名已自解释（`open_path: Callable[[Path], None]`、`make_view: Callable[[int], EditorView]`、`save: Callable[[], None]`）→ 保持内联。**理由**：跨层共享这些形态需要一个 L0 "公共类型层"，而那正是 `architecture-boundaries.md` §三.1 明令废止的 `interfaces.py` / `app_features/*` 模式 |
| **R-D** | 形态相同但**语义不同**（如主题 listener 与退订钩子都是 `Callable[[], None]`）→ 各命名、各定义，不强行合并 |
| **R-E** | 别名一律 PEP 695 `type` 语句 + `#:` 注释说明契约（`python-coding-style.md` §2.5、§3.5） |
| **R-F** | 命名不得触命名守卫（F11）：禁 `*Feature/*Host/*Ops/*Delegate/*Controller/AppProtocol`；回调别名统一 `*Fn`（动词性能力）或 `*Query`（状态查询） |

## 四、别名总表（唯一规范来源）

> 本表已按 §9.3 的偏离记录修订为**最终落地状态**：`SetApplyHook`、`DiffKeyHandler`、
> `Clock` 三个别名按 R-C 回退为内联，`editor_view/terminal.py` 一行不成立已移除。

### 4.1 flows 域：`yate/flows/__init__.py`（域内共享词汇表，不新建 types 模块）

| 别名 | 定义 | 消费点 |
|---|---|---|
| `MessageFn` | `Callable[[str, str], None]` | 7 个 flows 模块的 `message` / `report` |
| `SpawnFn` | `Callable[..., Worker[object]]` | 5 个 flows 模块的 `spawn` |
| `OverlayPusher` | `Callable[[Screen[Any]], None]` | `shell_flows` / `lsp_sync` / `overlay_flows` 的 `push_overlay` |
| `StateQuery` | `Callable[[], bool]` | `mounted` / `has_modal_screen` / `explorer_focused`（13 处） |

同步改`yate/flows/__init__.py` docstring：别名是本包注入式能力的词汇表，仍不做子模块再导出
（§三.5①保持成立，因为本模块不 import 任何子模块）。

`execute_action: Callable[[str], bool]` 复用 `keymaps.base` 的 `ActionRunner`（F12），不在 flows 里另立同名。

### 4.2 L1 / L0 拥有者

| 别名 | 定义（`type` 语句） | 拥有者模块 | 现状 |
|---|---|---|---|
| `ActionFunc` | `Callable[[ActionContext], None]` | `keymaps/base.py` | 普通赋值 + 字符串前引号（F3） |
| `ActionRunner` | `Callable[[str], bool]` | `keymaps/base.py` | 新增（`KeyUi.execute_action`） |
| `CommandFunc` | `Callable[[str], object]` | `registries.py` | 普通赋值（F2） |
| `ClosedHook` | `Callable[[list[Document]], None]` | `session.py` | 普通赋值（F2） |
| `OutputFn` / `ExitFn` | `Callable[[bytes], None]` / `Callable[[int \| None], None]` | `editor_term/pty_proc.py` | 普通赋值（F2） |
| `ExitState` | `int \| Literal["running", "failed"]` | `editor_term/pty_proc.py` | 普通赋值（F13） |
| `ResponseFn` | `Callable[[bytes], None]` | `editor_term/emulator.py` | 新增（`on_response`，PTY 响应字节） |
| `ConnectFn` / `NotificationFn` | 见 `editor_lsp/client.py:36-37` | `editor_lsp/client.py` | 普通赋值（F2） |
| `ClientFactory` | `Callable[[ServerConfig, Path], LspClient]` | `editor_lsp/manager.py` | 新增（2 处，R-B） |
| `RootQuery` | `Callable[[], Path \| None]` | `editor_lsp/manager.py` | 新增（工作区根查询） |
| `EventHook` | `Callable[[str], None]` | `editor_lsp/manager.py` | 新增（`on_event`） |
| `OptionParser` | `Callable[[str], object \| None]` | `config.py` | 新增（`:215` `SetOptionSpec.parse`） |
| `Clock` | `Callable[[], float]` | `services/idle_tracker.py` | 新增（可注入时钟）→ **已回退内联**（R-C，见 §9.3） |
| `RollbackHook` | `Callable[[], None]` | `services/extensions.py` | 新增（`ExtensionLoader._scope`） |
| `CommandDecorator` | `Callable[[CommandFunc], CommandFunc]` | `services/extensions.py` | 新增（`ExtensionAPI.command` 返回） |
| `AnyCallback` | `Callable[..., Any]` | `services/extensions.py` | 新增（`register_action` / `bind_key`） |
| `TeardownHook` | `Callable[[ExtensionAPI], None]` | `services/extensions.py` | 新增（2 处） |
| `ExcepthookFn` | `Callable[..., Any]` | `logs.py` | 新增（3 处） |
| `EventDeliverer` | `Callable[[Message], None]` | `keyproto/driver_windows.py` | 新增（`cast` 目标） |
| ~~`SetApplyHook`~~ | ~~`Callable[[Editor, object], None]`~~ | ~~`commands.py`~~ | **已回退内联**（表项元素类型，R-C，见 §9.3） |
| `SectionFn` | `Callable[[], list[str]]` | `diagnostics.py` | 新增（`sections` 表项） |

### 4.3 L2 `editor_view`

| 别名 | 定义 | 拥有者 | 消费点 |
|---|---|---|---|
| `ThemeListener` | `Callable[[], None]` | `editor_view/theme.py` | `_listeners` / `subscribe` / `attach` |
| `Unsubscribe` | `Callable[[], None]` | `editor_view/theme.py` | 7 个组件的 `_theme_unsubscribe`（F4，R-D：与 `ThemeListener` 同形异义） |
| `PromptCompleter` | `Callable[[str, str], list[str]]` | `editor_view/commandline.py` | 普通赋值改 `type`（F2） |
| ~~`DiffKeyHandler`~~ | ~~`Callable[[DiffPane], None]`~~ | ~~`editor_view/diffview.py`~~ | **已回退内联**（键表元素类型，R-C，见 §9.3） |
| `OutputFn` / `ExitFn` | 复用 `editor_term.pty_proc`（F10 方向合法） | — | 消费侧：`tests/test_terminal.py`、`tests/test_app_terminal.py`、`tools/smoke_test/scenarios/integration.py`（`editor_view/terminal.py` 无可别名化注解，见 §9.3 偏离 4） |

### 4.4 测试 / 工具（只复用，不新增别名定义）

- `tests/test_set_options.py:40` → 复用 `config.OptionParser`（假 spec 与真 spec 同形）；
- `tests/test_key_notation.py:433` → 复用 `keymaps.base.ActionFunc`；
- `tests/test_terminal.py:430-446`、`tests/test_app_terminal.py:84-90,158-159`、
  `tools/smoke_test/scenarios/integration.py:40-47` → 复用 `pty_proc.OutputFn` / `ExitFn`。

### 4.5 新增架构守护用例

`tests/test_architecture.py::test_callable_aliases_use_type_statements`（AST）：

1. 扫描 `yate/**/*.py`，模块级与类级 `Assign` / `AnnAssign` 的**值**里出现 `Callable[...]`
   下标 → 违规（必须写成 `type X = ...`，即 `ast.TypeAlias`节点）；
2. 扫描 `yate/` 内 `from typing import ... TypeAlias / TypeAliasType` → 违规；
3. 负向演练：临时回填一处普通赋值别名确认拦截，再还原。

同步更新：`tests/test_architecture.py` 模块 docstring + `architecture-boundaries.md` §六
（24 → **25** 个用例，含对照表新增一行）、`python-coding-style.md` §3.5（补"Callable 别名用 `type`"）。

## 五、备选方案与否决理由

| 方案 | 结论 | 理由 |
|---|---|---|
| **A. 新建 `yate/callbacks.py` 之类全局别名模块** | **否决** | 直接复刻 `architecture-boundaries.md` §三.1 废止的"公共类型层 / `interfaces.py`"；把跨层的 `Callable[[], None]` 提到 L0 会让 L0 反向承载 UI 语义（`focus_editor` / `refresh` / `readonly_notice`）。违反 R-C |
| **B. 全部 166 处内联 `Callable` 一律具名（含测试）** | **否决** | 一次性、参数名自解释的形态别名化后信息量不增反减（`save: Save`），且把测试 diff 放大到与行为无关的噪声 |
| **C. 每个 flows 模块各自定义 `MessageFn`** | **否决** | 7 份同名同义定义，读者无法判断是否同一契约，改一处漏六处 |
| **D. 新建 `yate/flows/callbacks.py`** | **否决** | 等价于在域内重建 types 模块；域内词汇表放包根`__init__.py` 已足够（且它不 import 任何子模块，惰性不受影响，F8） |
| **E. 只迁移存量 8 个别名，不加新别名、不加守护** | **否决** | 存量迁移只完成 issue 的1/3；跨模块高频形态（F4-F7）才是可读性收益主体，且无守护则必然回归 |
| **F. 用 `Callable` 的 `Protocol` 化替代** | **否决** | R2 冻结 `Protocol` 白名单，且回调本就是结构化类型，`Callable` 足够 |

## 六、实施波次（文件互不重叠；每波结束跑一次 pyright）

> **执行方式说明**：`subagent-workflow.md` §一.3 明令"子代理不得修改产品源码（`yate/`）"，
> 本方案 95% 改动落在 `yate/`，因此**代码实施由主代理亲自执行**；子代理只用于只读探索与
> §六.4 的独立审核（`code-review-expert`）。此为规则冲突时的显式取舍，非跳过并行纪律。

### Wave 0 — 定义（纯新增别名，无调用点改动；12 个文件）

`yate/flows/__init__.py`（4别名 + docstring）、`yate/editor_view/theme.py`（2）、
`yate/keymaps/base.py`（2）、`yate/registries.py`、`yate/session.py`、
`yate/editor_term/pty_proc.py`（3）、`yate/editor_lsp/client.py`（2）、
`yate/editor_lsp/manager.py`（3）、`yate/config.py`、`yate/commands.py`、`yate/diagnostics.py`、
`yate/logs.py`、`yate/services/idle_tracker.py`、`yate/services/extensions.py`（4）、
`yate/keyproto/driver_windows.py`、`yate/editor_term/emulator.py`

- 输入：§四 别名总表；输出：全部别名可被 import。
- 验收：`.venv\Scripts\python.exe -m pyright yate/` 零诊断；
  `.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_keymaps.py -q` 通过。

### Wave 1 — `yate/` 调用点改写（20 个文件）

- flows 7 子模块：`Callable[[str, str], None]`→`MessageFn`、`Callable[..., Worker[object]]`→`SpawnFn`、
  `Callable[[Screen[Any]], None]`→`OverlayPusher`、`Callable[[], bool]`→`StateQuery`、
  `Callable[[str], bool]`→`ActionRunner`（自 `keymaps.base` 导入）；
- `editor_view` 7 组件：`_theme_unsubscribe: Unsubscribe | None`（自 `theme` 导入）；
- `editor_view/terminal.py`：`on_output: OutputFn` / `on_exit: ExitFn`；
- `editor_view/diffview.py`：3 张键表→`DiffKeyHandler`；
- `editor_view/commandline.py`：`PromptCompleter`消费点保持（定义已改）；
- `pty_proc.py` / `emulator.py` / `manager.py` / `extensions.py` / `commands.py` /
  `diagnostics.py` / `logs.py` / `idle_tracker.py` / `driver_windows.py` 内部消费点。

- 验收：`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` 零诊断；
  `.venv\Scripts\python.exe -m pytest tests/ -q` 全绿。

### Wave 2 — 测试 / 工具复用 + 新守护（6 个文件）

`tests/test_architecture.py`（新用例 + docstring）、`tests/test_set_options.py`、
`tests/test_key_notation.py`、`tests/test_terminal.py`、`tests/test_app_terminal.py`、
`tools/smoke_test/scenarios/integration.py`

- 验收：`.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` →
  **25 passed**；全量 `pytest tests/ -q` 全绿。

### Wave 3 — 审核 / 门禁 / 文档回填

- `code-review-expert` 子代理独立评审（结论只认实测）；
- 主代理亲自跑：pyright 零诊断、`pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75`、
  `tests/test_architecture.py` 25 passed、冒烟 `tools/smoke_test`；
- 回填本文档第六节实测数字与偏离记录，删除临时产物 `_probe_callable.py` / `_callable_inventory.txt`；
- 同步 `.trae/rules/architecture-boundaries.md`（§六 25 用例 + 对照表）与
  `.trae/rules/python-coding-style.md`（§3.5 补Callable 别名条款）。

## 七、风险与回滚

| 风险 | 概率 | 缓解 | 回滚 |
|---|---|---|---|
| `type` 别名在 `cast("X", ...)` 字符串位置不被解析 | 低 | `keyproto/driver_windows.py` 保持字符串形式并由 pyright 实测 | 单文件 `git checkout` |
| 包根新增别名破坏 §三.5①"包根惰性" | 中（人工评审点） | `flows/__init__.py` 不 import 任何子模块；docstring 显式声明该边界 | 撤回 Wave 0 该文件 |
| 改动面过大漏改某处 | 中 | 新守护用例 + 全量 pytest + pyright 三重兜底 | 整分支 `git reset --hard 8724bd5` |
| flows 新增 `keymaps.base` 导入成环 | 低 | `keymaps/base.py` 只依赖 `session`，无反向边；pyright/pytest 立即暴露 | 撤回该 import |
| 覆盖率因重构掉行（不可能，纯注解） | 无 | — | — |

回滚路径：分支未推送，`git reset --hard 8724bd5` 或按波次 `git checkout -- <files>`。

## 八、架构影响自检（`architecture-boundaries.md` §五）

- 无新增 `Protocol` / `TYPE_CHECKING` / `Any`（`AnyCallback` / `ExcepthookFn` 沿用既有
  `Callable[..., Any]` 处的 `Any`，语义未变，且原代码已有 `noqa` 语义注释处保持）；
- 依赖方向全部向下或同级：flows→keymaps（L3→L1）、editor_view→editor_term（L2→L0）、
  editor_view→editor_view 同级；**未新增** `editor_view` 导入到 flows，故 `UI_FROZEN_FILES`
  无需变更（F9）；
- `Editor` / flows 均不持有新的 App 句柄，能力注入形态不变（`spawn=app.run_worker` 等原样）；
- R9/R10/R12/R13 不涉及；R2 不新增协议。

## 九、执行结果与偏离记录（2026-10-07 回填）

### 9.1 门禁实测（主代理亲自跑，worktree 内`.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 | `0 errors, 0 warnings, 0 informations` |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75` | 0 | 覆盖率 **91.44%**（13441 stmts / 929 miss，4438 branch / 429 miss），门禁 75 通过 |
| `python -m pytest tests/test_architecture.py -q` | 0 | **25 passed** |
| `python -m tools.smoke_test run --tag integration --no-color` | 0 | **6/6 scenarios，57/57 checks**，3.14s |

改动文件覆盖率：`yate/flows/__init__.py` 100%、`yate/config.py` 97%、`yate/logs.py` 94%、
`yate/services/extensions.py` 91%、`yate/editor_lsp/manager.py` 85%、`yate/editor_view/theme.py` 84%。

### 9.2 审核与修复（`code-review-expert` 子代理，只读评审 + 实测）

评审结论"不可按现状合并"，6 MAJOR / 6 MINOR / 2 NIT，逐条处理如下：

| 编号 | 问题 | 处理 |
|---|---|---|
| MAJOR-1 | `MessageFn` 注释把参数写反（实为 `message(text, kind)`，kind 取 `info/error/warn/ok`） | 已按 `yate/editor.py:498` 与 `commandline.py:53` `MESSAGE_COLORS` 订正 |
| MAJOR-2 | `PromptCompleter` 新旧注释叠加且第二参数写成 `prefix` | 删除旧行，按 `self.bar.completer(current, mode)` 改回 `mode` |
| MAJOR-3 | `ConnectFn` 注释把进程写成 `protocol`（`protocol` 是同文件无关兄弟模块） | 订正为 `(reader, writer, process)` |
| MAJOR-4 | `EventHook` 编造 `started/stopped/failed` 事件 | 按 `_fire()` 实测改为 `state` / `diagnostics` |
| MAJOR-5 | 守护判定范围超出自身文档（误报数据表），并逼出两个不该存在的别名 | 判定收窄为"顶层就是 `Callable[...]`"；回退 `SetApplyHook`、`DiffKeyHandler`（见 9.3 偏离 2） |
| MAJOR-6 | `architecture-boundaries.md` §六仍写 24 个用例 | 已改 25 + 对照表补第 25 行 + §六新增「回调别名」条目 |
| MINOR-1 | 方案未回填实测与偏离 | 本节 |
| MINOR-2 | 规则改动未随代码提交 | 已并入本次提交 |
| MINOR-3 | 删除 `# noqa: Any` 后未在 `Screen[Any]` 新家补理由 | `OverlayPusher` 行补 `# noqa: Any - any Textual Screen` |
| MINOR-4 | `OptionParser` 注释写"拼写无效"（拼写早在 `SET_OPTION_INDEX` 解析完） | 改为"值无效" |
| MINOR-5 | 守护漏报：`if`/`try` 内绑定、字符串前引号、`typing.Callable` | 递归进 `if`/`while`/`try`，新增限定名与字符串注解判定 |
| MINOR-6 | `flows/__init__.py` 包根新增两个 textual 导入 | docstring 显式声明该事实与理由 |
| NIT-1 | `Clock` 仅 1 处消费、参数名已自解释 | 按 R-C 回退内联 |
| NIT-2 | `ClientFactory` 注释"可注入"话术 | 改为指向 `set_client_factory` 的事实描述 |

守护用例负向演练（临时探针文件，已删除）：**6 类违规全部拦截**（普通赋值、带注解赋值、
`typing.Callable`、字符串前引号、模块级 `if` 内、类体），**3 类放行形态零误伤**
（数据表 `dict[str, Callable[...]]`、裸声明 `Field: Callable[...]`、函数体内实例属性）。

### 9.3 偏离记录

1. **波次合并执行**：Wave 0/1 按文件合并（同一文件的"别名定义 + 消费点"一次改完），
   波次门禁（每波 pyright）不变；理由：跨波次拆同一文件会让文件在两波之间处于
   "已定义未使用"的中间态，且把编辑轮次翻倍。
2. **三个别名按 R-C 回退为内联**：`commands.SetApplyHook`（全仓 1 处消费）、
   `editor_view.diffview.DiffKeyHandler`（键表元素类型，表名已自解释）、
   `services.idle_tracker.Clock`（参数名即 `clock`）。最终新增 **19** 个别名、
   迁移 **9** 个存量普通赋值别名（`ClosedHook` / `CommandFunc` / `ActionFunc` /
   `PromptCompleter` / `OutputFn` / `ExitFn` / `ConnectFn` / `NotificationFn` /
   `ExitState`），`yate/` 内 `type X =` 共 **33** 处（改动前 5 处）。
3. **计划外的消费点**：`yate/editor_view/palette.py` 新增
   `from yate.keymaps.base import ActionRunner`（§四 清单未列），与
   `flows/overlay_flows.py` 同为 `execute_action` 复用点。
4. **§4.3 一行不成立**：原计划"`editor_view/terminal.py` 复用 `OutputFn`/`ExitFn`"
   不存在可别名化的注解——该处 `on_output` / `on_exit` 是具体方法
   （`terminal.py:166,177`），已从表中移除；改为由 `tests/test_terminal.py`、
   `tests/test_app_terminal.py`、`tools/smoke_test/scenarios/integration.py`
   三个消费侧复用。
5. **theme 别名采用限定形式**：7 个组件已 `from . import theme`，故写作
   `theme.Unsubscribe` 而非再插一行 `from .theme import Unsubscribe`，
   避免同一模块出现两条指向 `theme` 的导入。

### 9.4 执行方式说明（对齐 `subagent-workflow.md`）

本任务 38 个改动文件全部落在 `yate/`（产品源码），而 `subagent-workflow.md` §一.3
规定子代理不得修改产品源码，故**代码实施由主代理亲自执行**；子代理仅用于
Wave 3 的只读独立评审（`code-review-expert`，1 名成员，全程 139 次工具调用，
产出实测门禁数据并给出 14 条问题，全部处置见 9.2）。这是规则冲突时的显式取舍，
未跳过审核环节。

## 十、存量冒烟失败修复（2026-10-07 追加）

审核阶段暴露的全量冒烟唯一失败项已定位并修复。完整根因、证据链与举一反三见评审记录
[reviews/2026-10-07-smoke-set-options-matrix.md](../reviews/2026-10-07-smoke-set-options-matrix.md)。

- **现象**：`set_options_matrix / keymap_warned` 恒失败——全量冒烟 101/102 scenarios、
  1235/1236 checks；单场景复跑同样失败（排除 timing 类偶发）。
- **根因**：断言钉死字面量 `"unknown keymap"`，而 `8b529d4`（表驱动 `:set`，A8/A9）已把该提示语
  收进选项表 `SET_OPTION_SPECS["keymap"].invalid_message`（`"keymap must be vsc or vim"`）。
  `yate/editor.py:750` 的 `unknown keymap: <name> (vsc|vim)` 属于 `:keymap <名字>` 命令路径，
  与 `:set` 本就是两条路径、两种文案。基线 JSON（`smoke_baselines/set_options_matrix.json`）
  只作对照、不参与判定，其中 `ok: true` 的历史记录长期掩盖了该失败。
- **修复**：`tools/smoke_test/scenarios/view.py` 的断言改为从
  `SET_OPTION_INDEX["keymap"].invalid_message` 取文案，即**跟随选项表**而非钉死字符串；
  **产品源码零改动**（`yate/` 未触碰一个字节）。基线文件无需改动：label 与 expected 未变。
- **实测（主代理亲自跑）**：单场景 `--scenario set_options_matrix` **16/16 checks**；
  全量冒烟 `--skip-slow` **102/102 scenarios、1236/1236 checks**、exit 0（修复前 101/102）；
  `pyright yate/ tests/ tools/` 0 errors；全量 pytest + 覆盖率门禁见 §十一。
- **登记**：评审记录已入 `.trae/reviews/README.md` 速览 #37 与轮次总表。