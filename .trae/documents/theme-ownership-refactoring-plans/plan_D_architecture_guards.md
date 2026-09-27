# Plan D — 架构守卫：钉住 T1/T2 治理结果

> 状态：✅ **已完成**（2026-09-27）· 前置：[Plan B](plan_B_scrollbar_injection.md)、
> [Plan C](plan_C_widget_theme_selfhold.md) · 后置：[Plan E](plan_E_gate_docs.md)
> 独占文件：`tests/test_architecture.py`
> 门禁：`pytest tests/test_architecture.py -q` → **20 passed**（原 18 + 本轮 2）

---

## D.1 背景

分层重构的防回归惯例（`architecture-boundaries.md` §六）：**架构测试失败 = 阻塞合并，
不得用豁免注释绕过**。T1/T2 治理是"删除类"改动——删除最怕回归（有人把 patch 加回来、
把 `styles.*` 直改写回去），必须用守卫固化。

## D.2 交付物（2 条新守卫）

### `test_no_class_level_scrollbar_renderer_patch`（钉 T1）

- 扫描 `_yate_files()` 全部源码，正则 `(?m)^\s*ScrollBar\.renderer\s*=` 命中即失败。
- 报错文案指路：`use editor_view.scrollbars.apply_slim_scrollbars(widget)`。
- **实例属性赋值不误伤**：正则锚定行首（`^\s*`），`widget.vertical_scrollbar.renderer = ...`
  这种带接收者的赋值天然不匹配。

### `test_editor_does_not_paint_widget_styles`（钉 T2）

- 对 `yate/editor.py` 源码断言 4 个禁用片段均不存在：
  `def apply_theme`、`def update_sidebar_head`、`.styles.background =`、`.styles.scrollbar_`。
- 报错文案：`widgets paint themselves`。
- **布局属性不误伤**：只禁背景/滚动条着色两类；`Editor` 自有的布局职责
  （terminal dock 高度等）不受影响。

## D.3 设计要点

1. **文本级断言足够**：两条守卫针对的都是"特定写法不得再现"的禁令，正则/子串匹配比
   AST 遍历更直接、失败信息更可读；`test_architecture.py` 既有用例（R1/R5 等）已是同款模式。
2. **`import re` 补齐**：文件原无 `re` 导入，本轮新增。
3. **docstring 引用治理来源**：两条用例的 docstring 均注明
   `review_ui_refine_20260927` + T1/T2 编号，追溯链完整。

## D.4 旧 → 新对照（守护覆盖增量）

| 张力 | 治理前守护 | 治理后守护 |
|---|---|---|
| T1 类级 patch | 无（仅代码评审） | `test_no_class_level_scrollbar_renderer_patch` |
| T2 L3 直改 | 无（仅代码评审） | `test_editor_does_not_paint_widget_styles` |

## D.5 验收证据

- `pytest tests/test_architecture.py -q` → **20 passed**（18 存量全绿 + 2 新增）。
- 守卫有效性隐含验证：若把 `install_slim_scrollbars` 或 `apply_theme` 原样恢复，
  两条用例立即红（正则/子串直接命中历史写法）。
