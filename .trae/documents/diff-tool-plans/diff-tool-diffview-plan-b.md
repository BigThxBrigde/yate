# diff-tool-diffview-plan-b（wave-2：L2 DiffScreen / DiffPane）

主计划：[../diff-tool-plan.md](../diff-tool-plan.md) · 总纲：[overview.md](overview.md)
前置：wave-1（plan-a）全部验收通过——本计划 import `yate.editor_core.diff` 的数据类型。

## 输入

- 设计决策 D2/D3/D4/D5/D6（形态、导航、复制、3way、保存守卫）。
- 事实 F3（`_OverlayScreen` 模式：esc/q 基类）、F5（EditorView 的主题自持/滚动条注入/on_key stop 模式，editor_view/editor.py:252-311）、F8（alt 弦记法）。
- `DiffScreen` 是**独立 ModalScreen**，不继承 `_OverlayScreen`（后者绑定 overlay 正文/提示形态；本屏复用其键位精神但结构不同），直接继承 `ModalScreen[None]`。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor_view/diffview.py` | 新增 |
| `yate/resources/diff-view.tcss` | 新增 |
| `tests/test_diffview.py` | 新增 |

## 具体修改

### `yate/editor_view/diffview.py`（新增，~400 行）

依赖：`rich.segment/rich.style`、`textual.*`（ScrollView/ModalScreen/Strip 等）、
`yate.editor_core.buffer`（TextBuffer/Pos）、`yate.editor_core.document.Document`、
`yate.editor_core.diff`（plan-a 全部公共符号）、`yate.keymaps.registry.KeymapSet`、
`yate.paths.load_tcss`、`yate.editor_view.theme`、`yate.editor_view.scrollbars.apply_slim_scrollbars`、
`yate.logs.tracing`（模块级 `log = tracing.get_logger(__name__)`，惰性 %，R12）。
**禁止** import `yate.editor` / `yate.app`（R3）；不新建 Protocol（R2）；无 TYPE_CHECKING（R6）。

#### 数据记录（frozen dataclass，非协议）

```python
@dataclass(frozen=True)
class PaneDiffState:
    """一侧文件的渲染状态，由 DiffScreen 从 L0 结果派生后整体下发。"""
    line_states: tuple[str, ...]      # 每行: "same" | "changed" | "added" | "removed" | "conflict"
    inline: dict[int, tuple[tuple[int, int], ...]]   # 行号 -> 字符高亮区间（仅 replace 型行）
    current_rows: frozenset[int]      # 当前 hunk/region 覆盖的行（加亮）
```

#### `class DiffPane(ScrollView)`（单栏渲染器）

- `can_focus = True`；构造参数：`doc: Document`、`role: str`（"base"/"left"/"right"/"local"/"remote"）、`title: str`、`read_only: bool`，`**kwargs` 透传（id 由 screen 赋）。
- 自持主题（R13，照抄 F5 模式）：`on_mount` → `apply_slim_scrollbars(self)`（实例注入，禁类级 patch）+ `self._apply_theme()` + `self._theme_unsubscribe = theme.subscribe(self._apply_theme)`；`on_unmount` 退订。`_apply_theme` 只改自身 `styles.background/scrollbar_*`。
- 渲染：`@override render_line(y)`——gutter（行号 + `+`/`-`/`!` 徽标）+ 正文；按 `PaneDiffState.line_states[y]` 选主题色背景（新增=green 底/删=red 底/改=yellow 底/冲突=red 加亮、same=无底）；`inline[y]` 区间内字符加 `Style(background=...)` 加深；当前 hunk 行加边框色。字体展开复用 `theme.expand_char` / `theme.char_to_cell`。
- `set_state(state: PaneDiffState)`：整体替换渲染状态 + `refresh()`。
- 键盘（R10 的落实点）：
  - **nav 模式**：不定义 `on_key` 消费——方向键交给 ScrollView 默认滚动，其余键冒泡到 screen BINDINGS（一次派发：冒泡目标只有 screen，modal 期间 `Editor.handle_key` 直返 False，F4）。
  - **edit 模式**（screen 置 `pane.editing = True` 后）：`on_key` 先查模块级键表命中则执行并 `event.stop()` + `event.prevent_default()`；**未命中（含未识别组合键）必须 fall-through 不 stop**（自检清单：历史缺陷"补全弹窗吞全部按键"的反面教材）；esc 退出编辑模式并 stop。
- 编辑键表（模块级函数表，能函数不造类）：`_vsc_edit_keys()` 与 `_vim_edit_keys()` 各返回 `dict[str, Callable[[DiffPane], None]]`：
  - vsc：`up/down/left/right/home/end/backspace/delete/enter` → `buffer.move_*`/`delete_backward`/`delete_forward`/`insert_newline`；单字符打印键 → `buffer.insert_text(ch)`；`ctrl+z` → `buffer.undo()`。
  - vim：normal 子表 `h j k l 0 $ x i a o dd`（`i/a` 切 insert 子模式、`o` 下一行插入、`dd` 用 `delete_lines`）；insert 子表 = 可打印/enter/backspace + `escape` 回 normal。子模式状态存 pane 实例属性。
  - 键表选择：`"vim" if keymaps.name == "vim" else "vsc"`（screen 在进入编辑模式时决定，运行中切 keymap 不热切换——页头提示当前生效键表）。

#### `class DiffScreen(ModalScreen[None])`

- 构造参数：`docs: list[Document]`（2 或 3 个）、`mode: Literal["2way", "3way"]`、`keymaps: KeymapSet`、`labels: list[str]`。
- `DEFAULT_CSS = load_tcss("diff-view.tcss")`（R9：screen 自有资源；内部 id `#diff-header` / `#diff-body` / `#diff-hint` 为 screen 局部 id，先例 `#overlay`，**不改 app.tcss**）。
- `compose()`：`Vertical(#diff-screen)` = `Static(#diff-header)`（路径 + 角色 + modified 徽标 + 键提示）+ `Horizontal(#diff-body)`（2-3 个 `DiffPane`，id `#diff-pane-0..2`）+ `Static(#diff-hint)`。
- 状态：`self._current: int`（当前差异索引，-1 = 无）、`self._regions: list[...]`（2way 存 `DiffHunk`、3way 存 `MergeRegion`）、`self._dirty: bool`（未保存关闭守卫）、`self._editing: bool`。
- `_recompute()`：读各侧 `doc.buffer.lines` → `diff_lines` / `diff3_regions` → 派生各 `PaneDiffState` → `pane.set_state` → `_update_header()`。单侧 > `_MAX_LINES = 20000` 行在构造前由调用方拒绝（本模块导出常量供 plan-c 校验），屏内不做二次防御。
- BINDINGS（screen 级，非 priority——焦点 pane 未消费时才轮到）：

| 键 | action | 行为 |
|---|---|---|
| `alt+up` / `ctrl+up` | `diff_prev` | `_current` 步进 -1（clamp 0，底部提示"no previous change"），各 pane `scroll_to(y=锚点行)`，重发 state（current_rows 变化） |
| `alt+down` / `ctrl+down` | `diff_next` | 步进 +1（clamp 末尾） |
| `alt+right` | `copy_right` | 2way：左→右；3way：local→remote。调 `hunk_replacement` → 目标侧 `buffer.replace_range(...)`（undo 免费）→ `_recompute()`；目标 `read_only` → `BufferReadOnlyError` 捕获 → hint "side is read-only" |
| `alt+left` | `copy_left` | 对称（右→左 / remote→local） |
| `tab` / `shift+tab` | `focus_next` / `focus_prev` | 焦点在 pane 间轮转 |
| `ctrl+1/2/3` | `focus_pane` | 3way 直达 base/local/remote（2way 仅 1/2） |
| `enter` / `e` | `toggle_edit` | 进入/退出焦点 pane 编辑模式（页头显示 `EDIT` 与生效键表名） |
| `ctrl+s` | `save_pane` | 焦点侧 `doc.save()`；成功清该侧 modified、hint "saved"；`read_only` 或 IO 错误 → hint 报错不抛 |
| `ctrl+z` | `undo_pane` | 焦点侧 `buffer.undo()` → `_recompute()`（编辑模式外也可用） |
| `escape` / `q` | `dismiss_guarded` | 有未保存改动（任一侧 `doc.modified`）且非第二次 → 只置 hint "unsaved changes — press esc again to close"；二次（`self._confirm_close` 标志，任何编辑/复制重置）→ `self.app.pop_screen()` |

- 布局细节：nav 模式下 `alt+up/down` 与 pane 内 ScrollView 默认滚动不冲突（alt 弦非 ScrollView 消费键）；普通 `up/down` 滚动仅本侧（非目标 D3：自由滚动持续对齐不做，导航跳转用 `align` 对齐）。

### `yate/resources/diff-view.tcss`（新增）

- `#diff-screen` 填满、`#diff-body { height: 1fr; }` 各 pane `width: 1fr` + 分隔边框、`#diff-header/#diff-hint` 单行 dock；颜色值一律引用 Textual 主题变量（`$background`/`$panel`/`$border` 等）——精确着色由 DiffPane 代码走 `yate.editor_view.theme` 调色板，tcss 只管布局骨架。

### 不修改的文件

`app.tcss`（R9 论证见上）、`editor_view/__init__.py`（保持惰性）、`overlays.py`/`commands.py`（plan-c 范围）。

## 新增测试（`tests/test_diffview.py`）

harness：仓库既有模式 = `textual pilot`（参照 `tests/test_app_textual.py` / textual-pilot-smoke 技能的临时脚本形态）。测试内建最小宿主：

```python
class _Host(App[None]):
    def __init__(self, docs, mode, keymaps): ...
    def on_mount(self) -> None:
        self.push_screen(DiffScreen(self._docs, self._mode, self._keymaps, labels))
```

fixture `make_docs(tmp_path, contents)`：为每份内容落盘临时文件 → `Document.open`。keymap 用 `KeymapSet({"vsc": VscKeymap(), "vim": VimKeymap()}, "vsc")`。

| 用例 | arrange / act | assert |
|---|---|---|
| `test_diff_screen_two_way_composes_two_panes` | 两个差异文件 push 屏 | `app.screen` 为 `DiffScreen`；`len(screen.query(DiffPane)) == 2`；`screen._regions` 长度 == 行级差异数（构造数据恰 1 处 → == 1） |
| `test_diff_screen_three_way_composes_three_panes` | 三个文件 push 屏 mode="3way" | `len(screen.query(DiffPane)) == 3`；regions 含 `conflict` kind（两侧改同一行不同内容） |
| `test_alt_down_steps_hunk_and_scrolls_panes` | 3 处差异、初始 `_current == -1`；`pilot.press("alt+down")` | `screen._current == 0`；两 pane `scroll_offset.y == 0`（首差异在行 0）；再按两次 → `_current == 2`；再按 → clamp 仍 2 且 hint 提示尾部 |
| `test_alt_right_copies_hunk_and_diff_recomputes` | 单 hunk 差异；`pilot.press("alt+right")` | 右侧 doc 行内容 == 左侧对应行；重算后 `screen._regions == []`；右侧 `doc.modified is True` |
| `test_alt_left_copy_into_readonly_side_refused` | 左侧 doc `buffer.read_only = True`；`press("alt+left")` | 左侧行内容不变；hint 文本包含 "read-only"（screen 可查 `_hint_text()` 或 hint Static 的 renderable） |
| `test_edit_mode_types_into_focused_buffer` | nav 下 `press("enter")` 进入编辑 → `press("x")` | 焦点 pane 对应 doc 的光标行含 `"x"`；`_recompute` 后 regions 反映新文本 |
| `test_edit_mode_esc_returns_to_nav_and_unmapped_key_falls_through` | 编辑模式中 `press("escape")` 后 `press("q")` | 屏仍开着（`app.screen is screen`，q 未触发关闭——编辑模式不吞 nav 键）；再 `press("escape")` 走关闭守卫路径 |
| `test_unsaved_close_requires_second_escape` | 编辑输入 1 字符后 `press("escape")` ×1 | `app.screen is screen`（未关）；再 `press("escape")` → screen 已 pop（`app.screen is not screen`） |
| `test_ctrl_s_saves_focused_pane_document` | 复制产生 modified 后 `press("ctrl+s")`，读回临时文件内容 | 磁盘文件含复制后的行；`doc.modified is False` |
| `test_vim_keymap_edit_table_moves_with_hjkl` | `KeymapSet(..., "vim")` 构造屏；`press("enter")` 后 `press("j")` | 焦点 doc buffer cursor 行号 +1（vim 键表生效的证据） |
| `test_oversized_file_rejected_constant` | `DiffScreen` 构造前调用模块级 `_check_sizes([lines]*2)`（>20000 行） | 返回错误消息字符串 / 抛 `ValueError`（以导出 API 为准断言） |

## 验证方案

```powershell
.venv\Scripts\python.exe -m pytest tests/test_diffview.py -q
python -m pyright yate/editor_view/diffview.py tests/test_diffview.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q   # R3/R13/R10 静态面回归
```

- 通过判定：退出码 0；架构守卫 22 用例不因新文件变红（`editor_view/*` 不 import 上层由 `test_editor_view_does_not_import_upward` 自动覆盖新文件）。
- 手工验证（无法自动化部分）：`python -m yate` 打开编辑器后本波次尚无入口（plan-c 才接 `:diff`）——本波以临时脚本经 `_Host` 目视检查：diff 底色、当前 hunk 加亮、CJK 宽字符列对齐（`theme.expand_char` 路径）、深浅主题各切一次（`:theme` 不适用本屏——临时脚本内 `theme.set_theme` 后观察重绘）。

## 风险与回滚

- R-2 大文件阻塞：`_MAX_LINES` 常量拒绝（测试锁定）；后续可改 worker。
- R-10 键面回归：编辑键表 miss 必须 fall-through；负向用例 `test_edit_mode_esc_returns_to_nav_and_unmapped_key_falls_through` 锁定。
- 回滚：纯新增文件 revert 即可；`diff-view.tcss` 为独立资源无交叉引用。

## 执行记录（2026-10-02，plan-executor）

### 验收结果（实测，均在 worktree `D:\Programming\yate-diff-tool`，分支 `feat/diff-tool`）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests/test_diffview.py -q` | `11 passed` | 0 |
| `python -m pyright yate/editor_view/diffview.py tests/test_diffview.py` | `0 errors, 0 warnings` | 0 |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | `22 passed` | 0 |

### 实际改动

- `yate/editor_view/diffview.py` 新增（~1010 行）：`MAX_DIFF_LINES`、`check_sizes`、`_replacement_triple`、
  `_undo`、编辑键表三函数、`PaneDiffState`、`DiffPane`（`PaneChanged` 消息 / `render_line` / nav-edit 双模式 `on_key`）、
  `DiffScreen`（BINDINGS 17 条 / `_recompute` / 2way+3way 复制 / 编辑 / 保存 / 撤销 / 两段关闭守卫）。
- `yate/resources/diff-view.tcss` 新增：布局骨架，全部 `DiffScreen` 前缀选择器（先例 `overlay-screen.tcss`），
  颜色全走主题变量；未改 `app.tcss`。
- `tests/test_diffview.py` 新增：11 用例（pilot `_Host` 宿主），全部通过。

### 偏离记录（附实测依据）

1. **执行位置**：会话启动于 master 主仓库目录，实际 worktree 为 `D:\Programming\yate-diff-tool`
   （`git worktree list` 实证），全部工作在该 worktree 完成。
2. **`_MAX_LINES` → `MAX_DIFF_LINES`**：子计划 62 行写 `_MAX_LINES`，按任务书"导出供 plan-c 校验"落实为公开常量。
3. **`_check_sizes` → `check_sizes`（公开名）**：pyright strict `reportUnusedFunction` 拦截"私有名且模块内零调用"
   （实测诊断原文：`无法存取函数"_check_sizes" (reportUnusedFunction)`）；该函数本就是 plan-c 的外部接口，改公开名，
   不用 `# pyright: ignore`（风格规则 §4.2 禁止）。
4. **复制链路补 `_replacement_triple` 包装**（重要，建议主代理裁定是否回修 wave-1）：
   `hunk_replacement` 的中段三元组（`t_end < line_count`）text 不带尾 `\n`，而
   `TextBuffer._delete_range` 对 `(t_start,0)-(t_end,0)` 会消费被替换段末尾换行——直接回放把下一行并入替换文本
   （实测：`["one","TWO","three"]` 应用 `((1,0),(2,0),"two")` 得 `["one","twothree"]`）；
   纯插入子段（`t_start==t_end` 且中段）同样缺尾 `\n`。EOF 两分支实测正确（`_delete_range` 终点取行尾、
   尾行内容充当拼接载体）。wave-1 锁定测试只断言三元组形态、未回放，故未暴露。
   修复落在本波独占文件内：`_replacement_triple` 调 L0 后按 `t_end < len(target)` 且 text 非空补尾 `\n`；
   **未改** `yate/editor_core/diff.py`（非本波独占文件）。
5. **`dismiss_guarded` 无条件两段式**：第一次 esc/q 总置 `_confirm_close` + hint（dirty → "unsaved changes — ..."，
   非 dirty → "press esc again to close"），第二次才 pop。子计划 76 行只规定 dirty 分支、未明文规定无 dirty 行为，
   字面实现（非 dirty 直接 pop）会使用例 7 的"q 后屏仍开着"断言矛盾；本实现使 7/8 两用例断言全部按字面通过。
6. **用例 4 act 补 arrange 键 `alt+down`**：`_copy` 在 `_current == -1` 时 hint "no change selected"
   （D4 语义"当前差异"要求先选中）；偏离用例 act 字面，plan 文字只写 `press("alt+right")`。
7. **用例 6 断言修正**：计划只要求"regions 反映新文本"；原写 `len(_regions) == 2` 在两行文档上不可达
   （"xone" vs "one" 与 "two" vs "TWO" 相邻差异合并为单一 `(0,2,0,2)` replace hunk，实测）。改为断言
   hunk 边界由 `(1,2)` 变 `(0,2)`，即重算真实反映了键入。
8. **用例 9 补 `tab` 移焦**：计划 BINDINGS 表中 alt+right 无焦点移动语义，焦点仍在 pane 0，ctrl+s 存"焦点侧"
   → 测试在复制后按 tab 聚焦目标侧再 ctrl+s；未擅自给复制加焦点移动行为。
9. **3way 复制**：将 `MergeRegion` 的源/目标区间打包成临时 `DiffHunk` 复用 `hunk_replacement`（含上面的
   `_replacement_triple` 修正），EOF 边界处理免费获得。
10. **新增 `DiffPane.PaneChanged(Message)`**：pane → screen 的编辑/内容变化通知（Textual 标准消息机制），
    screen 收到后 `_recompute`；仅在 `content_version` 或 `editing` 变化时发送，光标移动键不触发 O(N) 重算。
    子计划未规定重算触发机制，此为落实"`_recompute` 反映编辑"的最小实现。
11. **`check_sizes` 返回 `str | None`**：计划 113 行"返回错误消息字符串 / 抛 ValueError（以导出 API 为准断言）"
    二选一，取返回值形态。
12. **渲染细节**：行底色用 `Color.blend`（状态色按 `_TINTS` 强度混入 bg，conflict 0.45 最强）；changed 徽标用
    `~`（计划 46 行只列 `+`/`-`/`!` 三个符号，但 `line_states` 有 5 种状态，replace 型需第四符号）。
13. **命名与注解（pyright strict 实测驱动）**：`enter_edit_mode`/`exit_edit_mode`/`vim_insert`/`pending_d`
    用公开名（`reportPrivateUsage` 实证跨对象访问即公共面）；`**kwargs: Any`（仓库先例 editor.py:154 等 8 处）；
    DiffScreen.on_mount 不加 `@override`（Screen 无该基方法，先例 screensaver.py:140；DiffPane.on_mount 保留，
    ScrollView 有基方法）；关闭走 `self.dismiss(None)` 而非 `self.app.pop_screen()`
    （ModalScreen 自有 API，避免 L2 持 App 句柄）。
14. **vsc 键表 `ctrl+z`**：`buffer.undo()` 返回 bool，键表值类型 `-> None`，加 `_undo` 适配函数。

### 遗留与移交

- 偏离 4 的 L0 语义缺口（`hunk_replacement` 中段三元组直接回放会并行）建议主代理裁定：要么回修
  `yate/editor_core/diff.py`（plan-a 范围，其锁定测试需同步加"回放断言"），要么维持现状
  （调用方包装）；本波已在消费侧修复并有测试锁定（用例 4）。
- 手工验证项（计划"验证方案"节）：CJK 宽字符列对齐、深浅主题切换重绘——本波无入口（plan-c 接 `:diff`），
  以临时脚本目视验证属主代理收尾事项；自动化面已由 11 用例覆盖。
- 未执行 `git commit`（按任务书由主代理统一提交）。

### 裁定结果（主代理，wave-2 收口前）

- 已回修 L0：`hunk_replacement` 中段分支补尾 `\n`（text 非空时），见 plan-a
  「执行记录·裁定回修」；本模块 `_replacement_triple` 包装删除，3 处调用点直调
  `hunk_replacement`（diffview.py:869/874/906 附近）。
- 回修后复测：`pytest tests/test_editor_core_diff.py tests/test_diffview.py -q`
  → 25 passed（L0 14 + L2 11）；pyright 三文件 0 errors；架构测试 22 passed。
