# plan-d：L2 FileManagerScreen 组件（wave-3）

## 输入
总纲 §四/§六；plan-a EntryStat；plan-b preview.py；plan-c filemgr_model.py。
先例基线：`PaletteScreen(ModalScreen[None])`（palette.py:145-204：BINDINGS escape/
ctrl+c、`DEFAULT_CSS = load_tcss("palette-screen.tcss")`、构造全注入、
预览 worker `run_worker(..., group=..., exclusive=True, exit_on_error=False)`）；
explorer 的键位/主题/滚动条（explorer.py:348-403 on_key、242-253 attach/detach）；
`PreviewLog` / `PreviewData` / `PreviewCache` / `load_preview_worker`（plan-b 产物）；
`fuzzy_match` 不用（plan-c 子串过滤）。`Workspace.list_dir/invalidate/show_hidden/
stat_entry/create_entry/rename_entry/remove_entry/copy_entry/move_entry/list_drives`。

## 目标
三栏 lf 布局的 `FileManagerScreen(ModalScreen[None])`：左=父目录/盘符、
中=当前目录、右=预览（语法高亮），底部过滤/输入行 + 状态栏；全部 P0/P1 键位；
鼠标单击/双击/滚轮；R13 主题自持 + R15 细滚动条；浮层/全屏双形态仅 CSS 类差。

## 独占文件清单
- `yate/editor_view/filemgr.py`（新建；目标 <700 行，超标先拆 `filemgr_keys.py`
  键位表并在回报中说明）
- `yate/resources/filemgr-screen.tcss`（新建）
- `tests/test_filemgr.py`（新建）

## 组件设计

### 构造注入（R3 红线：只收具体协作者与回调）
```python
class FileManagerScreen(ModalScreen[None]):
    def __init__(
        self, *,
        workspace: Workspace,
        preview: FilePreviewConfig,
        open_selected: Callable[[list[Path]], None],   # flows 编排（含 Q1/Q2 语义）
        close: Callable[[], None],                     # 浮层=pop_screen；全屏=exit_app
        fullscreen: bool = False,
        initial_dir: Path | None = None,               # 默认 workspace.root 或 cwd
    ) -> None: ...
```
`open_selected` 传**选中集**（list[Path]，单选=1 元素）；Q1 dirty 确认/Q3 关闭时序
都在 flows 侧（screen 先 `self.dismiss()` 再调 `open_selected`——对齐 palette
`_choose` 先例 palette.py:639-671）；全屏退出 `close` 由 flows 注入 `exit_app`。
screen 自身**不做**工作区切换/保存判断（编排归 L3）。

### compose（id 前缀 `filemgr-`，不进外壳 app.tcss——自有 tcss）
```text
#filemgr (Vertical, .fullscreen 可选)
├── #filemgr-body (Horizontal)
│   ├── #filemgr-parent  (ListView, can_focus=False)
│   ├── #filemgr-list    (ListView)        ← 焦点栏
│   └── #filemgr-preview (PreviewLog, can_focus=False)
├── #filemgr-input (Input, 占一行, 默认隐藏)
└── #filemgr-status (Static)
```
`DEFAULT_CSS = load_tcss("filemgr-screen.tcss")`：浮层 `#filemgr { width: 90%;
height: 80%; }` 居中（ModalScreen 默认遮罩）；`.fullscreen #filemgr { width: 100%;
height: 100%; }`（对齐 palette `.with-preview` 类切换先例）；三栏宽
`1fr 2fr 2fr`；`Widget { scrollbar-size-vertical: 1 }` 由组件 tcss 自声明。

### 状态
- `_cwd: Path`、`_entries: list[Entry]`（当前目录过滤后）、`_stats`、
  `_rows: list[RowSpec]`、`_sort: SortKey = "name"`、`_desc: bool = False`、
  `_filter: str | None`、`_marked: set[Path]`、`_clipboard: tuple[Path, bool] | None`
  （(path, is_cut)）、`_dir_memory: dict[Path, Path]`（h 返回时光标落原目录）、
  `_preview_cache = PreviewCache()`、`_g_pending: bool`（gg 序列）。

### 刷新管线（目录切换/过滤/排序/标记共用）
`_reload(keep: Path | None = None)`：
1. `_entries = filter_entries(workspace.list_dir(_cwd), _filter or "")`；
2. `_stats = {e.path: workspace.stat_entry(e.path) for e in _entries}`（一次循环）；
3. `sort_entries(...)` → 每行 `build_row_text(...)`（目录行附
   `count_children`）；ListView `clear()` + 批量 `extend(ListItem(Static(text)))`；
4. `_refresh_preview()` + `_refresh_status()`；`keep` 恢复光标（`h` 返回 lf 语义）。
预览：对齐 palette `_update_preview`（390-416）：cache get（mtime+size 复验）→
miss 时 `run_worker(partial(load_preview_worker, path, cfg), group="filemgr-preview",
exclusive=True, exit_on_error=False)`；worker 回调渲染到 `#filemgr-preview`；
目录 → 直接渲染子项列表（`list_dir` 前 N=100 项）；盘符/根 → 占位文本；
二进制/超大 → PreviewData.note 原样显示（管线自带降级）。

### 键位（BINDINGS 为主 + on_key 处理 g 序列；焦点在 #filemgr-list）
- BINDINGS（action 名蛇形）：`j/down`/`k/up`（ListView 内建 cursor，仅补映射）；
  `l/enter/right → action_open`；`h/left/backspace → action_up`；
  `G → action_bottom`；`end/home`；`ctrl+d/ctrl+u → action_half_page(±)`；
  `slash/question_mark 不占用`（`/` 走 on_key 或 binding `slash` → action_filter）；
  `f → action_filter`；`h 大写 H? 不——`**大小写敏感**：`H → action_toggle_hidden`、
  `period(".") → action_toggle_hidden`；`s → action_cycle_sort`；
  `r → action_refresh`；`f5 → action_refresh`；`space → action_mark`；
  `v → action_invert_marks`；`escape → action_escape`（两级退出/关浮层）；
  `q → action_quit`；`a → action_new_file`；`A(shift+a) → action_new_dir`；
  `R → action_rename`；`d → action_delete`；`y → action_yank`；`x → action_cut`；
  `p → action_paste`；`g` 不进 BINDINGS（on_key 状态机：`g` 后等 `g` → Home，
  超时/其他键复位）。
- `Input` 聚焦时（过滤/prompt 模式）：`Esc` 退出模式、`Enter` 提交 prompt、
  其余键归 Input（Textual 焦点语义天然成立）。
- **过滤模式**：`Input.value` changed → `filter_entries` 实时收窄（复用 `_reload`
  轻量路径：仅重过滤+重渲染，不重 stat）；`Esc` 清 `_filter` 并隐藏 Input。
- **prompt 模式**（a/A/R/d/y 冲突/粘贴冲突共用）：placeholder 提示，Enter 提交 →
  对应 Workspace 调用（`create_entry`/`rename_entry`/`remove_entry`/
  `copy_entry`/`move_entry`），`FileExistsError`/`OSError` → Input 行显示错误
  （对齐 explorer prompt_delete 的 `type y to confirm`：`d` 需先输入 `y` 确认，
  目录行提示 `recursive`）；操作后 `_reload` + `workspace.invalidate()`。
- **多选打开**：`action_open` 时若 `_marked` 非空且含当前光标项则开集合：
  `open_selected(sorted(_marked))`（Q2 语义在 flows/screen 分层——screen 只传集合；
  混合集合的取舍在 flows `open_selected` 编排，见 plan-e）。
- **隐藏切换**：`workspace.show_hidden = not workspace.show_hidden` + `_reload`
  （与 explorer `H` 同一属性源，explorer.py:385-391 先例）。

### 鼠标（R6）
- ListView 内建：单击行 → cursor 移动（Highlighted）；**双击 → Selected 事件** →
  `on_list_view_selected` 触发 `action_open`（Textual 8.x 双击行为；若实测不符，
  以 `on_click` + `time.monotonic()` 双击窗口（300ms）自实现，回填偏离记录）；
- 滚轮：三栏独立滚动（ListView/PreviewLog 内建）；`can_focus=False` 的两栏
  `PreviewLog` 滚轮仍可用（RichLog 内建）；
- `support_mouse` 闸门在 `YateApp.on_event`（app.py:236-258）统一拦截，
  组件无需自查。

### 主题（R13）与滚动条（R15）
- `on_mount`：三栏 + Input 挂好后 `apply_slim_scrollbars(w)` × 每个滚动容器、
  `theme.attach(self, self._apply_theme)`；`on_unmount` `theme.detach(self)`；
- `_apply_theme`：`apply_scrollbar_theme()` 每栏 + 重染全部行（复用 `_reload`
  的行构建，读 `theme.active().accent`）+ 状态栏配色（Static `update` Text）。

### 日志
`log = tracing.get_logger(__name__)`（R12），异常路径 `log.debug("... %s", e)`。

## 新增测试（tests/test_filemgr.py）
模式 A（screen 级，最小 _Host 对齐 test_palette.py:26-36 先例——App + tmp workspace
+ push FileManagerScreen + pilot）；模式 B（纯函数已由 plan-c 覆盖，此处不重复）。

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_filemgr_renders_three_panes_and_status` | push + pilot.pause | `#filemgr-parent/#filemgr-list/#filemgr-preview/#filemgr-status` 存在；中栏行数 == list_dir 数 |
| `test_filemgr_navigate_enter_dir_and_back_lands_on_origin` | j/l 进入子目录 → h | 中栏内容回到父目录；光标 index 落在原目录项（lf 语义） |
| `test_filemgr_filter_narrows_and_esc_clears` | `/` 输入子串 → Esc | 行数收窄；Esc 后恢复全量 |
| `test_filemgr_sort_cycles_with_dirs_first` | s ×3 | 状态栏提示 name→size→mtime；目录恒在前 |
| `test_filemgr_toggle_hidden_and_refresh` | H → r | dotfile 出现；`Workspace.invalidate` 后重建同列表 |
| `test_filemgr_mark_and_invert_and_open_collection` | Space/v → Enter | `open_selected` 收到集合参数（记录型 stub 回调断言） |
| `test_filemgr_double_click_opens_via_selected` | `pilot.click` 双击行 | `open_selected` 收到该文件（若 Textual 双击不发 Selected 则记录偏离改 on_click 实现） |
| `test_filemgr_preview_shows_tokens_and_binary_note` | 文本文件 / 二进制文件 | 预览区含高亮行 / note 降级文本（wait_until 轮询 worker） |
| `test_filemgr_dirty_confirmation_flows_through_callback` | （P1 后置）a 建文件不涉及；此处仅验证 Esc 两级退出 | 有过滤先清过滤，再 Esc 才 dismiss |
| `test_filemgr_theme_switch_repaints_rows` | `theme.set_theme(另一主题)` | 行 span 色变（新 accent）且滚动条主题跟随 |
| `test_filemgr_file_ops_create_rename_delete` | a 输入名 → R 改名 → d y 确认 | 磁盘状态逐步断言（tmp_path） |
| `test_filemgr_fullscreen_css_class_switches_layout` | fullscreen=True push | `.fullscreen` 类存在且 `#filemgr` 尺寸类生效（DOM 断言） |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/filemgr.py yate/resources/filemgr-screen.tcss --skip 2>$null; .venv\Scripts\python.exe -m pyright yate/editor_view/filemgr.py tests/test_filemgr.py
.venv\Scripts\python.exe -m pytest tests/test_filemgr.py tests/test_filemgr_model.py tests/test_palette_preview.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```
（tcss 非 py 目标，pyright 只跑 .py。）

## 风险与回滚
- ListView 大列表（>1000 行）构建耗时：`count_children` 只对目录行 + >999 截断；
  如 pilot 实测 >0.5s，目录徽标降级为懒加载（回填偏离）；
- gg 状态机与 BINDINGS 冲突：`g` 用 on_key 拦截（`event.key == "g"`），勿同时
  注册 `g` binding；
- Textual 双击语义实测不符 → on_click 计时方案（本计划已预案）；
- 回滚：新文件三枚，独立成笔 revert 零残留。
