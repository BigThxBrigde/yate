---
alwaysApply: true
scene: architecture
---

# yate 架构边界规则

本规则固化「拆分并移除 AppProtocol」重构的目标架构（完整方案见
`.trae/documents/split_app_protocol_plan.md`）。**所有新增/修改代码都必须遵守，
不得因为新功能而破坏这些边界。** 部分边界仍在重构实施中（如 AppProtocol 尚未删除），
新代码从今天起就要遵守，不得加重遗留。

## 一、依赖方向（硬性规则）

```
L0 叶子：editor_core / editor_lsp / editor_syntax / editor_term / logs / paths
L1 服务：services/{workspace,shell,fonts} / keymaps / actions
L2 功能与 UI：app_features/* / editor_view/* / services/extensions / diagnostics
L3 组合根：app.py（YateApp） / cli.py
```

- **R1 — YateApp 是顶层，不被下层引用**：`yate/` 内只有 `cli.py`（入口）允许
  `import yate.app`。其他模块需要宿主能力时，在**自己的模块内**定义窄 Protocol，
  由 `YateApp` 结构性满足（不需要 import 具体类型）。
- **R2 — 禁止"全应用协议"**：任何协议只包含**单个消费者**实际访问的成员。
  - Host 协议：组件声明自己需要的宿主能力，定义在组件模块内，`YateApp` 实现；
  - Ops 协议：Feature 声明对外提供的操作，定义在 Feature 模块内，widget 依赖。
  - ❌ 给某个公共接口"加一个成员"；✅ 在使用方模块扩展/新增窄协议。
  - ❌ 重建 `interfaces.py` 式的中央接口文件。
- **R3 — `app_features/*` 不得导入 `editor_view` 的 widget**
  （`editor` / `explorer` / `panes` / `terminal` / `statusbar` / `commandline` /
  `modals` / `palette`）。需要面板/屏幕/提示条能力时，使用**语义化 Host 方法**
  （如 `show_terminal_panel(height)`、`activate_prompt(...)`）。
  - 例外（被导入方不反向依赖对应 Feature）：`docs → editor_view.manual`、
    `completion → editor_view.completion`。
- **R4 — `editor_view` 的 widget 只能导入 `app_features` 的协议或数据类型**
  （如 `ExplorerOps`、`CommandRegistry`），**不得**导入其实现类（`ExplorerFeature` 等）。
- **R5 — 循环敏感边**：`services/extensions.py` 与 `app_features/commands.py`
  不得导入 `editor_view`（否则 `extensions → commands → editor_view 包 → statusbar`
  `→ extensions` 成环）。`:theme` 等信息通过 Host 语义方法获取，不直接读模块全局状态。
- **R6 — 禁止 `TYPE_CHECKING`**：不新增 `if TYPE_CHECKING:` 导入块。类型注解跨模块
  引用时，使用模块内窄 Protocol 或叶子类型。现状 2 处遗留（`interfaces.py`、
  `tests/test_editor_core.py`）随重构清除，目标全仓库 0 处。

## 二、接口设计

1. 协议定义在**消费方或提供方模块自身**，不建中央接口文件、不建"公共类型层"。
2. 协议成员类型只能来自：stdlib、textual、叶子包（`editor_core`、`editor_lsp`、
   `editor_syntax`、`editor_term`、`logs`、`paths`、`services.workspace`、
   `services.shell`）或本模块内定义的类型/协议。
3. 协议成员数 = 消费者实际访问量；不"预留"、不"顺手加一个"。
4. 禁止用 `Any` / `# type: ignore` 掩盖协议不匹配（pyright strict 会强制
   `YateApp` 真正满足协议）。
5. 读写分离：读状态用只读属性/查询方法；只有真正的命令才用操作方法。
6. 同名成员（如 `message`）在多个协议中重复出现是**正确**的（结构化子类型），
   不要为了去重而抽出共享基接口。

## 三、跨模块交互

| 场景 | 规定机制 |
|---|---|
| 1:1 操作 / 查询 | 窄 Protocol 同步直调 |
| 1:N 低频广播 | 现有回调（如 `LspManager(on_event=...)`）；必要时轻量 Signal（回调列表） |
| UI 事件 | Textual messages（`on_key` / `Input.Submitted` 等） |
| 异步任务 | `host.spawn(coro_fn, group=...)` 原语；下层不得直接使用 textual worker |
| 插件注册 | `ActionRegistry` / `CommandRegistry` / `Keymap.add_binding` |

- **禁止**：全局 EventBus、字符串事件名、下层直接读写高层私有状态（`app._xxx`）。
- 新增信号的门槛：出现 ≥3 处"通知方不知道谁在监听且订阅者动态增删"的场景后再评估，
  且保持同线程同步派发。

## 四、新增功能自检清单

提交前逐项确认：

- [ ] 新依赖方向向下：没有 `import yate.app`、没有导入上层实现类？
- [ ] 需要宿主能力时，在消费方模块定义**窄协议**，而不是扩展公共接口？
- [ ] `app_features` 没有导入 `editor_view` 的 widget（改用语义化 Host 方法）？
- [ ] 没有新增 `TYPE_CHECKING`、`Any`、`# type: ignore`？
- [ ] 业务逻辑归属正确：Feature 管业务操作，`YateApp` 只做组合、接线、协议实现？
- [ ] 跨模块交互用协议直调/回调，而不是把逻辑堆回 `YateApp` 或直连私有状态？
- [ ] `python -m pyright yate/ tests/ tools/` 零诊断、`python -m pytest tests/ -q` 全绿？

## 五、防回归

重构落地后新增 `tests/test_architecture.py`（草案见计划文档 §7.2），守护：

- 无 `AppProtocol`、无 `yate.interfaces` 引用；
- 无 `TYPE_CHECKING`；
- 仅 `cli.py` 可 `import yate.app`；
- `app_features` 不导入 `editor_view` widget；
- 模块依赖图无环。

架构测试失败 = 阻塞合并，不得用豁免注释绕过。

## 六、与其它规则的关系

- 本规则是**架构边界**的权威来源。`python-coding-style.md` 中旧有的
  `TYPE_CHECKING` 条款（§1.3 / §3.2 / §4.3）已按本规则修订，二者冲突时以本规则为准。
- 架构决策变更必须**同步更新**本规则与 `.trae/documents/split_app_protocol_plan.md`。
