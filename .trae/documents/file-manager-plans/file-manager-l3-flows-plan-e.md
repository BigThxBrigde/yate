# plan-e：L3 FileManagerFlows + editor 接线（wave-4）

## 输入
总纲 §三（Q1/Q2/Q3 裁决）/§四；plan-d 的 FileManagerScreen 构造签名。
事实基线（editor.py / flows/）：
- flows 属性声明：类体纯类型注解（editor.py:389-426），`_build_pane_stack`
  （237-366）内构造（OverlayFlows 先例 275-295：全关键字注入）；
- `bind_hex_opener`（editor.py:294-296 定义于 DocumentFlows，editor.py:299 调用）
  晚绑定先例；
- App 动词注入：`ed.app.push_screen` / `ed.app.pop_screen`（276-277）、
  `ed.app.run_worker`（多处）；`flows/__init__.py` 共享别名
  MessageFn(28)/SpawnFn(32)/OverlayPusher(37)/StateQuery(42)，lazy 无 re-export；
- `Workspace.set_root`（workspace.py:102-106）+ `DocumentFlows.open_path`
  （document_flows.py:264-284：目录分支 set_root+refresh+reveal、文件分支
  `_open_document`+`_after_open`）；无 close_workspace 概念；
- ExplorerTree：`refresh_tree()` / `open_path` 晚绑定（editor.py:221）；
- dirty 检测：Document 的 dirty 状态在 editor_core（executor 以实际属性为准，
  TabBar `●` 渲染处有现成读取点可参照）；
- 保存：`DocumentFlows.save_document()`（actions.py:187 引用先例）。

## 目标
`FileManagerFlows`：双形态打开入口、`open_selected` 编排（Q1 dirty 三态 →
关旧工作区 → `set_root` → 打开目标）、全屏退出注入。Editor 装配接线。

## 独占文件清单
- `yate/flows/filemanager_flows.py`（新建）
- `yate/flows/__init__.py`（追加 type 别名）
- `yate/editor.py`（类属性声明 + _build_pane_stack 构造 + bind_exit 方法）
- `tests/test_filemgr_flows.py`（新建）

## 具体修改

### 1. flows/__init__.py 追加（保持 lazy，无 re-export）
```python
#: Open a selected path set from the file manager (paths, dirs resolved by flows).
type OpenSelectedFn = Callable[[list[Path]], None]
```

### 2. filemanager_flows.py
```python
"""File manager flows: overlay/fullscreen open points and workspace switching."""
class FileManagerFlows:
    def __init__(
        self, *,
        spawn: SpawnFn,                       # ed.app.run_worker（透传给 screen 预览 worker）
        push_screen: OverlayPusher,           # ed.app.push_screen
        pop_screen: Callable[[], None],       # ed.app.pop_screen
        session: EditorSession,
        workspace: Workspace,
        explorer_tree: ExplorerTree,
        documents: DocumentFlows,             # open_path / save_document 复用
        prompt_bar: PromptBar,                # dirty 提示消息面（非输入）
        message: MessageFn,
        report: Callable[[str], None],
        refresh_ui: Callable[[], None],
        mounted: Callable[[], bool],
        focus_editor: Callable[[], None],
        config: YateConfig,                   # FilePreviewConfig 读取
    ) -> None: ...
    def bind_exit(self, exit_app: Callable[[], None]) -> None: ...
    def open_overlay(self) -> None: ...
    def open_fullscreen(self, initial_dir: Path) -> None: ...
    def _open_selected(self, paths: list[Path]) -> None: ...   # 注入 screen 的回调
    def _switch_workspace(self, target: Path) -> bool: ...     # Q1 → 关旧 → set_root
```
- `open_overlay()`：`push()` 语义对齐 OverlayFlows.push（先 `prompt.idle()` 再
  push？——OverlayFlows.push 是既有统一入口；**定稿直接用注入的 push_screen**，
  不并 OverlayFlows（职责独立），但 push 前调 `self._message_idle()` 等价卫生
  （executor 参照 overlay_flows.py:86-99 行为，保持「陈旧消息不回流」契约）。
  构造 `FileManagerScreen(workspace=..., preview=config.file_preview,
  open_selected=self._open_selected, close=self.pop_screen, fullscreen=False)`。
- `open_fullscreen(initial_dir)`：同上 + `fullscreen=True` + `initial_dir`；
  close 回调 = `self._exit_app`（bind_exit 注入；未绑定时降级 pop_screen 并
  log.warning——防御性，正常路径 L4 必绑）。
- `_open_selected(paths)`（Q1/Q2/Q3 编排核心）：
  1. 空集合 → return；
  2. 多集合（len>1）：目录过滤——若有目录则**仅取第一个目录**（光标序=列表序），
     其余全忽略，`report("...")` 提示；纯文件 → 全部进切换流程；
  3. 单目录 → `_switch_workspace(dir)`，无文件打开；
  4. 文件集 → `_switch_workspace(首个文件.parent)` 成功后逐个
     `session.open(path)`（首个 activate，其余后台 tab）——**对齐 `yate
     path1 path2` 启动多文件语义**（executor 核对 cli 多 path 现状；若无此语义
     则逐个 open 也是目标形态，报告记录）；
  5. `focus_editor()` + `refresh_ui()`。
- `_switch_workspace(target)`（Q1）：
  1. dirty 检测（**已验证事实，按此实现**）：`any(doc.modified for doc in
     session.docs)`——`doc.modified` 是 Document 的既有 property（TabBar `●` /
     statusbar / `:q` 三处消费），`session.docs` 是 `list[Document]`；
     `Editor.quit` 的阻塞判定同款（editor.py:1201）。有 dirty →
     `report(f"{n} unsaved changes - save or discard first", kind="warn")` +
     返回 False（不切换、不关闭任何文档——绝不静默丢弃）；
  2. 无 dirty → 关旧工作区：**已验证事实**——`close_active()` 返回
     `(closed, fallback)` 且最后一个 tab 关闭时自动追加 scratch buffer
     （session.py:201-213，session 恒有 active doc）。循环终止条件不能用
     fallback（恒存在）：正确写法 = 关到只剩无路径 scratch
     （`len(session.docs) == 1 and session.docs[0].path is None` 时停）；
     随后 `workspace.invalidate()`；
  3. `documents.open_path(target)`（目录分支自带 set_root+refresh_tree+reveal；
     文件分支自带 root=parent+打开）——**复用既有编排，不自写 set_root**；
  4. 返回 True。
- 不持 App 句柄（守卫 test_flow_modules_hold_no_app_handle）：全部经注入。

### 3. editor.py 接线（三处，行号为当前基线）
1. import 区（51-62 flows import 组）追加
   `from yate.flows.filemanager_flows import FileManagerFlows`；
2. 类体声明区（389-426）追加 `filemanager_flows: FileManagerFlows`；
3. `_build_pane_stack`（237-366）OverlayFlows 构造段后追加构造（全关键字注入，
   协作者复用该工厂既有局部变量：panes/session/workspace/prompt_bar/documents
   等按实际变量名）；`bind_hex_opener`（299）旁追加 bind 点注释：
   `bind_exit` 由 L4 在 on_mount 调用（editor 不持 App.exit——App 句柄边界）。
   Editor 增公共方法 `bind_filemanager_exit(self, exit_app)` 转发（一行）。
- 装配顺序注释（__init__ 457-461）按 §三.8 接入清单第 4 条同步。

### 4. tests/test_filemgr_flows.py
stub 协作者（session/workspace/documents 用记录型 fake，不起 Textual app）：

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_open_selected_single_file_switches_root_and_opens` | stub dirty=False | `documents.open_path` 收到文件；焦点回调被调 |
| `test_open_selected_collection_pure_files_opens_all` | 3 文件 | open_path 序列含全部（首个激活语义在 stub 记录） |
| `test_open_selected_mixed_takes_first_dir_only` | dir+files | 仅目录进入，report 收到提示 |
| `test_open_selected_blocked_by_dirty_reports_and_keeps` | stub dirty=True | open_path 未被调；report 含 unsaved；screen 未被 dismiss（close 回调未调） |
| `test_switch_workspace_closes_all_tabs_after_clean_check` | 2 tabs | close_active 调用至空；invalidate 调用 |
| `test_bind_exit_wires_fullscreen_close` | bind 后 `open_fullscreen` + 触发 close 回调 | exit_app 被调 |
| `test_flows_hold_no_app_handle` | AST 已有全局守卫覆盖；此处行为级：构造后 `hasattr(flows, "app") is False` | True |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/flows/filemanager_flows.py yate/flows/__init__.py yate/editor.py tests/test_filemgr_flows.py
.venv\Scripts\python.exe -m pytest tests/test_filemgr_flows.py tests/test_flow_modules.py tests/test_app_render.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```
（若 tests/test_flow_modules.py 不存在，以 `tests/` 全量 flows 相关文件名替代——
executor 先 `search_file "test_*flow*"` 确认。）

## 风险与回滚
- editor.py 是共享热点文件（豁免名单在册，当前 1239 行）：本计划仅追加
  ~40 行（import/声明/构造/bind），零既有行为改动；与 wave-5 的 app.py 接线
  分属两文件，无冲突；
- Q1 裁决修订（三态→提示阻塞）已回填总纲 §三；
- session.close_active 循环的 fallback 语义（201-221 返回 (closed, fallback)）
  以实际返回为准，循环终止条件=fallback 且 closed=False；
- 回滚：flows 新文件独立 revert；editor.py 三处小改可手工精准还原。
