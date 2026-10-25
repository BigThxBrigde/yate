# chunked-loading-hex-plan-c（wave-2：hex 接入）

## 输入

- 主计划 [../chunked-loading-plan.md](../chunked-loading-plan.md) §三 定案 4（hex 侧保存）与 §二 hex 链路事实。
- plan-a 产物 `yate/editor_core/chunked.py`（`ChunkedBinaryFile`，以 plan-a 验收后的实际签名为准）。

## 目标

hex 视图数据源由一次性 `read_bytes()` 改为注入 `ChunkedBinaryFile`（与文本侧共用同一分块机件）；废除 `MAX_HEX_VIEW_SIZE = 100 MB` 上限；保存从「全量覆写」改为「脏字节就地写回」，TOCTOU 指纹门与冲突门原样保留；渲染逐字节断言零变化。

## 独占文件清单（只改这些，不要动其它任何文件）

- `yate/flows/overlay_flows.py`
- `yate/editor_view/hexview.py`
- `tests/test_hex_view.py`
- `tests/test_overlay_flows_hex.py`

与 plan-b 零重叠。

## 具体修改

### 1. `yate/editor_view/hexview.py`（净改约 ±40 行，总量仍在 800 内）

- `HexView.__init__`（:251-275）：入参 `data: bytes` → `source: ChunkedBinaryFile`；删除 `self._data: bytearray`（:260-262），改持 `self._source`；`virtual_size`（:273-275）改由 `source.size` 计算（`(size + 15) // 16`，构造期无需读内容——语义不变）。
- `render_line`（:383-423）：`chunk = self._data[offset:offset+16]`（:396-397）→ `chunk = self._source.read(offset, 16)`。渲染函数其余逻辑（xxd 布局/分类/ASCII 列）零改动。
- 编辑路径：nibble 写入 `self._data[cursor] = byte` → `self._source.apply_edit(cursor, byte)`（undo 栈 `(offset, old_byte)` 语义不变，:351-368）。
- `current_bytes()`（:298-300）删除；新增 `dirty_edits() -> dict[int, int]`（透传 source）。
- `HexScreen.__init__`（:466-499）：`data: bytes` → `source: ChunkedBinaryFile`；`_load_size` 初始化改用 `source.size`；原始 data 兜底（:480、:556）删除——未挂载时 `save()` 拒绝写（`_write_bytes is None` 路径已有）。
- `HexScreen.save()`（:538-569）：`write_bytes` 回调签名 `(path, data, mtime, size)` → `(path, edits, mtime, size)`（`edits: dict[int, int]`）；成功后清脏集：`self._source.clear_edits(edits.keys())`（新增调用，:565-567 旁）；指纹刷新逻辑不变。
- 模块 docstring（:4-7「data is handed in pre-read」）与类 docstring 同步改写为 chunked source 语义。

### 2. `yate/flows/overlay_flows.py`（±25 行）

- `open_hex_view`（:186-233）：删除 `MAX_HEX_VIEW_SIZE` 门禁（:208-214）与 `data = path.read_bytes()`（:216）；改为 `source = ChunkedBinaryFile(path, size, mtime)` 构造（O(1)，不读盘）；`HexScreen(path, source, ...)`。
- `_write_hex_bytes`（:235-267）改名 `write_hex_edits`（动词化）：参数 `data: bytes` → `edits: dict[int, int]`；冲突门（:252-254）与 TOCTOU 门（:255-258）原样；写回段改：

```python
with open(path, "r+b") as f:
    for offset in sorted(edits):
        f.seek(offset)
        f.write(bytes((edits[offset],)))
```

- 成功后返回新指纹（:266-267）不变。空 edits 早退（no-op 返回当前指纹）。
- `MAX_HEX_VIEW_SIZE` 从 `hexview.py` 删除；全仓搜索确认无残留引用。

### 3. 测试改造（渲染断言逐字节不动）

- `tests/test_hex_view.py`：39 例的构造 helper 统一改为「给 bytes → 包 `ChunkedBinaryFile(path, len(data), 0.0)`」的工厂（tmp_path 写临时文件再构造，保 read 语义真实）；断言目标全部保持。
- `tests/test_overlay_flows_hex.py`：
  - `test_open_hex_view_rejects_oversize_file`（:208）→ 改写为 `test_open_hex_view_accepts_large_file_without_full_read`：mock/大 stat size（tmp_path 稀疏文件），断言 HexScreen push 且底层读盘字节数受控（monkeypatch 计数 ≤ 1 block）。
  - `test_open_hex_view_stat_precheck_rejects_without_read`（:227）：保留 stat 预检语义（stat 失败仍拒绝，不可读路径 :254 用例不动）；原「超限拒绝」断言删除。
  - binary open 回退/启动/ toggle 各例：构造链适配 source，断言不变。
- 新增：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_hex_view_renders_from_chunked_source_without_full_read` | 1 MiB 文件，block 64 KiB，monkeypatch 底层 read 计数 | push HexScreen 渲染首屏 | 累计底层读取 ≤ 2 blocks（首屏与文件大小无关） |
| `test_hex_screen_save_writes_only_dirty_bytes_inplace` | 1 KiB 文件 source，编辑 2 字节 | `save()` | 磁盘全文件与原文件 diff 恰 2 字节差异；新指纹返回；脏集清空 |
| `test_hex_screen_save_gates_unchanged` | 既有两门 | 冲突门/外部修改门场景 | 拒写行为与回归锁 `test_hex_screen_save_refreshes_fingerprint_for_resave`（:753）语义不变（该例同步适配签名后必须仍绿） |
| `test_hex_view_edit_undo_roundtrip_chunked` | source 注入 | e → nibble 编辑 → u | 读回原字节；undo 栈语义不变 |

## 验收命令（执行者跑）

```powershell
Set-Location D:\Programming\yate-chunked-loading
.venv\Scripts\python.exe -m pytest tests/test_hex_view.py tests/test_overlay_flows_hex.py -q
.venv\Scripts\python.exe -m pyright yate/flows/overlay_flows.py yate/editor_view/hexview.py tests/test_hex_view.py tests/test_overlay_flows_hex.py
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
```

通过判定：全部退出码 0；`test_hex_screen_save_refreshes_fingerprint_for_resave` 与启动端到端 `test_startup_binary_open_flows_to_hex_screen` 必须在列且绿。

## 风险与回滚

- 渲染逐字节断言是行为锚点：只换数据来源，`render_line` 内部零逻辑改动；任一渲染断言失败先查 source 而非改断言。
- 稀疏大文件测试在 Windows tmp 的落盘行为：用 `tmp_path` + 小文件 + monkeypatch stat 尺寸优先，避免真实 100 MB 落盘。
- 回滚：两产品文件逐 hunk 撤销；`MAX_HEX_VIEW_SIZE` 删除属行为变更（放松上限），如需紧急回滚恢复常量与门禁 hunks 即可。

## 执行记录（wave-3 回填，2026-10-25）

- 提交：`fba33c8`（`feat(chunked-loading): feed the hex view from the chunked source`）。
- 验收（执行者实测，主代理独立复核通过）：
  `pytest tests/test_hex_view.py tests/test_overlay_flows_hex.py -q` → 56 passed，退出码 0；
  `pyright yate/flows/overlay_flows.py yate/editor_view/hexview.py tests/test_hex_view.py
  tests/test_overlay_flows_hex.py` → 0 errors，退出码 0；
  `pytest tests/ -q -n auto` → 全绿，退出码 0；
  锚点用例 `test_hex_screen_save_refreshes_fingerprint_for_resave` /
  `test_startup_binary_open_flows_to_hex_screen` 单独复核绿。
- 偏离 5 条（主代理裁定全部接受）：
  1. `render_line` 取数行加 EOF 长度钳制（`min(16, size-offset)`）——
     `ChunkedBinaryFile.read` 对越界区间抛 ValueError，不钳制则末行渲染必炸；
     属数据源接线必要部分，渲染布局/样式逻辑零改动。
  2. `test_open_hex_view_read_failure_reports` 适配为 monkeypatch `ChunkedBinaryFile`
     构造抛 OSError（全量读盘删除后原形态必失败），断言 "cannot read" 原样保留。
  3. 遗留门禁两例各加一行 `source.apply_edit(0, 0x41)`：空 edits 现为 no-op 早退，
     无编辑不再触达门禁；新增 `test_hex_screen_save_gates_unchanged` 覆盖同语义。
  4. `test_hex_view_current_bytes_immutable` 随 `current_bytes()` 删除改写为
     `test_hex_view_dirty_edits_returns_copy`（保留快照不可外部改动意图）。
  5. undo 栈断言按实测语义：每 nibble 一条 `(offset, old_byte)` 记录，两次 undo 回原字节。
- 遗留：无。
