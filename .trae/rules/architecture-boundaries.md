---
alwaysApply: true
scene: architecture
---

# yate 架构边界规则

本规则固化「分层重构」后的目标架构。完整方案与执行记录见
[`.trae/documents/app-layering-refactoring-plans/`](../documents/app-layering-refactoring-plans/README.md)
（总纲 `README.md` + `plan_A`…`plan_F`）。
**所有新增/修改代码都必须遵守，不得因为新功能而破坏这些边界。**

## 一、依赖方向（硬性规则）

```
L4 外壳：app.py（YateApp） / cli.py（唯一入口）
L3 调度：editor.py（Editor）/ actions.py / commands.py / completion.py /
         prompt_completion.py / diagnostics.py / services/extensions.py
L2 组件：editor_view/*
L1 会话与模型：session.py（EditorSession）/ registries.py / keymaps/registry.py（KeymapSet）
L0 叶子：editor_core / editor_lsp / editor_syntax / editor_term / logs / paths /
         config / services/* / keymaps/base|vim|vsc
```

- **R1 — `YateApp` 是顶层，不被下层引用**：`yate/` 内只有 `cli.py` 允许 `import yate.app`。
- **R2 — 禁止"全应用协议"**：不得新增 `Protocol`。例外（**存量冻结白名单，共 4 个类**）：
  `editor_view/editor.py::PaneRegistry`（本轮唯一新增：打断 `PaneHost ↔ EditorView` 的构造环，见 Plan B）、
  `editor_syntax/engine.py::SyntaxBackend`、`editor_syntax/ts_backend/backend.py::_TsPoint` / `_TsNode`
  （后三者先于本轮重构存在，属叶包内部；后两个是可选依赖 py-tree-sitter 的私有结构化类型）。
  需要共享状态时传**具体对象**。
- **R3 — `editor_view/*` 不得 import `yate.editor` / `yate.app`**：组件只接受具体协作者
  （`EditorSession` / `Workspace` / `PromptBar` / `LspManager` / `KeymapSet` / `Textual App`）
  或 `Callable` 回调。
- **R4 — `keymaps/*`、`services/*`、`session.py`、`registries.py` 不得 import `editor_view`**。
- **R5 — 内置表单向**：`actions.py` / `commands.py` 可以 import `yate.editor`；反向禁止
  （`editor.py` 不得 import 它们，否则成环）。
- **R6 — 禁止 `TYPE_CHECKING`**：全仓库 **0 处**（已达成，架构测试拦截回归）。
- **R11 — 冻结 UI 耦合**：`completion.py` / `prompt_completion.py` 是 L3 流程模块，**允许** import
  `editor_view`（存量耦合，冻结）；两者禁止向上 import `yate.editor` / `yate.app`，且**新增**
  `editor_view` 导入必须先在 `tests/test_architecture.py` 的白名单中登记。
- **R7 — 外壳装载内置表**：`YateApp.__init__` 调 `populate(editor.actions, editor)` 与
  `register_commands(editor.commands, editor)`。
- **R8 — 共享模型用具体对象**：跨层传递 `EditorSession` / `KeymapSet` / `ActionRegistry` /
  `CommandRegistry` 本身，不再为每个消费者定义窄协议。
- **R9 — 组件 id 归调度层**：`Editor` 构造 widget 时必须带上 id
  （`#sidebar` `#sidebar-head` `#explorer` `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar`），
  `compose()` 里再带上容器 id（`#body` `#bottom-dock` `#bottom`）。
  其中 `#statusbar` 只是 widget id（CSS 用类选择器 `StatusBar`），其余 id 均被 `app.py` 的 CSS 直接引用：
  改 id 必须同步改 CSS。
- **R10 — 一次按键只派发一次**：`EditorView.on_key` 处理后 `event.stop()` / `prevent_default()`，
  未被消费的键不得冒泡到外壳二次派发。

## 二、分层职责

| 层 | 可以做什么 | 不可以做什么 |
|---|---|---|
| `YateApp`（L4） | Textual 生命周期、`CSS`、主题桥（`get_theme_variable_defaults` / `theme.*` 注册）、事件转发、装载内置表 | 不持有业务状态、不实现业务操作 |
| `Editor`（L3） | 组合模型/服务/组件，实现横跨多个协作者的"操作" | 不做渲染、不做文本算法、不直接持有 widget 内部状态 |
| 表与流程模块（L3） | 把内置能力登记进注册表（`populate` / `register_commands`）；把单一流程独立成模块（`completion.py`、`prompt_completion.py`、`diagnostics.py`） | 不被 `editor.py` 反向导入 |
| `editor_view/*`（L2） | 自己的渲染与行为（自持），构造注入具体协作者或回调 | 不 import `yate.editor` / `yate.app`；不直连 LSP 状态 |
| `EditorSession` / `KeymapSet` / 注册表（L1） | 文档、标签、搜索、键映射集合、动作与命令容器（无 UI） | 不 import `editor_view`、不碰 Textual |
| 叶子（L0） | 纯逻辑（编辑器内核、LSP 客户端、语法、终端模拟、配置、日志、路径、shell、workspace、字体） | 不 import 上层 |

## 三、接口与代码形态设计

1. 不建中央接口文件、不建"公共类型层"（`app_features/*`、`interfaces.py`、`*Protocol` 命名均已废止）。
2. 需要"能力"时：优先传**具体对象**；确实是 1:1 回调时用 `Callable` 类型别名或 `*Ui` 记录
   （如 `KeyUi`、`PromptCompleter`），不引入协议类。
3. 禁止用 `Any` / `# type: ignore` 掩盖类型不匹配（pyright strict 必须真正成立）。
4. 读写分离：读状态用只读属性 / 查询方法；只有真正的命令才用操作方法。
5. 包 `__init__.py` 保持惰性：不 re-export 子模块符号，避免 `import yate.X` 连带加载整层。
6. **能用函数实现的就不造类**：内置表（`populate` / `register_commands` / `load_startup_extensions`）、
   纯计算（`prompt_completions` / `format_report` / `mode_chip` / `fuzzy_match`）、数据操作
   （`pane_types.py` 的 `find_leaf` / `replace_node` …）一律用函数。

## 四、跨模块交互

| 场景 | 规定机制 |
|---|---|
| 1:1 操作 / 查询 | 直接调用具体协作者的方法（`session` / `workspace` / `lsp` / widget） |
| 1:N 低频广播 | 回调列表或构造注入的回调（如 `EditorSession(on_closed=...)`、`TabBar(on_activate=...)`） |
| UI 事件 | Textual messages（`on_key` / `Input.Submitted` / `MouseDown` 等） |
| 异步任务 | Textual `App.run_worker(...)`；调度层提供 `*_later` 便捷入口（`open_path_later` / `run_shell_command_later`）；防抖定时用 `asyncio.get_running_loop().call_later` |
| 插件注册 | `ActionRegistry` / `CommandRegistry` / `Keymap.add_binding`（经 `ExtensionContext` 暴露） |

- **禁止**：全局 EventBus、字符串事件名、下层直接读写高层私有状态（`app._xxx`）。
- 新增信号的门槛：出现 ≥3 处"通知方不知道谁在监听且订阅者动态增删"的场景后再评估，
  且保持同线程同步派发。

## 五、新增功能自检清单

提交前逐项确认：

- [ ] 依赖方向向下：没有 `import yate.app`、没有导入上层实现类？
- [ ] 状态放在正确的层：文档 / 标签 / 搜索 → `EditorSession`；键映射 → `KeymapSet`；
      动作与 `:` 命令 → `ActionRegistry` / `CommandRegistry`？
- [ ] 组件行为写在组件内部（自持），而不是加回 `Editor` 或外壳？
- [ ] `Editor` 只新增"横跨多个协作者的操作"；单一流程已拆成独立模块（参照 `completion.py`）？
- [ ] 没有新增 `Protocol`（除 `PaneRegistry`）、`TYPE_CHECKING`、`Any`、`# type: ignore`？
- [ ] 没有使用 `*Feature` / `*Host` / `*Ops` / `*Delegate` 命名？
      （白名单：`PaneHost`、`PaneManager`、`LspManager`；`*Controller` 仅限流程类如 `CompletionController`）
- [ ] 新 widget 需要外壳 CSS 时，id 已由 `Editor` 传入（R9）？
- [ ] 新按键路径不会造成二次派发（R10）？
- [ ] `python -m pyright yate/ tests/ tools/` 零诊断、`python -m pytest tests/ -q` 全绿？

## 六、防回归

`tests/test_architecture.py` 已落地 **12 个用例**（`python -m pytest tests/test_architecture.py -q` → 12 passed）：

- **R1** 仅 `cli.py` 可 `import yate.app`（`app.py` 自身豁免）；
- **R2** 全仓（yate + tests + tools）无 `AppProtocol`；`yate/interfaces.py` 不存在；
  除 4 个冻结白名单外无任何 `Protocol` 类；
- **R3** `editor_view/*` 不 import `yate.editor` / `yate.app`（子模块前缀匹配，不误伤 `editor_core` /
  `editor_lsp` / `editor_syntax` / `editor_term`）；`yate/app_features/` **目录**不存在（只删 `__init__.py`
  不够：残留目录会被当作空命名空间包导入，掩盖删除）；
- **R4** `keymaps/*`、`services/*`、`session.py`、`registries.py` 不 import `editor_view`（严格 0 违规）；
- **R11** `completion.py` / `prompt_completion.py` 不向上依赖，`editor_view` 导入必须落在冻结集合内；
- **R5** `editor.py` 不 import `yate.actions` / `yate.commands`；
- **R7** 只有 `app.py` 导入内置表，且 `YateApp.__init__` 调用
  `populate(self.editor.actions, self.editor)` / `register_commands(self.editor.commands, self.editor)`；
- **R6** 全仓无 `TYPE_CHECKING`；
- **命名守卫** yate 下标识符不得为 `*Feature` / `*Host` / `*Ops` / `*Delegate` / `AppProtocol`
  （白名单：`PaneHost`；`*Manager` / `*Controller` 允许）。

架构测试失败 = 阻塞合并，不得用豁免注释绕过。

## 七、与其它规则的关系

- 本规则是**架构边界**的权威来源。`python-coding-style.md` 中旧有的 `TYPE_CHECKING` 条款
  （§1.3 / §3.2 / §4.3）已按本规则修订，二者冲突时以本规则为准。
- 架构决策变更必须**同步更新**本规则与
  `.trae/documents/app-layering-refactoring-plans/`（总纲 + 对应 Plan）。
- 前序重构（拆分并移除 `AppProtocol`）的方案文档：
  [`.trae/documents/split_app_protocol_plan.md`](../documents/split_app_protocol_plan.md)；其产物
  `app_features/` 已在本轮 Plan D 删除。
