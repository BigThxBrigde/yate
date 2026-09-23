# 编辑器窗格分割（vim :split / :vsplit）实现方案

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - 纯数据模型抽到 `yate/editor_view/pane_types.py`（`Leaf` / `Split` / `Node` /
>   `ViewState` 与树工具），Textual 侧为 `yate/editor_view/panes.py`
>   （`PaneManager` + `PaneHost`）；`EditorView` 已参数化 `leaf_id` 与宿主，
>   焦点切换经 `PaneManager.capture_active()` / `apply_doc()` 同步视图状态
>   （同文档多窗格光标/选区/滚动独立）。
> - 命令已在 `app_features/commands.py` 注册：`:split` / `:sp`、
>   `:vsplit` / `:vs`、`:only`、`:close`；vim NORMAL 下 `Ctrl+W` 和弦
>   （`s`/`v`/`q`/`o`/`h-j-k-l`/`+ - < >`/`=`）已在 `app.py` 接线。
> - 测试：`tests/test_panes.py`（模型）+ `tests/test_app_textual.py`（pilot）已覆盖。
> - 与本文档的差异：`Leaf.states` 的键**不是** `id(doc)`，而是稳定的
>   `Document.uid`（`pane_types.py::Leaf.state_for`，注释说明用于规避文档重建
>   导致的键失效，见 `remove_type_checking_review_v3.md`）；`PaneManager`
>   构造为 `PaneManager(session: EditorSession, doc: Document, ...)`（2026-09-23
>   更新：不再使用 `AppProtocol`，改为具体对象注入），Textual 宿主类为
>   `yate/editor_view/panes.py::PaneHost`（`reconcile` 目前是整树重建，文件内
>   留有 `TODO(perf)`）。

## 需求（已与用户确认）

- 范围：基础窗格 + 调整大小。`:split`/`:vsplit`（别名 `:sp`/`:vs`）、`:only`；vim NORMAL 下 `Ctrl+W` 和弦；`:q`/`Ctrl+W q` 关窗；窗格间方向导航与尺寸调整。
- 新窗格：无参数 = 复制当前 buffer（vim 默认）；`:sp path` 在新窗格打开指定文件；文件树/文件列表打开文件进入活动窗格。
- 同一文件多窗格时，**各窗格独立光标/选区/滚动**（vim 语义）。

## 仓库调研结论

- 布局：[app.py](yate/app.py#L1874-L1889) `compose()` 为 `Horizontal#body > [Vertical#sidebar(explorer) + Vertical#editor-col(tabbar/breadcrumbs/EditorView#editor)]`；终端面板与状态栏在下方 dock，不受影响。
- 全应用只有**一个** `EditorView`，`app.editor_view` 被约 30 处直接引用；`EditorView.buffer` 取 `yate.buffer`（全局活动文档），渲染（gutter/选区/光标/搜索高亮/LSP 标记）全部基于它。
- 文档模型：`app.docs: list[Document]` + `app.doc_index`；`Document` 持 `TextBuffer`；**光标 `buf.cursor` 与选区 `buf.anchor` 在 buffer 内**；滚动状态 `scroll_col`/`scroll_offset` 在 EditorView（天然按视图独立）。打开同路径文件复用已有 Document（[app.py L267-305](yate/app.py#L267-L305)）。
- 已有 vim 窗格和弦体系：`try_window_prefix()`/`_window_navigate()`（[app.py L631-671](yate/app.py#L631-L671)），现仅支持 `h/l`（explorer↔editor）与 `Ctrl+W Ctrl+W` 循环，`j/k` 为 no-op；仅 vim NORMAL 生效。vsc 键位中 `Ctrl+W` 是关闭标签，**不占用**。
- 命令注册：`_register_commands()` 单参数 lambda（[app.py L1475-1508](yate/app.py#L1475-L1508)）；`:q` 当前直接 `quit()`，`quit()` 对**所有** docs 做 dirty 统一拦截（L1747-1752）。
- 补全弹窗 `CompletionPopup` 挂在 `#editor-col`，offset 由调用方按活动视图几何计算（`app.editor_view` 改为活动视图 property 后自动跟随）。
- Textual 不能给已挂载 widget 换父容器 → 结构变更采用"卸载旧叶子视图、原位挂载 SplitBox 装两个新视图"的增量方式；EditorView 是轻量可重建部件，所有跨重建状态（文档绑定、光标/选区快照）外置到模型。

## 设计

### 1. 新模块 `yate/editor_view/panes.py`

- `ViewState` dataclass：`cursor: Pos`、`anchor: Optional[Pos]`。滚动留在 widget，不进 ViewState。
- 模型树（纯 Python，可单测）：
  - `Leaf(id: int, doc: Document)`，自带 `states: dict[int, ViewState]`（按 `id(doc)` 保存该窗格在各文档上的视图状态）；
  - `Split(axis: Literal["horizontal","vertical"], sizes: list[float])` + children：`horizontal` = 上下（`:split`，Textual `Vertical`），`vertical` = 左右（`:vsplit`，`Horizontal`）；`sizes` 为分数，resize 时守恒并钳制最小值（如 0.1）。
- `PaneHost(Widget)`：
  - 初始挂载单叶子 EditorView；
  - `split(leaf, axis, doc, *, clone)`：模型替换节点；DOM 上 unmount 旧 EditorView、原位 mount SplitBox（两个**新建** EditorView，新叶子继承旧叶子 states 与滚动位置）；
  - `close(leaf)`：父 Split 用兄弟节点替换（兄弟为 Split 时提升），DOM 同步；根叶子的关闭由 app 走退出/标签关闭流程；
  - `only(leaf)`：重建为单叶子树（保留各文档绑定与 states）；
  - `focus(direction)`：基于各叶子 widget 的 `region` 做几何最近邻导航（h/j/k/l）；左侧无编辑窗格时返回 `None`，由 app 转交 explorer（保留现 `Ctrl+W h` 语义）；
  - `resize(leaf, axis, delta)` / `equalize(leaf)`：调所属同轴向 Split 的分数并应用 `styles.width/height` 百分比；
  - `active_leaf`/`active_view`：由 EditorView `on_focus` 上报维护；`views_for(doc)` 供联动刷新。

### 2. `yate/editor_view/editor.py` 改造

- 构造增加 `leaf_id`；`doc`/`buffer` 属性解析为叶子绑定文档（不再取全局活动文档）。
- 渲染光标/选区：活动叶子（`host.active_view is self`）读 `buf.cursor`/`buf.anchor`；非活动叶子读该 `(leaf, doc)` 的 ViewState 快照。搜索高亮/诊断标记按叶子自身文档渲染。
- `on_focus` → 通知 host：app 依次完成 ①旧活动叶子把 `buf.cursor/anchor` 存入其 states；②切换 `doc_index` 到新叶子文档；③把该叶子 ViewState 写回 `buf.cursor/anchor`；④恢复滚动、vim 模式显示、刷新 tabbar/面包屑/状态栏。
- `on_blur` 不需处理（统一在 focus 切换点同步）。

### 3. `yate/app.py` 接线

- `compose()`：`#editor-col` 内以 `PaneHost` 替换裸 `EditorView`（tabbar/breadcrumbs/popup 挂载点不变）；`app.editor_view` 从实例属性改为 **property → host.active_view**；`mounted` 判定随之适配。
- 打开/新建/循环文档（`_open_document_path(_async)`、`open_path(_later/async)`、`new_buffer`、`cycle_tab`）语义从"全局切换活动文档"改为"**改绑活动叶子**"，并同步 `doc_index`；其他叶子不动。内部打开函数增加 `target_leaf` 形参（默认活动叶子），供 `:sp path` 落到新叶子。
- `close_tab()`（`:bd`）：关闭文档后，活动叶子改绑剩余文档；**所有**绑定该文档的叶子一并改绑；docs 清空时仍建 scratch（现有兜底）。
- 关窗语义（vim）：
  - 多窗格时 `:q`/`:quit`/`Ctrl+W q` = 关闭活动窗格，文档保留为隐藏 buffer（不拦 dirty——最终 `quit()` 仍对全部 docs 统一 dirty 检查，行为不回退）；
  - 仅一个窗格时 `:q` 维持现有退出流程；`:q!` 维持强退；`:wq` 不变。
- 新命令：`split`/`sp`、`vsplit`/`vs`（可选路径参数；相对路径优先相对当前文档目录、其次 cwd；目录参数转交文件夹打开逻辑）、`only`。
- 和弦扩展（仅 vim NORMAL，沿用 `try_window_prefix`）：`s`=:split、`v`=:vsplit、`q`=关窗、`o`=:only、`h/j/k/l`=几何方向导航、`Ctrl+W`=explorer↔各编辑窗格循环、`+`/`-`=活动窗格高度增减、`<`/`>`=宽度增减、`=`=等分；更新待命提示文案。
- `ui_refresh()`：活动视图 `content_changed()`，并对所有显示同一文档的视图刷新（编辑/搜索/LSP 诊断联动）。逐个审计现有约 30 处 `editor_view` 引用，区分"作用活动窗格"（保存/打开/补全几何）与"作用全部相关窗格"（内容变更刷新）。
- 文件树/`Ctrl+P`/命令面板打开文件：进入活动叶子（改绑后与现体验一致）。

### 4. CSS

SplitBox（Horizontal/Vertical 容器）与子 EditorView：`width/height: 1fr/100%`、padding 0、无外框。窗格间默认**不画分隔条**（省终端空间，对齐 vim）；若实测辨识度不足，再加 1 行/列 panel 底色分隔（实施时决定，属视觉微调）。

## 文件与模块

- 新增 `yate/editor_view/panes.py`：ViewState、叶子/分割模型、PaneHost（约 300 行）。
- 改 `yate/editor_view/editor.py`：叶子绑定、ViewState 渲染、focus 上报。
- 改 `yate/app.py`：compose/property、文档绑定与打开关闭流程、新命令、和弦与 resize、刷新联动（主工作量）。
- 新增 `tests/test_panes.py`：模型与尺寸分数纯逻辑测试。
- 改 `tests/test_app_textual.py`：新增 `PanesTests`（pilot 端到端）。
- 双语文档：`yate/resources/manual.zh.md`、`manual.en.md`（窗格管理小节、ex 命令表、快捷键总表）；检查并同步 `yate/docs/yaterc.zh.md`/`.en.md` 与 README 两份的功能/键位描述。

## 实施顺序

1. `panes.py`：ViewState + 树模型（split/close/only/resize 分数/导航顺序），纯模型先行。
2. PaneHost 的 Textual 容器增量维护 + EditorView 参数化（leaf_id、doc 绑定、focus 上报）。
3. app：compose/property/focus 切换同步（光标/anchor/doc_index/滚动/模式/状态栏）。
4. 文档打开/新建/循环/`:bd` 改为叶子绑定；逐点审计 editor_view 引用。
5. `:split`/`:vsplit`/`:only` 命令与路径解析；`:q` 关窗语义。
6. `Ctrl+W` 和弦全套（s/v/q/o/hjkl/cycle/resize/equalize）。
7. ui_refresh/LSP 回调/搜索/补全几何的多窗联动审计；CSS。
8. 测试：test_panes.py + PanesTests pilot 用例。
9. 双语文档同步。

## 验证

- 新增 `tests/test_panes.py`：split 树结构、close 折叠与 Split 提升、only 保留文档与状态、resize 分数守恒/最小钳制/等分、叶子导航顺序。
- pilot 用例：
  - `:vsplit` 后两视图内容一致；右窗 `j` 移动后左窗光标不变（独立 ViewState），各自滚动独立；
  - `:sp path` 新窗为另一文件，内容/面包屑随焦点切换；
  - `Ctrl+W` 和弦（vim 键位）s/v/h/j/k/l/q/o 与 cycle；`h` 在最左编辑窗格落到 explorer；
  - `:q` 多窗关窗不退出、单窗维持退出；`:only`；
  - `+/-/< >/=` 后容器宽高百分比生效；
  - `:bd` 关闭多窗共有文档后各叶子正确改绑；隐藏 buffer 有改动时 `:q` 退出仍被 dirty 拦截。
- pyright strict 0/0；全量 `pytest tests`（当前 296 个 + 新增）通过。
- 不涉及打包/frozen 路径，无需重建产物。

## 风险与处理

- EditorView 结构变更时重建：焦点丢失/异步 mount——所有操作经 host async 方法完成后显式 focus 目标叶子；pilot 测试 `pause()` 后断言。
- ViewState 与 buffer 不同步：唯一写入点是 focus 切换与编辑命令（编辑只发生在活动叶子）；undo/redo 改变 buf.cursor 后活动叶子直接以 buffer 为准，切走时快照即最新位置。
- 约 30 处 `editor_view` 引用语义漏改：按"活动 vs 全部相关"逐点 grep 审计，pilot 覆盖编辑联动（同文档两窗输入同步、光标独立）。
- 终端面板、Manual/Help/Output/Palette 覆盖屏走 screen stack，不经过窗格体系，零影响。
- vsc 键位用户只有 ex 命令入口（Ctrl+W 保留为关标签）；如后续需要可再配 vsc 和弦，不在本次范围。
