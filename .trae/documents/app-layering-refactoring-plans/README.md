# 分层重构计划：外壳 / 调度 / 组件 / 会话

> 状态：**Plan A–G 全部完成**（Plan A–F 于 2026-09-22 落地 · 2026-09-23 审计与迁移收口；
> Plan G 窗格模型下沉于 2026-09-23 落地），见 §5 索引与 §10 审计记录。
> 目标：项目结构清晰、层次划分清晰、扩展性与维护性好；改动性质以**代码搬运 + 删除**为主，
> 不重写算法；**能用函数实现的就不造类**。
> 本目录是本次重构的**唯一计划来源**；代码侧的硬性边界同时固化在
> [`.trae/rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md)，
> 由 `tests/test_architecture.py` 守护。
> 2026-09-23 的逐条审计结果与处置见 §10。

---

## 1. 事实基线（2026-09-22 实测 / 2026-09-23 复核）

> **行数口径：非空行**。`wc -l` 或编辑器显示的总行数会多算空行
> （例：`app.py` 总 172 / 非空 152；`editor.py` 总 1388 / 非空 1245）。

| 指标 | 值 |
|---|---|
| `yate/app.py` | **152 行**（重构前 2005 行） |
| `yate/editor.py` | 1274 行（`Editor`：唯一允许的编排大类） |
| `yate/session.py` | 281 行（`EditorSession` 161 行 + 窗格树模型 120 行，无 UI） |
| `yate/registries.py` / `actions.py` / `commands.py` | 60 / 111 / 207 行 |
| `yate/completion.py` / `prompt_completion.py` | 280 / 126 行 |
| 已删除 | `yate/app_features/`（6 文件 / 1070 行）、`app.py` 内 1875 行业务代码（均为历史值）、`yate/editor_view/pane_types.py`（155 行，Plan G 下沉至 `session.py`） |
| `AppProtocol` / `yate.interfaces` | 定义 **0 处**（字面量仅存于 `tests/test_architecture.py` 的禁用名守卫） |
| 新增模块 | `session.py`、`registries.py`、`editor.py`、`actions.py`、`commands.py`、`completion.py`、`prompt_completion.py`、`editor_view/chrome.py`、`keymaps/registry.py` |
| 门禁现状 | `python -m pyright yate/ tests/ tools/` → **0 errors, 0 warnings, 0 informations**；`pytest tests/` **全绿**；`tools.smoke_test run --fail-only` → **86/86 场景、889/889 checks**（2026-09-23 **Plan G 收口**实测；§1.1 是 Plan E 时点的旧值，场景/checks 数此后随新增场景增长） |

### 1.1 迁移与门禁收口（2026-09-23 实测）

| 范围 | 结果 |
|---|---|
| E1 `tests/test_app_textual.py` | ✅ **137 passed**（旧属性路径 ≈250 处全部迁移） |
| E2 `test_explorer.py` / `test_changelog_view.py` / `test_diagnostics.py` | ✅ **26 passed**（收集期中断消除） |
| E3 `test_cli` / `test_config` / `test_panes` / `test_editor_core` / `test_extensions` / `test_highlight` | ✅ **175 passed** |
| E4 `tools/smoke_test/scenarios/`（8 个未迁移场景） | ✅ 全量 `run --fail-only` → **62/62 场景、651/651 checks** |
| 全量门禁 | ✅ `pytest tests/ -q` exit 0 · `pyright yate/ tests/ tools/` 0 诊断 · `yate --diag` / `--version` 正常 |
| 迁移记录 | 逐文件方式见 [Plan E](plan_E_tests_tools.md) §E.5 / §E.6.4；属性映射见 §E.1 |

### 1.2 复核命令

```powershell
# 行数（非空行口径）
python -c "import pathlib; [print(n, 'total=', len(t), 'nonblank=', sum(1 for l in t if l.strip())) for n,t in ((n,(pathlib.Path('yate')/n).read_text(encoding='utf-8').splitlines()) for n in ['app.py','editor.py','session.py','registries.py','actions.py','commands.py','completion.py','prompt_completion.py'])]"
# 门禁
python -m pytest tests -q
python -m pyright yate/ tests/ tools/
python -m tools.smoke_test run --fail-only
```

---

## 2. 目标分层（唯一权威定义）

```
L4 外壳   yate/app.py            YateApp     Textual 壳：CSS / 主题桥 / 生命周期 / 事件转发 / 装载内置表
L3 调度   yate/editor.py         Editor      会话 + 服务 + 组件的编排层："编辑器操作"的唯一落点
L3 表     yate/actions.py        populate(registry, editor)
          yate/commands.py       register_commands(registry, editor)      内置表（纯函数，无类）
L3 流程   yate/completion.py     CompletionController                     会话级流程（补全）
          yate/prompt_completion.py  prompt_completions(...)              无状态候选生成（允许 import editor_view.theme，R11）
          yate/diagnostics.py    format_report(editor) / print_report(editor)  函数式报告
L2 组件   yate/editor_view/*     TabBar / Breadcrumbs / PromptBar / ExplorerTree /
                                 TerminalPanel / PaneHost / StatusBar / CompletionPopup /
                                 HelpScreen / OutputScreen / PaletteScreen / MarkdownDocScreen / EditorView
L1 会话   yate/session.py        EditorSession + 窗格树模型（Leaf / Split / ViewState / 树操作）
           └ 模块内容             文档 / 标签 / 搜索 + 无 UI 的窗口布局模型（无 UI、无 LSP）
L1 模型   yate/registries.py     ActionRegistry / CommandRegistry（叶子容器）
          yate/keymaps/registry.py  KeymapSet（键映射集合 + 活动项）
L0 叶子   editor_core / editor_lsp / editor_syntax / editor_term / services / config / logs / paths /
          keymaps/base|vim|vsc（`keymaps/registry.py` 属 L1，键映射集合本身无 UI 但被各层共享）
```

**一句话职责划分**

| 层 | 干什么 | 不干什么 |
|---|---|---|
| `YateApp`（外壳） | 调 `Editor`；持有 Textual 生命周期、主题桥、CSS、内置表装载 | 不实现任何业务操作 |
| `Editor`（调度） | 组合模型/服务/组件，实现"操作"（打开、保存、窗格、键分发、提示、主题、shell、LSP、覆盖层、扩展） | 不做渲染、不做文本编辑算法、不写补全候选算法 |
| 表 / 流程模块 | 把"内置能力"登记到注册表；把可独立成段的流程挪出 `Editor` | 不反向被 `editor.py` 导入（防环） |
| Widget（组件） | 自持自己的行为与渲染，构造注入具体协作者或回调 | 不 import `yate.editor` / `yate.app` |
| `EditorSession` | 文档集合、标签、搜索状态、关闭通知 | 不碰 UI、不碰 LSP |
| 窗格模型（同 `session.py`，L1） | 窗格树 / 每文档视口状态（`Leaf` / `Split` / `ViewState` + 树纯函数），被 L2/L3 直接 import | 不碰 UI；窗口布局仍由 L2 `PaneManager` 持有、L3 `Editor` 组装 |
| 叶子 | 纯逻辑 | 不 import 上层 |

`yate/editor_view/` 模块清单：`chrome.py`（TabBar / Breadcrumbs / `sidebar_head_text()`）、`commandline.py`（PromptBar / CommandInput）、
`explorer.py`（ExplorerTree）、`completion.py`（CompletionPopup）、`editor.py`（EditorView + 唯一保留的
`PaneRegistry` Protocol）、`panes.py`（PaneManager / PaneHost）、
`statusbar.py`（StatusBar + `mode_chip()`）、`terminal.py`（TerminalView / TerminalPanel）、
`modals.py`（Help 与输出覆盖层）、`palette.py`（文件/命令面板）、`manual.py`（手册屏幕）、
`theme.py`（主题与单元格宽度工具）、`icons.py` / `keys.py`。

---

## 3. 统一命名（硬性）

| 类别 | 命名 | 例 |
|---|---|---|
| 会话模型 | `<Noun>Session` / 无 UI 模型 | `EditorSession`、`KeymapSet` |
| 调度层 | `Editor`（唯一） | `Editor` |
| 外壳 | `YateApp`（唯一） | `YateApp` |
| 组件 | 形态后缀：`*View` `*Panel` `*Bar` `*Tree` `*Screen` `*Popup` | `EditorView`、`TerminalPanel`、`PromptBar`、`ExplorerTree`、`HelpScreen`、`CompletionPopup` |
| 表模块 | 动词函数 | `populate()`、`register_commands()`、`load_startup_extensions()` |
| 流程 / 纯函数模块 | 名词流程 or 动宾函数 | `CompletionController`、`prompt_completions()`、`format_report()`、`mode_chip()` |
| 回调记录 | `*Ui` 具体记录（非协议） | `KeyUi` |
| 操作前缀 | `open_` `close_` `save_` `refresh_` `apply_` `toggle_` `focus_` `show_` `push_` | `open_path()`、`refresh_ui()` |
| **禁用后缀** | `*Feature`、`*Host`、`*Ops`、`*Delegate`、`*Protocol`；`*Manager` 仅存量、`*Controller` 仅流程 | `app_features/` 已整体删除 |
| **命名白名单**（架构测试不视为违规） | `PaneHost`（Textual 容器 widget）、`PaneManager` / `LspManager`（存量）、`CompletionController`（流程类） | 见 §4「冻结清单」与 `tests/test_architecture.py` |

---

## 4. 依赖规则（硬性，架构测试守护）

- **R1** `yate/` 内除 `cli.py` 外不得 import `yate.app`。
- **R2** 不得新增 `Protocol`；仅保留 4 个**存量冻结**协议类（见下"冻结清单"）。
- **R3** `editor_view/*` 不得 import `yate.editor` / `yate.app`（组件向上只收回调/具体对象）。
- **R4** `keymaps/*`、`services/*`、`session.py`、`registries.py` 不得 import `editor_view`。
- **R5** `actions.py` / `commands.py` 可以 import `yate.editor`；**反向禁止**（`editor.py` 不得 import 它们，否则成环）。
- **R6** 不使用 `TYPE_CHECKING`。
- **R7** 内置表由**外壳装载**：`YateApp.__init__` 调 `populate(editor.actions, editor)` 与
  `register_commands(editor.commands, editor)`。
- **R8**（新增，Plan E 起生效）跨层共享状态只用**具体对象**：`EditorSession`、`KeymapSet`、
  `ActionRegistry`、`CommandRegistry` —— 不再为每个消费者造一个窄协议。
- **R9** 组件 id 归调度层：`Editor` 构造 widget 时带上 id（`#sidebar` `#sidebar-head` `#explorer`
  `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar`），`compose()` 里再带上
  容器 id（`#body` `#bottom-dock` `#bottom`）。其中 `#statusbar` 只是 widget id（CSS 用类选择器
  `StatusBar`），其余 id 均被 `app.py` 的 CSS 直接引用 —— 改 id 必须同步改 CSS。
- **R10** 一次按键只派发一次：`EditorView.on_key` 处理后 `stop()` / `prevent_default()`，未消费的键不再冒泡。
- **R11**（新增，Plan E 落地）`completion.py` / `prompt_completion.py` 作为 L3 流程模块**允许** import
  `editor_view`（存量耦合，冻结）；但禁止向上 import `yate.editor` / `yate.app`，且新增 `editor_view`
  导入必须在 `tests/test_architecture.py` 的白名单中登记。

### 冻结清单（存量，禁止新增）

| 类别 | 白名单 | 说明 |
|---|---|---|
| Protocol 类 | `editor_view/editor.py::PaneRegistry`、`editor_syntax/engine.py::SyntaxBackend`、`editor_syntax/ts_backend/backend.py::_TsPoint` / `_TsNode` | 前者是本轮唯一新增（环打断器）；后三者先于本轮重构存在（叶包内部：语法后端 + 可选依赖 py-tree-sitter 的私有结构化类型） |
| 禁用命名 | 仅 `PaneHost`（`editor_view/panes.py` 的 Textual 容器 widget）、`PaneManager` / `LspManager`（存量）、`CompletionController`（流程类） | 其余 `*Feature` / `*Host` / `*Ops` / `*Delegate` 一律禁止 |
| UI 耦合 | `completion.py` / `prompt_completion.py` → `editor_view` | 见 R11；新增导入须登记 |

### 守护覆盖（2026-09-23 实测）

`tests/test_architecture.py` 的 **13 个用例**实际覆盖：**R1 / R2 / R3 / R4 / R5 / R6 / R7 / R11 +
窗格模型归属 + 命名守卫**（`*Feature` / `*Host` / `*Ops` / `*Delegate` / `AppProtocol`），以及 `app_features/`
**目录**与 `yate/interfaces.py` 已消失。其中「窗格模型归属」由 `test_pane_model_lives_in_l1_session` 守护：
窗格树模型（`Leaf` / `Split` / `ViewState` + `find_leaf` 等树操作）归 L1 `yate/session.py` 所有，
`editor_view/` 只 import、不再重导出（`editor_view/pane_types.py` 已删除）。R7 由 `test_shell_loads_the_builtin_tables` 守护：
断言 `app.py` 含 `populate(self.editor.actions, self.editor)` /
`register_commands(self.editor.commands, self.editor)`，且 `actions.py` / `commands.py` 只被 `app.py` 导入。

> **R8 / R9 / R10 仍无自动守护**（R8 仅被 R2 的协议守卫间接覆盖）：依赖代码评审与
> [Plan F](plan_F_gate_docs.md) 冒烟清单。

---

## 5. Plan 索引（按序执行，每个 Plan 结束跑门禁）

| # | 文档 | 内容 | 状态 |
|---|---|---|---|
| A | [plan_A_leaf_models.md](plan_A_leaf_models.md) | 叶子模型：`session.py`、`registries.py`、`keymaps/registry.py`、`KeyUi` | ✅ |
| B | [plan_B_widget_selfhold.md](plan_B_widget_selfhold.md) | 组件自持：`chrome.py`、`commandline.py`、`explorer.py`、`terminal.py`、`panes.py`、`statusbar.py`、`modals.py`、`palette.py`、`editor.py` | ✅ |
| C | [plan_C_functional_tables.md](plan_C_functional_tables.md) | 函数化表与流程：`prompt_completion.py`、`completion.py`、`actions.py`、`commands.py`、`services/extensions.py`、`editor.py` | ✅ |
| D | [plan_D_shell_wiring.md](plan_D_shell_wiring.md) | **外壳瘦身与接线**：解环、`app.py` 瘦到 152 行、删除 `app_features/`、cli 走 `app.editor` | ✅ |
| E | [plan_E_tests_tools.md](plan_E_tests_tools.md) | **测试与冒烟脚本迁移**：`app.X` → `app.editor.*`；架构守护规则更新（§E.5 落地记录、§E.6 迁移清单与实测） | ✅ |
| F | [plan_F_gate_docs.md](plan_F_gate_docs.md) | **门禁与文档**：pyright / pytest / `--diag` / 冒烟清单、扩展与用户文档、CHANGELOG、`architecture-boundaries.md` | ✅ |
| G | [plan_G_pane_model_to_session.md](plan_G_pane_model_to_session.md) | **窗格模型下沉**：删除 `editor_view/pane_types.py`，模型并入 `session.py`（L1）；清掉 `panes.py` 的 deprecated 重导出 | ✅ |

---

## 6. 门禁（每个 Plan 结束后执行）

```
python -m pyright yate/ tests/ tools/      # 0 诊断
python -m pytest tests/ -q                 # 全绿（当前被 Plan E 阻塞，见 §1.1）
python -m yate --diag                      # 报告正常
python -m yate --version                   # 正常
```

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `Editor` 变成新的上帝对象 | 它是**唯一**允许的编排大类；新增能力优先落在 `session` / `registries` / `services` / widget / 表模块 / 流程模块；只有"横跨多个协作者的操作"才进 `Editor`。计划 E/F 之后新增会话级流程时，先在 `yate/` 顶层建独立模块（如 `completion.py` 的做法），再考虑塞回 `Editor` |
| 键事件被派发两次（`EditorView.on_key` 与 `YateApp.on_key`） | `EditorView.on_key` 处理后 `event.stop()`；未被消费的键也不再冒泡到外壳二次派发（Plan D.3-6，R10） |
| CSS 布局失效（id 丢失） | `Editor` 构造 widget / compose 容器时必须带上 id：`#sidebar` `#sidebar-head` `#explorer` `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar` + `#body` `#bottom-dock` `#bottom`（详见 §4 R9） |
| 测试大面积改动 | 机械替换属性路径 + 少量语义重写（见 Plan E §E.1 映射表与 §E.6 清单） |
| 行为回归（提示流 / 终端 / 窗格） | 保持原调用顺序与消息文案；按 Plan F 冒烟清单逐项验证 |
| 文档与代码再次脱节 | 架构边界改动必须同时更新 `architecture-boundaries.md` 与本目录对应 Plan；门禁含 `test_architecture.py`；行数等易漂移的事实请标口径与复核日期 |

## 8. 冒烟清单

见 [plan_F_gate_docs.md](plan_F_gate_docs.md) §F.2（启动 / explorer / 终端 / 补全 / vim / 命令 / 扩展 / `--diag`）。

## 9. 相关文档

| 文档 | 关系 |
|---|---|
| [`.trae/rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md) | 本重构的**硬性边界规则**（已按新分层改写），随代码一起被守护 |
| [`.trae/documents/split_app_protocol_plan.md`](../split_app_protocol_plan.md) | **前序重构**：拆分并移除 `AppProtocol`，其产物 `app_features/` 在本轮 Plan D 删除；其正文 §3.2 的 R1–R6 为**旧编号**，勿与本目录的 R1–R11 对照 |
| [`.trae/issues/review.md`](../../issues/review.md) | 代码审查问题清单（多项落在 `app_features/*`，随目录删除而消解） |

## 10. 审计记录（2026-09-23）

4 个子代理按「文档断言 vs 代码事实」逐条复核本目录 7 份文档，并顺带扫描 `tests/` + `tools/`。
**结论：分层、命名、依赖规则与代码一致** —— R1–R6 / R11 实测成立，Plan A / B 的成员清单与构造点
行号（`editor.py:106` / `editor.py:119`）零缺失、精确命中。发现并修正的问题：

| # | 位置 | 问题 | 处置 |
|---|---|---|---|
| 1 | 本 README §1 / Plan C §C.4 / Plan D §D.5-D.6 | 行数未标口径，易被误判为"过期"（差异正是空行） | 标注为**非空行**并给出复核命令（§1.2） |
| 2 | 本 README §4 R9、§7；Plan B §B.5 | id 清单漏 compose 容器 `#body` `#bottom-dock` `#bottom`；`#statusbar` 并非 CSS 选择器 | 按代码更正并说明 |
| 3 | 本 README §4 守护清单 | 误写"由 R1/R2/R4/R5/R6/R7/R11 守护" | 更正为 R1/R2/R3/R4/R5/R6/R11 + 命名守卫，并注明 R7/R9/R10 无自动守护 |
| 4 | 本 README §2 | `keymaps` 同时出现在 L0 与 L1 | L0 限定 `keymaps/base|vim|vsc`；`keymaps/registry.py` 归 L1 |
| 5 | [Plan E](plan_E_tests_tools.md) §E.1 | `app.editor.window_pending` 被标成**方法** | 更正为**属性**（`@property`，加括号会 `TypeError`） |
| 6 | [Plan E](plan_E_tests_tools.md) §E.2 / §E.3 | 迁移理由与用例名过期（`test_terminal.py` 本无需迁移；用例已改名） | 更正并补 `test_highlight.py`、`*Ops` / `*Delegate` |
| 7 | [Plan E](plan_E_tests_tools.md) §E.5 | 未记录 E1–E4 的真实进度 | 改为实测状态 + 新增 §E.6 逐文件待迁移清单 |
| 8 | [Plan F](plan_F_gate_docs.md) §F.3 / §F.2 | 文档现状记错（扩展文档写的是 `ExtensionHost`，非 `YateApp`；rules 已是 R1–R11；`api.keymaps` 仍是 `dict`） | 已更正，并入 §F.5 |
| 9 | `tests/test_architecture.py` docstring；`.trae/rules/architecture-boundaries.md` | 引用不存在的 `app_layering_plan.md`；命名守卫冒用 R7 编号；`test_collaborators_*` 标 R4（实为 R11）；R9 id 清单同上 | 已修正（§F.5） |
| 10 | `.trae/rules/python-coding-style.md`、`.trae/skills/textual-pilot-smoke/SKILL.md`、`split_app_protocol_plan.md` | 残留"窄 Protocol（Host/Ops）"指导、`yate/tracing.py` / `yate/crash.py` 失效路径、错误的 baseline 目录、旧 R 编号 | 已修正（§F.5） |
| 11 | `yate/app_features/` 残留目录（同日追加） | 目录只剩 `__pycache__`，`import yate.app_features` 仍**成功**（空命名空间包），而原用例只断言 `__init__.py` 不存在 | 删除残留目录；`test_app_features_package_is_gone` 改为断言**目录**不存在；rules §六 同步 |
| 12 | `tests/test_architecture.py`（同日追加） | R7（外壳装载内置表）此前**无自动守护** | 补 `test_shell_loads_the_builtin_tables`（用例数 11 → 12），rules §六 与 [Plan E](plan_E_tests_tools.md) §E.3 / §E.5 同步 |
| 13 | [Plan G](plan_G_pane_model_to_session.md) 落地（同日追加） | 窗格模型挂在 L2 `editor_view/pane_types.py`，与「状态放在正确的层 / 不建公共类型层」冲突 | `pane_types.py` 整体删除、模型下沉 `yate/session.py`（L1，与 `EditorSession` 同模块但类本身零改动）；`panes.py` 的 deprecated 重导出与 `__all__` 清理；新增架构守护用例 `test_pane_model_lives_in_l1_session`（用例数 12 → 13）；`.trae/rules/architecture-boundaries.md` §一 / §二 / §三.6 / §六、本 README §2 / §4、[Plan B](plan_B_widget_selfhold.md) §B.2、[split_panes_plan.md](../split_panes_plan.md) 实施状态段同步回填；本 README §1 行数已按实测回填（`session.py` 161 → 281 行）。落地实测见 [Plan G](plan_G_pane_model_to_session.md) §G.9 |

> Plan E / Plan F 的迁移与门禁执行结果（含 5 个并行子任务的交付与复核数据）见
> [Plan E](plan_E_tests_tools.md) §E.5 / §E.6.4 与 [Plan F](plan_F_gate_docs.md) §F.6。
