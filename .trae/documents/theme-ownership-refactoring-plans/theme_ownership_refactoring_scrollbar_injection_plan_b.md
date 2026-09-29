# Plan B — 滚动条 per-widget 注入：删除进程级 monkey-patch（T1 治理）

> 状态：✅ **已完成**（2026-09-27）· 前置：无（与 [Plan A](theme_ownership_refactoring_theme_broadcast_plan_a.md) 可并行）·
> 后置：[Plan D](theme_ownership_refactoring_architecture_guards_plan_d.md)
> 独占文件：`yate/editor_view/scrollbars.py`、`yate/editor_view/{editor,explorer,manual}.py`（仅 `on_mount` 挂载行）、
> `yate/app.py`（仅删除调用）、`tests/test_scrollbars.py`
> 门禁：`tests/test_scrollbars.py` 全过；`ScrollBar.renderer` 类默认在测试中断言**未被改动**

---

## B.1 背景

重构前 `install_slim_scrollbars()` 以 `ScrollBar.renderer = SlimScrollBarRender`
**类属性赋值**实现全局细滚动条（总纲 §2 T1）：进程内所有 Textual App 一律生效、
隐式全局状态、且上游本就提供 per-widget 钩子（总纲 F2）。

## B.2 交付物

| 符号 | 变化 | 说明 |
|---|---|---|
| `install_slim_scrollbars()` | **删除** | 类级 patch 不复存在 |
| `apply_slim_scrollbars(widget: Widget) -> None` | **新增** | 读 `widget.vertical_scrollbar` / `horizontal_scrollbar`（F1：property 首次访问即懒创建并注册）后，用 `setattr` 设**实例** renderer |
| `ScrollBar` 导入 | 移除 | 模块不再引用类，从根上杜绝类级赋值回归 |
| 挂载点 ×3 | 新增 `on_mount` 一行 | `EditorView.on_mount`、`ExplorerTree.on_mount`、`MarkdownDocScreen.on_mount`（`#doc-scroll`）——覆盖全部可滚动 widget（总纲 F6） |
| `YateApp.__init__` 调用 | 删除 | L4 不再发起全局变更 |

## B.3 设计要点

1. **懒创建即触发**：`apply_slim_scrollbars` 内的 property 访问本身就是"取或建"（F1），
   `on_mount` 时机访问安全，无需关心创建顺序。
2. **`setattr` 显式绕过 typing 限制**：上游把 `renderer` 声明为 `ClassVar`，typing 规范不允许
   实例直赋（pyright 会拦）；但 per-widget 覆盖是 Textual **官方文档化用法**
   （`scrollbar.py` docstring 示例）。用 `setattr` + 注释说明理由——不是静默 ignore
   （项目禁止 `# type: ignore`，`cast`/显式表达优先）。
3. **挂载点就近自持**：三个滚动组件在自己的 `on_mount` 调用一行，新滚动组件照抄一行即可；
   动态创建的 widget（分屏 view、`:help` 屏幕）天然被覆盖（各自 mount 时触发）。
4. **行为零变化**：只换绘制的字形（`▐` / `▂` 半格/四分之一格），鼠标元数据原样搬运，
   拖拽/hover/点击滚动全部保留（ui-refine 轮已建立的行为测试不动）。

## B.4 旧 → 新对照

| 旧 | 新 |
|---|---|
| `ScrollBar.renderer = SlimScrollBarRender`（进程级） | 每个滚动 widget 实例属性 |
| `YateApp.__init__` 调 `install_slim_scrollbars()` | 各组件 `on_mount` 调 `apply_slim_scrollbars(self)` |
| 效果：单进程所有 App | 效果：仅 yate 自己的滚动 widget |

## B.6 评审修复（2026-09-27，实现评审发现）

按方案复审实现时发现并修复 `on_mount` 覆写遮蔽问题：

- **本轮引入**：`ExplorerTree.on_mount`（Tree 继承 ScrollView）覆写时未调
  `super().on_mount()`，遮蔽了 `ScrollView.on_mount` 的 `_refresh_scrollbars()`
  （scroll_view.py:58 / widget.py:2078，滚动条**可见性**刷新）——已补 `super()`。
- **存量缺陷顺带修复**：`EditorView.on_mount` 自初始提交起同样缺 `super().on_mount()`
  （此前一直被 `watch_scroll_x/y` + resize 路径掩盖），一并补上。
- 取证：Textual 的 `App`/`Screen` 只有**私有** `_on_mount`/`_watch_theme`（私有 handler
  独立于公开覆写调用），故 `YateApp.watch_theme`、各 Screen 的 `on_mount` 无遮蔽问题；
  `chrome.py` 三个类 / `PromptBar` / `StatusBar` 的 MRO 上不存在公开 `on_mount`，不加
  `@override` 是正确的。
- 复验：pyright（latest 版本）0 errors；pytest 全量绿；`smoke_test compare` exit 0。

## B.7 验收证据

- `tests/test_scrollbars.py::test_install_points_widget_scrollbars_at_slim` 重写为 **pilot 内断言**
  （懒创建需要活跃 App 上下文）：注入后 `widget.vertical_scrollbar.renderer is SlimScrollBarRender`
  且 `widget.horizontal_scrollbar.renderer` 同；**并断言 `ScrollBar.renderer is not SlimScrollBarRender`**
  ——类默认未被改动，进程级 patch 不复存在。
- 架构守卫 [Plan D](theme_ownership_refactoring_architecture_guards_plan_d.md) 的
  `test_no_class_level_scrollbar_renderer_patch` 长期钉住本结论。
- `pyright yate/ tests/ tools/` → 0 诊断；`tools.smoke_test` 滚动条相关场景全过。
