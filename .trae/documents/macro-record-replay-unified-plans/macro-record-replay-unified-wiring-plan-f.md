# 子计划 f：组装接线 + 跨架构边界同步（wave-3）

> 唯一规范来源：`overview.md` §1.7 / §1.9 / §2 + 主计划
> `../macro-record-replay-unified-plan.md` §5.1 / §5.5(7) / §7；
> 本文件自包含。**本子计划是跨架构边界的独立子计划**。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F9（`Editor` 类属性 / 组装注释 / 800 行）、F10
  （`editor_compose.py` 工厂 / StatusBar 构造 / `__all__`）、F12/F13（R7 装载）、
  F17（`_LAYER_RANKS` / `SIZE_EXEMPT_FILES`）、F21（§三.8 接入清单 / §三.7）。
- 上游依赖：**wave-2 全部验收通过**（plan-d 已登记 `editor.py` 豁免；plan-e 已落盘
  `MacroFlows`）；wave-1 的 `session.macro` 与 statusbar 回调参数已就绪。
- 输出：`Editor.macro_flows` 契约、`_build_macro_flows` 工厂、StatusBar 录制指示
  接线、规则文本与守卫集合**两处同步**、组装顺序注释；接线单测。

> **纪律**：本子计划对 `.trae/rules/architecture-boundaries.md` 的改动属于**执行阶段**；
> 本轮【方案】环节（plan-architect-designer）**不触碰** `.trae/rules/**`，只在方案中
> 描述。执行者按 `overview.md` §2 的产品源码归属裁定由主代理 / 授权 plan-executor
> 实施。

## 1. 独占文件清单（只改这些）

- `yate/editor.py`
- `yate/editor_compose.py`
- `.trae/rules/architecture-boundaries.md`（**执行阶段**同步）
- `tests/test_macro_wiring.py`（新增）
- `tests/test_editor_compose.py`（**D9 主代理亲改**，执行阶段补登）：既有
  `test_editor_compose_exports_five_factories` 硬编码「恰好 5 个工厂」，本计划新增
  第 6 个 `_build_macro_flows` 后确定性冲突。执行者按纪律停下上报、未改断言；
  主代理裁定先补登本清单再亲自更新 expected 集合为 6 个工厂（保持「恰好」强度），
  并同步 `test_editor_imports_factories_from_compose` 的名字列表；改后须实测
  `pytest tests/ -q -k "editor or compose"` 退出码 0。

> **不动** `tests/test_architecture.py`（plan-d 独占）、`yate/editor_dispatch.py`
> （plan-g）、`yate/keymaps/*`、`yate/flows/macro_flows.py`（plan-e）。

## 2. 具体修改（文件:行号）

### 2.1 `yate/editor.py`

- import 区（**第 68-80 行** flows 导入块）按字母序插入
  `from yate.flows.macro_flows import MacroFlows`（`macro_flows` 排在
  `lsp_sync` 之后、`mouse_flows` 之前）。**不** import `yate.actions` /
  `yate.commands`（R5 反向禁止）。
- 类属性注解区（**第 103-143 行**，其它 `*Flows` 之间）追加一行
  `macro_flows: MacroFlows`（§三.8 第 2 条）。
- `__init__`（**第 145 行**起）：
  1. 组装顺序注释（**第 168-176 行**）补一句 ASCII 说明：macro_flows 在 models
     之后、widgets 之前构造（依赖 `session`、被 key_ui 动作间接使用）。
  2. 工厂调用序列（**第 177-181 行**）在 `_build_models(self, keymap)` 之后、
     `_build_widgets(self)` 之前插入 `_build_macro_flows(self)`（§三.8 第 3/4 条）。
- **不改**任何既有方法体（`handle_key` / `handle_raw_key` / `message` /
  `refresh_ui` / `mode_chip`）、不新增 `def apply_theme`（T2）、不引入 `App` 句柄
  到 flows（能力注入守卫）。

### 2.2 `yate/editor_compose.py`

- 顶部内部导入组追加 `from yate.flows.macro_flows import MacroFlows`；保持文件末
  `import yate.editor` 防循环形态不变（对照 `editor_dispatch.py` 第 243 行先例，
  若本文件已有同形态则不动）。
- `__all__`（**第 57-64 行**）追加 `"_build_macro_flows"`（使 `editor.py` 的导入
  对 pyright 读作刻意，避免 `reportPrivateUsage`）。
- 新增工厂（放在 `_build_models` 结束、**第 127 行 `_build_widgets` 之前**）：

```python
def _build_macro_flows(ed: yate.editor.Editor) -> None:
    """Build the macro recorder/replayer with editor capabilities injected."""
    ed.macro_flows = MacroFlows(
        ed.session,
        dispatch_raw=ed.handle_raw_key,
        notify=ed.message,
    )
```

  - `ed.handle_raw_key`（`editor.py:499`）与 `type DispatchRaw = Callable[[str], bool]`
    匹配；`ed.message(text, kind="info")`（`editor.py:423`）与
    `type Notify = Callable[[str, str], None]` 匹配（带默认参数的可调用对象可赋给
    需两个位置参数的 `Callable`，pyright strict 须实测确认，见 §4）。
  - **不持 App 句柄**（§四能力注入 / `test_flow_modules_hold_no_app_handle`）；
    只经绑定方法注入。
- `_build_widgets` 的 `StatusBar(...)` 调用（**第 163-168 行**）在 `id="statusbar"`
  之前追加一行：
  `recording_label=lambda: ed.session.macro.recording_label(),`
  （plan-c 已为 `StatusBar` 加好缺省参数；R13/R14：L2 只接 `Callable`）。
  **不动** `extension_segments` / `loaded_extensions` / `id`。

### 2.3 `.trae/rules/architecture-boundaries.md`（执行阶段同步，四处）

1. §一 L3 清单（**第 18-29 行** `flows/(*.py)` 枚举）追加 `macro_flows.py`。
2. R11 条款（**第 138-160 行**）的 flows 子包枚举追加 `macro_flows.py`，并注明
   「**不** import editor_components，故不进 `UI_FROZEN_FILES`」。
3. §三.7 豁免名单（**第 313-361 行**正式名单）追加 `editor.py` 条目：写明触发
   原因（新增 `MacroFlows` 类属性 / 工厂接线使 splitlines 越 800）、单一职责薄委托
   依据、实测行数（**执行阶段实测后回填，不臆测**），并显式指向
   `tests/test_architecture.py::SIZE_EXEMPT_FILES` 两处同步。
4. §三.8 接入清单第 6 条要求的「同步 §一 L3 清单与本清单」及 §六 用例计数
   （**第 461-467 / 581-623 行**）：按执行阶段**实测**回填新增守卫用例的计数与
   对照表两行；本方案不写未实测的门禁数字。
5. **不**改 `UPWARD_EDGES_FROZEN`（保持空集；本计划无新增向上连线）、
   **不**改 R9 的 id 清单（无新 widget / id）。

### 2.4 `tests/test_macro_wiring.py`（新增）

沿用 `tests/conftest.py` 的 editor / app fixture（若构造 `Editor` 需完整 App，
用既有 fixture，不自建）；断言见 §3。禁止 `# type: ignore`；需要窄化时用
`cast()`（python-coding-style §4.4）。

## 3. 详细测试用例（`tests/test_macro_wiring.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_editor_exposes_macro_flows_bound_to_session` | editor fixture | 构造完成后读 `ed.macro_flows` | `isinstance(ed.macro_flows, MacroFlows)` 为 `True`；`ed.macro_flows._session is ed.session` 为 `True`；`ed.macro_flows` 非 `None` |
| `test_macro_flows_dispatch_raw_routes_to_handle_raw_key` | editor fixture；`monkeypatch.setattr(ed, "handle_raw_key", recorder)` 需在构造前，或直接断言绑定 | 读 `ed.macro_flows._dispatch_raw` 并调用一次 `("x")` | 记录器收到一次 `("x",)`；`ed.macro_flows._dispatch_raw.__self__ is ed`（绑定方法形态，注入而非新协议） |
| `test_macro_flows_notify_is_bound_to_editor_message` | editor fixture | 读 `ed.macro_flows._notify` | `_notify.__self__ is ed` 且 `_notify.__func__ is type(ed).message`（或等价断言：调用后 `message` 收到 `(text, kind)`） |
| `test_statusbar_receives_recording_label_from_session_macro` | editor fixture | 置 `ed.session.macro.recording = "a"` 后调 `ed.status_bar.recording_label()` | 返回 `"rec @a"`；置 `recording = None` 后返回 `None`；`ed.status_bar.recording_label` 非 `None` |
| `test_editor_compose_all_exports_macro_flows_factory` | 无 | `import yate.editor_compose as c` | `"_build_macro_flows" in c.__all__` 且 `callable(c._build_macro_flows)` |
| `test_size_exemption_rule_and_guard_are_in_sync`（两处同步） | 无 | 读 `tests/test_architecture.py::SIZE_EXEMPT_FILES` 与规则文本 §三.7 名单 | 二者都含 `"editor.py"`；`len(Path("yate/editor.py").read_text(encoding="utf-8").splitlines()) > 800`（**实测**）；`pytest tests/test_architecture.py::test_source_files_within_size_threshold` 退出码 0 |
| `test_rule_l3_and_r11_lists_include_macro_flows` | 无 | 读规则文本 §一 L3 清单段与 R11 段 | 两段文本都含 `macro_flows.py`；且规则文本不含把该模块登记进 `UI_FROZEN_FILES` 的表述（R11 免登记） |
| `test_editor_does_not_import_action_tables_after_wiring`（R5 回归） | 无 | `ast.parse("yate/editor.py")` 收集 import | 不含 `yate.actions` / `yate.commands`；含 `yate.flows.macro_flows`；`UPWARD_EDGES_FROZEN` 仍为空集（读守卫常量） |
| `test_wiring_preserves_statusbar_id_and_existing_injections`（边界 / R9） | editor fixture | 读 `ed.status_bar.id` 与既有注入 | `ed.status_bar.id == "statusbar"`；`ed.status_bar.extension_segments` / `loaded_extensions` 与未接线前一样非 `None`（按既有 fixture 取值） |
| `test_missing_macro_flows_attribute_is_a_type_error`（异常流，静态） | 无 | 对 `yate/editor.py` 运行 pyright strict | 退出码 0、零诊断（证明类属性注解 + 工厂赋值两处齐全，无 `reportAttributeAccessIssue`）；若故意删注解则 pyright 报错（执行者负向演练，演练后还原） |

## 4. 验证方案

- **验证目标**：证明 §三.8 六条接入清单逐条落地（命名 / 类属性 / 工厂注入 /
  组装注释 / 免 `UI_FROZEN_FILES` / L3 清单同步）、§三.7 体量豁免两处同步、
  R5 / R9 / R13 / R14 / 能力注入守卫全部成立。
- **需一并回归的既有测试**：`tests/test_architecture.py` 全量（含 plan-d 两条新
  守卫）、`pytest tests/ -q -k "editor or compose"`、`tests/test_macro_statusbar.py`
  （plan-c）、`tests/test_macro_flows.py`（plan-e）。
- **通过判定标准**：pyright 退出码 0 零诊断（特别验证 `Notify` 与
  `ed.message` 带默认参数的赋值兼容）；pytest 退出码 0、断言全绿；架构守卫
  无违规；规则文本与 `SIZE_EXEMPT_FILES` 两处一致。
- **实测项（不可凭假设）**：`editor.py` 改后 `splitlines()` 实际行数须回填
  （主计划 §12 第 5 条）；若实测 ≤ 800，须**撤销**豁免登记并在方案 / 报告回填
  偏离依据，不得静默改设计。
- **无法自动化部分**：真实 App 启动后 `rec @a` 的视觉呈现由 plan-c 的人工验证 +
  plan-k 端到端覆盖。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/editor.py yate/editor_compose.py yate/flows/macro_flows.py
.venv\Scripts\python.exe -m pytest tests/test_macro_wiring.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "editor or compose"
```

## 6. 架构边界与守卫（本子计划触发的 R 条款）

| 条款 | 触碰点 | 应落入 `tests/test_architecture.py` 的守卫 |
|---|---|---|
| R5 | `editor.py` 新增 flows import，仍不 import 内置表 | `test_editor_does_not_import_action_tables`（既有，回归） |
| R7 | 装载仍由 `YateApp.__init__` 的 `populate` / `register_commands` 承担，本计划不改 app.py | `test_shell_loads_the_builtin_tables`（既有，回归） |
| R8 / §四 | 具体对象 `EditorSession` + 绑定方法注入，不持 App 句柄 | `test_flow_modules_hold_no_app_handle`、`test_app_annotations_are_precise`（既有，回归） |
| R9 | 不新增 widget / id，`#statusbar` 沿用 | 既有 id 守卫（回归） |
| R11 | `macro_flows.py` 不 import `editor_components`，免登记 `UI_FROZEN_FILES` | `test_collaborators_keep_widget_coupling_frozen`（既有，回归） |
| R13 / R14 | L3 只给 L2 注入 `Callable`，`UPWARD_EDGES_FROZEN` 保持空集 | `test_no_unregistered_upward_imports`、`test_editor_components_does_not_import_upward`（既有，回归） |
| §三.7 | `editor.py` 越线登记豁免（规则文本 + 守卫集合两处） | `test_source_files_within_size_threshold`、`test_editor_size_exemption_is_registered`（plan-d 新增，回归） |
| §三.8 | 新增 L3 流程模块 6 条接入清单 | wave-3 pyright + 全量架构守卫 + 规则文本同步复核 |
| 层秩 | 新模块由 `("flows/", 3)` 自动归 L3 | `test_no_unregistered_upward_imports`（既有，回归） |

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `editor.py` 越 800 行而豁免未登记 → 架构守卫红 | plan-d 已提前登记；本计划同步规则文本 §三.7 + 两处一致性用例 | `git checkout -- yate/editor.py yate/editor_compose.py .trae/rules/architecture-boundaries.md tests/test_macro_wiring.py` |
| 规则文本与 `SIZE_EXEMPT_FILES` 两处不同步 | §2.3 四处一次性改 + `test_size_exemption_rule_and_guard_are_in_sync` | 同上（两处同时回退） |
| `ed.message` 与 `Notify` 类型不兼容导致 pyright 诊断 | pyright strict 实测；必要时在 `MacroFlows` 侧用 `Callable[[str, str], None]` 保持契约，不改编辑器签名 | 同上；若契约确需变，停下来上报 |
| import 循环（`editor_compose` ↔ `editor`） | 保持文件末 `import yate.editor` 防循环形态；`MacroFlows` 不 import `editor_compose` | 同上 |
| 组装修注 / 类属性漏加导致 pyright `reportAttributeAccessIssue` | §2.1 三处 + 静态负向演练 | 同上 |
| 实测 `editor.py` 仍 ≤ 800 却已登记豁免 | §4 实测项：撤销登记并回填偏离 | 同上 |
