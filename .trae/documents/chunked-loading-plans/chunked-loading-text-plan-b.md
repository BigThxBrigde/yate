# chunked-loading-text-plan-b（wave-2：文本接入）

## 输入

- 主计划 [../chunked-loading-plan.md](../chunked-loading-plan.md) §三 定案 1/2/3/4（文本侧）。
- plan-a 产物 `yate/editor_core/chunked.py`（`ChunkedTextFile` / `ChunkedFallback`，以 plan-a 验收后的实际签名为准）。

## 目标

`session.open` 超阈值走分段 Document；`TextBuffer` 渐进填充；L3 `ChunkedFlows` 编排后台扫描与按需加载；`EditorView` 渲染触发行加载回调；阈值 yaterc 可配；`:fullload` 显式升级。

## 独占文件清单（只改这些，不要动其它任何文件）

- `yate/editor_core/document.py`
- `yate/editor_core/buffer.py`
- `yate/session.py`
- `yate/config.py`
- `yate/yaterc_options.py`
- `yate/commands.py`
- `yate/flows/chunked_flows.py`（新增）
- `yate/editor.py`
- `yate/editor_view/editor.py`
- `tests/test_document_chunked.py`（新增）、`tests/test_session.py`、`tests/test_editor_core.py`（仅新增用例）、`tests/test_config.py`（仅新增用例，若存在该文件——执行时以实际测试文件名为准，找不到则新建 `tests/test_large_file_option.py`）

与 plan-c（`overlay_flows.py` / `hexview.py` / hex 测试）零重叠。

## 具体修改

### 1. `yate/editor_core/buffer.py`（~+35 行）

- 新增字段 `locked: bool = False`（模块 docstring 与类 docstring 各补一句：locked = structural write lock for chunked read-only documents）。
- 卫语句：全部用户面变更方法入口 `if self.locked: return`——集中在底层原语 `_apply_text`（:423）、`insert_at_points`（:656）、`delete_at_points`（:691）、`delete_forward_at_points`（:737）与 `set_text`（:164）六处；上层封装（type_char/insert_newline/delete_*/paste/…）全部经底层原语，无需逐个改。
- 新增 `fill_lines(start: int, rows: list[str]) -> None`：分段填充专用——**不受 locked 限制**、不快照、不递增 `content_edits`（非用户编辑，`modified` 保持 False），递增 `content_version` 并扩展 `self.lines` 至 `start + len(rows)`（用 `""` 占位行扩展后原地替换）。原语级实现，供 ChunkedFlows 调用。
- 新增 `rows_loaded(start: int, count: int) -> bool` 查询：该行区间是否已填真实内容（占位空行 = 未加载；约定：填充只发生在「从首个占位行起连续替换」，用 `content_version` 与填充水位变量 `_filled_rows: int` 判断，避免逐行扫描）。

### 2. `yate/editor_core/document.py`（~+55 行）

- 类新增字段 `chunked: ChunkedTextFile | None = None`（`__init__` 形参默认 None；`from yate.editor_core.chunked import ...` 为 L0 包内绝对导入，合规）。
- 新增 `open_chunked(cls, path: Path | str, chunk_size: int = CHUNK_SIZE) -> Document`：
  1. `chunked_file = ChunkedTextFile(path, chunk_size)`（`ChunkedFallback` 上抛，调用方回退 `open`）；
  2. `doc = cls(p, TextBuffer())`；`doc.chunked = chunked_file`；`doc.buffer.locked = True`；`doc.eol` 取预扫描首块 EOL 统计（渐进，终值与 `_dominant_eol` 同语义）；`encoding` 取 chunked_file.encoding；
  3. `doc.buffer.move_doc_start()`；
  4. 返回（此时 lines 为空占位，`line_count == 0`，由 ChunkedFlows 填充首块）。
- 新增 `promote_to_full(cls 级别不需要，实例方法) -> None`：`fullload` 用——读全文件（复用 `open` 的解码/EOL 路径），替换 `self.buffer` 为全量 `TextBuffer(text)`，`self.chunked = None`，`locked = False`，重记 `_saved_edits/_saved_lines`。
- `save()`（:200）入口卫语句：`if self.chunked is not None: raise`（或报错经 flows 提示；分段只读文档不应到达 save——`:w` 对 locked 文档由 read-only 面拦截，此处防御性断言用 `RuntimeError`）。
- `modified`：分段模式 `content_edits` 恒等于 `_saved_edits`（fill_lines 不递增）→ O(1) 路径自然 False，无需分支。

### 3. `yate/session.py`（~+12 行）

- `EditorSession` 已持 config（构造参数，现有 `apply_buffer_options` 消费 tab_width，:72-83；执行时核实 config 引用的确切持有形态，按同模式取 `config.large_file_threshold`）。
- `open`（:97-116）与 `open_async`（:118-139）：`path.exists()` 分支内、`Document.open` 之前判 `st = path.stat(); if st.st_size > threshold: doc = Document.open_chunked(path)`；`ChunkedFallback` 捕获后回退 `Document.open(path)`。`open_async` 的 stat 并入现有 `_inspect` 线程任务（返回三元组）。

### 4. `yate/config.py` + `yate/yaterc_options.py`（~+40 行）

- 仿 `file_preview` dict 形态：`@dataclass LargeFileConfig`，字段 `threshold: int = 8_388_608`（8 MiB；允许 0 = 禁用分段；范围 0 或 [1_048_576, 1_073_741_824]）；`YateConfig` 增 `large_file: LargeFileConfig` 字段；`KNOWN_OPTIONS` 注册 `large_file`。
- `yaterc_options.py` 新增 `_extract_large_file`（解析 dict 选项，非法值进 `config.errors`，措辞对齐 `_extract_file_preview` :394-407），并在 `_extract_options` 尾部 dict 区调用（:538-540 旁）。
- `:set` 表：不新增 SetOption（阈值重启期生效即可，记录于手册）。

### 5. `yate/flows/chunked_flows.py`（新增，L3 流程模块，~120 行）

`ChunkedFlows`（§三.8 清单：不持 App 句柄；构造注入，全部依赖经 `__init__`）：

```python
class ChunkedFlows:
    # __init__(
    #     ensure_view_refresh: Callable[[], None],   # -> editor_view refresh
    #     message: Callable[[str, str], None],       # status line
    #     spawn: Callable[..., object],              # editor.run_worker (verb injection, IKJB0Q)
    # ) -> None
    # attach(doc: Document, view_row_probe: Callable[[int], None]) -> None
    #   - binds the active chunked doc; resets scan state; kicks the initial
    #     fill (first chunk, synchronous) + background scan worker
    # ensure_row(row: int) -> None
    #   - called from EditorView render path; dedups per row watermark;
    #     loads the owning chunk synchronously if missing (≤ CHUNK_SIZE read)
    #     and fills; heavy prefetch stays on the scan worker
    # promote_to_full() -> None
    #   - :fullload handler: doc.promote_to_full() + message
```

- 后台扫描 worker：`spawn`（Editor 注入 `run_worker`）循环 `chunked.scan_next_batch()` → `buffer.fill_lines(...)` 新扫描块行（仅推进索引与水位，不预填内容——内容仍按需读）→ 完成后 `ensure_view_refresh()`。扫描与填充职责：**扫描建索引**（行号正确性）、**fill 只在 ensure_row 触达时填内容**（内存上限）。
- `fill_lines` 水位：填充区间必须与 `rows_loaded` 判定一致（连续推进，不空洞）。

### 6. `yate/editor.py`（L3 组装，~+15 行）

- 类属性声明 `chunked_flows: ChunkedFlows | None = None`（类型注解 + None 初值，§三.8.2）。
- `_build_*` 工厂内构造（§三.8.3）：注入 `ensure_view_refresh=ed.<view refresh 入口>`、`message=<message line 回调>`、`spawn=ed.run_worker`（动词注入）；`__init__` 组装顺序注释同步。
- 打开成功尾巴挂接：`_open_document` 成功路径后（document_flows 不在独占清单——挂接点放 `Editor`：`ed.document_flows` 已有 after-open 回调缝？执行时核实 `_after_open`（document_flows.py:250-261）调用链；若必须改 document_flows.py 才能挂接，**停下上报主代理**调整独占清单，不得自行扩文件）。
- 只读面确认：分段 doc 的编辑拦截复用现有只读机制（`document_flows.py:432-437` 形态）；执行时核实 EditorView 对 locked/read-only 的现有按键路径，若 EditorView 需要显式只读查询，经构造注入回调补（editor_view/editor.py 在独占清单内）。

### 7. `yate/editor_view/editor.py`（L2，~+18 行）

- `__init__` 新增关键字参数 `ensure_row: Callable[[int], None] | None = None`（默认 None = 现行为，全部既有构造零改动）。
- `render_line`（:345-381）：`y += self.scroll_offset.y` 之后、`buf.lines[y]` 之前：`if self._ensure_row is not None: self._ensure_row(y)`。未加载行 = 空串 → 走既有渲染路径显示空白（:377 越界分支兜底渐进 line_count）。
- R3 合规：只新增回调参数，无向上 import。

### 8. `yate/commands.py`（~+8 行）

- `:fullload` 命令：`reg("fullload", _fullload, "promote the chunked document to a fully loaded editable buffer")`；`_fullload` 调 `editor.chunked_flows.promote_to_full()`（非分段文档 no-op + 提示）。

## 需要新增的测试

`tests/test_document_chunked.py`（新建）：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_open_chunked_fills_first_chunk_and_locks` | 小文件（chunk_size 注入小值） | `Document.open_chunked` | `doc.chunked 非 None`；`buffer.locked is True`；首块行已填（rows_loaded(0,n) True 区间） |
| `test_fill_lines_progresses_watermark_without_edits` | 分段 doc | 逐块 fill_lines | `content_edits` 不变；`modified is False`；`rows_loaded` 水位单调推进 |
| `test_locked_buffer_rejects_all_edits` | locked TextBuffer | type_char/insert_newline/delete_lines/set_text/insert_at_points | 全部 no-op（lines/cursors 不变，不抛异常） |
| `test_promote_to_full_restores_editing` | 分段 doc（已填充首块） | promote_to_full | `chunked is None`、`locked is False`、`get_text()` 与磁盘全等、`modified is False` |
| `test_save_raises_on_chunked_document` | 分段 doc | `doc.save()` | raises RuntimeError |
| `test_open_chunked_fallback_on_cr_only` | CR-only 文件 | `Document.open_chunked` | raises ChunkedFallback（session 层回退另测） |

`tests/test_session.py` 增补：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_open_uses_chunked_document_above_threshold` | config.large_file.threshold=0 禁用外的极小阈值 + 生成文件 | `session.open` | 返回 doc.chunked 非 None |
| `test_open_full_load_below_threshold` | 阈值 0（禁用） | `session.open` | doc.chunked is None，行为与现状一致 |
| `test_open_async_uses_chunked_document_above_threshold` | 同上异步版 | `session.open_async` | 同步版等价 |
| `test_open_falls_back_to_full_on_cr_only` | CR-only 文件 + 小阈值 | `session.open` | 返回全量 doc（chunked is None）且内容正确 |

config 选项（文件名执行时核实）：

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_large_file_threshold_option_round_trip` | rc 文本 `large_file = {"threshold": 16777216}` → load_config | `config.large_file.threshold == 16_777_216`；errors 为空 |
| `test_large_file_threshold_rejects_bad_values` | `{"threshold": 512}` 与 `{"threshold": "big"}` | 进 `config.errors`；config 字段保持默认 |

flows/Editor（若现有 flows 测试基建可复用则加；不可复用不强行造）：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_editor_view_ensure_row_called_for_visible_rows` | EditorView 注入记录型 ensure_row | render_line 可见行 | 回调收到的 row 在视口范围内 |
| `test_chunked_flows_ensure_row_fills_requested_chunk` | ChunkedFlows attach 分段 doc | ensure_row(末行) | 对应块已填、rows_loaded 为真 |

## 验收命令（执行者跑）

```powershell
Set-Location D:\Programming\yate-chunked-loading
.venv\Scripts\python.exe -m pytest tests/test_document_chunked.py tests/test_session.py tests/test_editor_core.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

通过判定：全部退出码 0；架构 36 用例不因本计划新增违规（`test_no_unregistered_upward_imports` / `test_flow_modules_hold_no_app_handle` / `test_source_files_within_size_threshold` 重点观察）。

## 风险与回滚

- buffer.py / editor.py（L3）是豁免名单成员：改动后同步更新 `architecture-boundaries.md` §三.7 对应条目行数与 `tests/test_architecture.py` 的 `SIZE_EXEMPT_FILES`（两处同步，§三.7 硬性）。
- editor_view/editor.py 若改动后超 800 行须先评估拆分/豁免并上报，不得静默越线。
- 回滚：本计划改动集中在列出的 9 个产品文件，逐 hunk 撤销即可；`large_file` 选项未写 rc 时默认 8 MiB——若执行期判定默认开启风险大，回滚点 = 阈值默认改 `0`（禁用）保持行为中立，登记偏离后由主代理定夺。
