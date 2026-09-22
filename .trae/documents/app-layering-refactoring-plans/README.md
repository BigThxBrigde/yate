# 分层重构计划：外壳 / 调度 / 组件 / 会话

> 状态：**Plan A–D 已完成 · Plan E 执行中 · Plan F 待执行**（2026-09-22）
> 目标：项目结构清晰、层次划分清晰、扩展性与维护性好；改动性质以**代码搬运 + 删除**为主，
> 不重写算法；**能用函数实现的就不造类**。
> 本目录是本次重构的**唯一计划来源**；代码侧的硬性边界同时固化在
> [`.trae/rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md)，
> 由 `tests/test_architecture.py` 守护。

---

## 1. 事实基线（2026-09-22 实测）

| 指标 | 值 |
|---|---|
| `yate/app.py` | **152 行**（重构前 2005 行） |
| `yate/editor.py` | 1245 行（`Editor`：唯一允许的编排大类） |
| `yate/session.py` | 161 行（`EditorSession`，无 UI） |
| `yate/registries.py` / `actions.py` / `commands.py` | 60 / 111 / 203 行 |
| `yate/completion.py` / `prompt_completion.py` | 280 / 126 行 |
| 已删除 | `yate/app_features/`（6 文件 / 1070 行）、`app.py` 内 1875 行业务代码 |
| `AppProtocol` / `yate.interfaces` | 全仓库 0 处 |
| 新增模块 | `session.py`、`registries.py`、`editor.py`、`actions.py`、`commands.py`、`completion.py`、`prompt_completion.py`、`editor_view/chrome.py`、`keymaps/registry.py` |
| 门禁现状 | `python -m pyright yate/` → **0 errors, 0 warnings** |

---

## 2. 目标分层（唯一权威定义）

```
L4 外壳   yate/app.py            YateApp     Textual 壳：CSS / 主题桥 / 生命周期 / 事件转发 / 装载内置表
L3 调度   yate/editor.py         Editor      会话 + 服务 + 组件的编排层："编辑器操作"的唯一落点
L3 表     yate/actions.py        populate(registry, editor)
          yate/commands.py       register_commands(registry, editor)      内置表（纯函数，无类）
L3 流程   yate/completion.py     CompletionController                     会话级流程（补全）
          yate/prompt_completion.py  prompt_completions(...)              纯函数候选生成
          yate/diagnostics.py    format_report(editor) / print_report(editor)  纯函数报告
L2 组件   yate/editor_view/*     TabBar / Breadcrumbs / PromptBar / ExplorerTree /
                                 TerminalPanel / PaneHost / StatusBar / CompletionPopup /
                                 HelpScreen / OutputScreen / PaletteScreen / MarkdownDocScreen / EditorView
L1 会话   yate/session.py        EditorSession   文档 / 标签 / 搜索（无 UI、无 LSP）
L1 模型   yate/registries.py     ActionRegistry / CommandRegistry（叶子容器）
          yate/keymaps/registry.py  KeymapSet（键映射集合 + 活动项）
L0 叶子   editor_core / editor_lsp / editor_syntax / editor_term / services / config / logs / paths / keymaps
```

**一句话职责划分**

| 层 | 干什么 | 不干什么 |
|---|---|---|
| `YateApp`（外壳） | 调 `Editor`；持有 Textual 生命周期、主题桥、CSS、内置表装载 | 不实现任何业务操作 |
| `Editor`（调度） | 组合模型/服务/组件，实现"操作"（打开、保存、窗格、键分发、提示、主题、shell、LSP、覆盖层、扩展） | 不做渲染、不做文本编辑算法、不写补全候选算法 |
| 表 / 流程模块 | 把"内置能力"登记到注册表；把可独立成段的流程挪出 `Editor` | 不反向被 `editor.py` 导入（防环） |
| Widget（组件） | 自持自己的行为与渲染，构造注入具体协作者或回调 | 不 import `yate.editor` / `yate.app` |
| `EditorSession` | 文档集合、标签、搜索状态、关闭通知 | 不碰 UI、不碰 LSP |
| 叶子 | 纯逻辑 | 不 import 上层 |

`yate/editor_view/` 模块清单：`chrome.py`（TabBar / Breadcrumbs）、`commandline.py`（PromptBar）、
`explorer.py`（ExplorerTree）、`completion.py`（CompletionPopup）、`editor.py`（EditorView + 唯一保留的
`PaneRegistry` Protocol）、`panes.py`（PaneManager / PaneHost）、`pane_types.py`（Pane 树纯数据结构）、
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
- **R9** 组件 id 归调度层：`Editor` 构造 widget 时带上外壳 CSS 依赖的 id（`#sidebar` `#sidebar-head`
  `#explorer` `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar`）。
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

> 以上由 `tests/test_architecture.py`（11 个用例）守护：R1 / R2 / R4 / R5 / R6 / R7 / R11 + `app_features`
> 与 `yate/interfaces.py` 已消失。

---

## 5. Plan 索引（按序执行，每个 Plan 结束跑门禁）

| # | 文档 | 内容 | 状态 |
|---|---|---|---|
| A | [plan_A_leaf_models.md](plan_A_leaf_models.md) | 叶子模型：`session.py`、`registries.py`、`keymaps/registry.py`、`KeyUi` | ✅ |
| B | [plan_B_widget_selfhold.md](plan_B_widget_selfhold.md) | 组件自持：`chrome.py`、`commandline.py`、`explorer.py`、`terminal.py`、`panes.py`、`statusbar.py`、`modals.py`、`palette.py`、`editor.py` | ✅ |
| C | [plan_C_functional_tables.md](plan_C_functional_tables.md) | 函数化表与流程：`prompt_completion.py`、`completion.py`、`actions.py`、`commands.py`、`services/extensions.py`、`editor.py` | ✅ |
| D | [plan_D_shell_wiring.md](plan_D_shell_wiring.md) | **外壳瘦身与接线**：解环、`app.py` 瘦到 152 行、删除 `app_features/`、cli 走 `app.editor` | ✅ |
| E | [plan_E_tests_tools.md](plan_E_tests_tools.md) | **测试与冒烟脚本迁移**：`app.X` → `app.editor.*`；架构守护规则更新 | 🔄 执行中 |
| F | [plan_F_gate_docs.md](plan_F_gate_docs.md) | **门禁与文档**：pyright / pytest / `--diag` / 冒烟清单、扩展与用户文档、CHANGELOG、`architecture-boundaries.md` | ⏳ |

---

## 6. 门禁（每个 Plan 结束后执行）

```
python -m pyright yate/ tests/ tools/      # 0 诊断
python -m pytest tests/ -q                 # 全绿
python -m yate --diag                      # 报告正常
python -m yate --version                   # 正常
```

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `Editor` 变成新的上帝对象 | 它是**唯一**允许的编排大类；新增能力优先落在 `session` / `registries` / `services` / widget / 表模块 / 流程模块；只有"横跨多个协作者的操作"才进 `Editor`。计划 E/F 之后新增会话级流程时，先在 `yate/` 顶层建独立模块（如 `completion.py` 的做法），再考虑塞回 `Editor` |
| 键事件被派发两次（`EditorView.on_key` 与 `YateApp.on_key`） | `EditorView.on_key` 处理后 `event.stop()`；未被消费的键也不再冒泡到外壳二次派发（Plan D.3-6） |
| CSS 布局失效（id 丢失） | `Editor` 构造 widget 时必须带上外壳 CSS 依赖的 id：`#sidebar` `#sidebar-head` `#explorer` `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` |
| 测试大面积改动 | 机械替换属性路径 + 少量语义重写（见 Plan E 映射表） |
| 行为回归（提示流 / 终端 / 窗格） | 保持原调用顺序与消息文案；按 Plan F 冒烟清单逐项验证 |
| 文档与代码再次脱节 | 架构边界改动必须同时更新 `architecture-boundaries.md` 与本目录对应 Plan；门禁含 `test_architecture.py` |

## 8. 冒烟清单

见 [plan_F_gate_docs.md](plan_F_gate_docs.md) §F.2（启动 / explorer / 终端 / 补全 / vim / 命令 / 扩展 / `--diag`）。

## 9. 相关文档

| 文档 | 关系 |
|---|---|
| [`.trae/rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md) | 本重构的**硬性边界规则**（已按新分层改写），随代码一起被守护 |
| [`.trae/documents/split_app_protocol_plan.md`](../split_app_protocol_plan.md) | **前序重构**：拆分并移除 `AppProtocol`，其产物 `app_features/` 在本轮 Plan D 删除 |
| [`.trae/issues/issues.md`](../../issues/issues.md) | 代码审查问题清单（多项落在 `app_features/*`，随目录删除而消解） |
