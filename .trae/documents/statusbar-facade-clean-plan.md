# statusbar-facade-clean 方案：移除 L2→L3 存量白名单例外

> 任务：修复 `editor_view/statusbar.py` 对扩展机件的直接依赖，移除
> `EXTENSION_SUBMODULE_FROZEN` 与 `UPWARD_EDGES_FROZEN` 两处白名单，使 L2→L3
> 向上连线**归零**。用户已在对话中批准注入回调的思路（"继续修复 statusbar.py
> 约束，移除白名单"）。
> 执行环境：worktree `../yate-statusbar-facade-clean`（分支
> `ref/statusbar-facade-clean`，基于 master `d84bef5`，沙箱 venv 已重建自证）。

## 一、现状取证

| # | 事实 | 证据 |
|---|---|---|
| 1 | statusbar 仅以 `self.ui.segments(align)` 一个方法使用桥 | `yate/editor_view/statusbar.py:211` |
| 2 | statusbar 还持 `ExtensionLoader`，仅用 `len(loader.loaded)` 画提示段 | `statusbar.py:29, 92, 138` |
| 3 | editor 注入 `ui=ed.extension_api.ui` | `yate/editor.py:156-159` |
| 4 | 两处守卫白名单：`UPWARD_EDGES_FROZEN`（statusbar 2 条向上连线）、`EXTENSION_SUBMODULE_FROZEN`（statusbar 1 条直引） | `tests/test_architecture.py:163-166, 270-272` |
| 5 | 测试对 `status_bar.ui` / 裸构造StatusBar 的引用集中在 test_ui_contributions | `tests/test_ui_contributions.py:222-231` |
| 6 | `StatusSegment` 是门面公共名（14 名内），`SegmentAlign` 不是 | `yate/services/extensions/__init__.py:65` |
| 7 | 规则文本多处登记该例外（R14 条目、§一 mermaid 虚线、§六 #30/#32 描述） | `.trae/rules/architecture-boundaries.md` |

## 二、方案（对话已批准的"切干净"路线）

`StatusBar` 不再持有任何 L3 对象，改为两个回调注入：

1. `extension_segments: Callable[[Literal["left", "right"]], list[StatusSegment]] | None = None`
   —— editor 注入 `ed.extension_api.ui.segments` 绑定方法（语义能力注入，
   issue IKJB0Q 模式；`StatusSegment` 走门面公共名）；
2. `loaded_extensions: Callable[[], int] | None = None`
   —— editor 注入 `lambda: len(ed.extension_loader.loaded)`；`None` 时按 0
   （保持裸构造路径可用）。

删除项：
- `statusbar.py` 的 `ExtensionLoader` / `UiExtensionBridge` 两个 import；
- `tests/test_architecture.py` 的 `EXTENSION_SUBMODULE_FROZEN` 机制（直引守卫
  改为零例外断言）与 `UPWARD_EDGES_FROZEN` 内容（置空集，机制保留作回归守卫）；
- 规则文本 R14 的"L2→L3 已登记例外"、§一 mermaid 虚线例外边、§六 #30/#32 的
  白名单描述——**例外清零是收紧边界，规则文本同步现实**。

## 三、备选与否决

| 路线 | 结论 |
|---|---|
| A（采纳）：回调注入两个能力，statusbar 零 L3 import | 例外清零，不动门面 14 名 |
| B（否决）：门面再导出 `UiExtensionBridge` / `SegmentAlign` | 需改 14 名冻结测试 + 规则文本，用户明确不要 |
| C（否决）：仅移除 bridges 直引、保留 ExtensionLoader | 白名单只减一条不清零，未达"移除白名单"目标 |

## 四、实施步骤与验收

### Step 1：statusbar + editor 接线
- `yate/editor_view/statusbar.py`：构造参数、`_extension_texts`、hints 段、
  模块 docstring；
- `yate/editor.py:156-159`：改传两个回调。
- 验收：`.venv\Scripts\python.exe -m pyright yate/`；`.venv\Scripts\python.exe -m pytest tests/test_ui_contributions.py tests/test_app_lsp.py -q`

### Step 2：守卫测试清零白名单
- `tests/test_architecture.py`：`UPWARD_EDGES_FROZEN` 置空集（注释更新）、
  删除 `EXTENSION_SUBMODULE_FROZEN` 并改写 `test_extension_machinery_hides_behind_facade`
  的直引断言为零例外；相关 docstring 更新。
- `tests/test_ui_contributions.py`：`status_bar.ui` 引用与新构造签名适配。
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_ui_contributions.py -q`

### Step 3：规则文本同步（收紧）
- `.trae/rules/architecture-boundaries.md`：§一 连线图 intro 与 mermaid 虚线、
  R14 条目例外段、§六 #30/#32 描述。
- 验收：纯文档（misc-rules §三豁免测试），但同批含代码按全量门禁走。

### Step 4：收尾
- 全量门禁（主代理亲自跑）：pyright yate/ tests/；pytest 全量 --cov-fail-under=75；
  test_architecture 单跑。
- 提交按步骤分笔（refactor / test / docs(rules) / docs(plan)）。

## 五、风险与回滚

- `StatusBar` 构造签名变更影响所有构造点（editor + 测试裸构造）——已 grep 全量定位；
- 回滚路径：分支级 revert，无数据/配置迁移。

## 六、执行记录（回填区）

- [x] Step 1（提交 `3ca1a21`）：statusbar 改注入 `extension_segments` /
  `loaded_extensions` 两个回调；**偏离计划一处（更优）**：原设计注解用门面公共名
  `StatusSegment`，实测该 import 本身仍是 L2→L3 向上连线（层秩守卫拦截）——改为
  editor 侧把桥对象适配成 `(id, provider)` 纯数据行（PEP 695
  `type SegmentRow`），statusbar 对 L3 **零 import**。
- [x] Step 2（提交 `3f99d9b`）：`UPWARD_EDGES_FROZEN` 置空集、
  `EXTENSION_SUBMODULE_FROZEN` 删除（直引断言改为零例外）；实测
  pyright 0 errors，架构 + 贡献 + LSP 测试 56 passed。
- [x] Step 3（提交 `27570f7`）：规则文本同步——§一连线图删除 R14 虚线例外边、
  R14 条目与 §六 #30/#32 改为例外清零表述（边界收紧）。
- [x] 全量门禁（主代理亲自跑，均 exit 0）：pyright yate/ + tests/ → 0 errors；
  pytest 全量 --cov-fail-under=75 → 全绿，覆盖率 **92.00%**；
  test_architecture → 35 passed。
