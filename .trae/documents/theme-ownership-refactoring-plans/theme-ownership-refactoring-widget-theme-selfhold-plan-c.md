# Plan C — 七组件自持主题：删除 `Editor.apply_theme`（T2 治理）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 后置：[Plan D](theme-ownership-refactoring-architecture-guards-plan-d.md)
> 独占文件：`yate/editor_view/{editor,explorer,commandline,chrome,statusbar}.py`、
> `yate/editor.py`、`yate/app.py`
> 门禁：主题广播探针（§C.5）六处 styles 断言全等；pyright 0 诊断；pytest 全量绿

---

## C.1 背景

重构前 `Editor.apply_theme`（`yate/editor.py:1143-1177`，总纲 F3）是 L3 直改面的集中体现：
`app.screen.styles.background`、每个 view 的 bg + `apply_scrollbar_theme` + `content_changed`、
explorer 的 6 项 scrollbar 样式、`prompt_bar.styles.background`、`status_bar.refresh_status()`、
`update_sidebar_head()`、`tabbar.refresh_tabs()`、`breadcrumbs.refresh_crumbs()`。
调用点仅 2 处：启动（`:260`）与 `set_theme`（`:1140`，总纲 F4）。

L2 组件自持先例已存在（总纲 F5）：`EditorView.on_mount` 自己读 `theme.active()` 上色；
`StatusBar.refresh_status` 等本来就是组件自持刷新、L3 只是触发。本轮把"触发"也还给组件。

## C.2 交付物（自持组件清单）

| 组件（L2） | 自持的 `_apply_theme` 内容 | 订阅方式 |
|---|---|---|
| `EditorView` | bg + `apply_scrollbar_theme()` + `content_changed()` | `on_mount` 先执行一次再订阅；`_theme_unsubscribe` 属性持退订钩子 |
| `ExplorerTree` | 6 项 scrollbar 样式（track 全透明 / thumb border 色 / hover 提亮 / active accent）+ `refresh_tree()` | 同上；`on_mount` 补 `@override`（pyright strict） |
| `PromptBar` | bar + message/prompt/input 四处 `styles.background` | 同上（收编原 `on_mount` 直写段） |
| `SidebarHead`（新增类） | panel 背景 + `sidebar_head_text()` 粗体标题 | 替代原 `yate/editor.py` 里的裸 `Static` + L3 `update_sidebar_head()` |
| `TabBar` | `refresh_tabs()` | `on_mount` 订阅 `refresh_tabs`（现成自持方法） |
| `Breadcrumbs` | bg + 重渲染 | bg 直写从 L3 移入 `refresh_crumbs()`；订阅之 |
| `StatusBar` | `refresh_status()` | 订阅现成自持方法 |

统一模式（每个组件三件套）：

```python
_theme_unsubscribe: Callable[[], None] | None = None   # None = 未挂载

def on_mount(self) -> None:
    self._apply_theme()                                 # 先自取当前主题（动态创建兜底）
    self._theme_unsubscribe = theme.subscribe(self._apply_theme)

def on_unmount(self) -> None:
    if self._theme_unsubscribe is not None:
        self._theme_unsubscribe()
        self._theme_unsubscribe = None
```

## C.3 L3 / L4 侧的收缩

| 位置 | 变化 |
|---|---|
| `yate/editor.py::apply_theme` | **删除**（用户决策：彻底删除，不留薄壳） |
| `yate/editor.py::update_sidebar_head` | **删除**（职责整体归 `SidebarHead`） |
| `yate/editor.py` 启动路径 `apply_theme()` 调用 | 删除（组件 mount 时自取主题） |
| `yate/editor.py::set_theme` 内 `apply_theme()` 调用 | 删除（`theme.set_theme()` 内部已广播；L3 只剩校验 + 主题桥 + `app.theme` 赋值 + 用户提示） |
| `yate/editor.py` 导入清理 | `textual.color.Color`、`textual.widgets.Static` 移除；`chrome` 导入改为 `Breadcrumbs, SidebarHead, TabBar` |
| `yate/app.py::watch_theme` | **新增**（L4 自持）：screen 是外壳唯一拥有的表面，主题 reactive 变化时刷 `screen.styles.background`；挂载前 no-op（`screen_stack` 空判断） |
| `yate/app.py::on_mount` | 补一次 `screen.styles.background = theme.active().bg`（`watch_theme` 对挂载前赋值不触发，启动屏需补刷） |

## C.4 设计要点

1. **`on_mount` 先自取再订阅**：顺序保证"先画一次、再听后续"，动态创建的 view（分屏、
   `:theme` 切换后新开的 leaf）不依赖错过与否广播。
2. **`watch_theme` 的挂载前 no-op**：Textual reactive watcher 在 `super().__init__()` 内的
   初始赋值阶段就可能触发，此时 `screen_stack` 为空——判空跳过，`on_mount` 补刷。
3. **`content_changed()` 归位**：原由 L3 对每个 view 调用；现属 `EditorView._apply_theme`
   内部（它是"主题变了 → 重新计算渲染几何"的组件内部反应）。
4. **订阅现成方法而非包一层**：`StatusBar`/`TabBar` 的 `refresh_status`/`refresh_tabs`
   已是自持刷新，直接作为 listener 传入，不新增间接层。

## C.5 验收证据（一次性 pilot 探针，临时脚本已删）

对 `YateApp`（`run_test(size=(100, 30))`）断言，mocha → `set_theme("latte")` → mocha 往返：

| 断言点 | 内容 |
|---|---|
| `prompt_bar.styles.background` | == `Color.parse(t.panel)`，切换后 == `Color.parse(t2.panel)` |
| `sidebar_head.styles.background` | 同上（panel） |
| `app.screen.styles.background` | == `t.bg` → `t2.bg` |
| `status_bar.styles.background` | == `t.accent` → `t2.accent` |
| `view.styles.background` | == `t.bg` → `t2.bg` |
| `tree.styles.scrollbar_color` | == `Color.parse(t.border)` → `t2.border` |

全部命中 → **"THEME BROADCAST OK"**；架构守卫 `test_editor_does_not_paint_widget_styles`
（Plan D）长期钉住"editor.py 直改面清零"。

## C.6 行为等价性

视觉表现零变化：各组件 `_apply_theme` 的赋值内容与原 `apply_theme` 对应行逐一相同
（仅位置搬运）；`tools.smoke_test` 全场景 check 100% 通过（总纲 §1.2）佐证无回归。
