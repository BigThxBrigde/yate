# Hex View - Plan E: Review Fixes (W1-W4 + S1 待办)

## 目标

修复评审（python-code-review + pr-review 双视角）发现的 4 项 WARNING；SUGGESTION 按纪律登记待办不修。

## 非目标

- 不新增 hex view 功能；
- 不改变波次结构（wave-1..4 已完成）。

## 输入

- `yate/editor_view/hexview.py:41-44`（`_CONTENT_WIDTH` 公式错误）；
- `yate/flows/overlay_flows.py:196-207`（`read_bytes()` 在尺寸闸门之前）；
- `yate/flows/document_flows.py:230-236`（`_open_document_async` 二进制分支零单测）；
- `yate/flows/overlay_flows.py:211-222`（空会话 `:hex` 崩溃）；
- `yate/editor_view/hexview.py:69`（`self._path` 仅写不读）。

## 独占文件清单

- `yate/editor_view/hexview.py`（W1 公式修正 + S1 登记）；
- `yate/flows/overlay_flows.py`（W2 stat 预检 + W4 空会话守卫 + 注释修正）；
- `tests/test_overlay_flows_hex.py`（W3 async 用例 + W4 空会话用例）；
- `tests/test_hex_view.py`（W1 满行宽度断言）。

## 具体修改

### W1: 修正 `_CONTENT_WIDTH` 公式

**定位**：`yate/editor_view/hexview.py:41-44`

**当前逻辑**：
```python
#: Fixed content width of a full line: 8 offset digits + ``:`` + space +
#: 2 groups of 8 bytes (16 hex chars each, 2 spaces between groups) +
#: 2 spaces + 16 ASCII chars.
_CONTENT_WIDTH: int = 9 + 1 + 2 * (2 * _BYTES_PER_LINE) + 2 + _BYTES_PER_LINE
```

**问题**：算出 92，实际满行 62 列（offset 9+1=10 + hex 16*2+组间 2=34 + 2 + ASCII 16）。

**新逻辑**：
```python
#: Fixed content width of a full line: 8 offset digits + ``:`` + space +
#: 2 groups of 8 bytes (16 hex chars each, 2 spaces between groups,
#: total 34 chars) + 2 spaces + 16 ASCII chars.
_CONTENT_WIDTH: int = 9 + 1 + (2 * _BYTES_PER_LINE + 2) + 2 + _BYTES_PER_LINE
```

**测试**：在 `tests/test_hex_view.py` 补 `test_hex_view_full_line_width_is_62`：
```python
def test_hex_view_full_line_width_is_62() -> None:
    """A full 16-byte line renders exactly 62 columns (offset + hex + ASCII)."""
    from yate.editor_view.hexview import _CONTENT_WIDTH
    assert _CONTENT_WIDTH == 62
```

**验收**：
```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_hex_view.py::test_hex_view_full_line_width_is_62 -q
```

### W2: stat 预检尺寸闸门

**定位**：`yate/flows/overlay_flows.py:196-207`

**当前逻辑**：
```python
try:
    data = path.read_bytes()
except OSError as exc:
    self._message(f"cannot read {path.name}: {exc}", "warn")
    return
if len(data) > MAX_HEX_VIEW_SIZE:
    self._message(
        f"file too large for hex view: {path.name} "
        f"(> {MAX_HEX_VIEW_SIZE} bytes)",
        "warn",
    )
    return
```

**问题**：10GB 文件先全量入内存再拒收，且 `MemoryError` 非 OSError 会穿透。

**新逻辑**：
```python
try:
    size = path.stat().st_size
except OSError as exc:
    self._message(f"cannot stat {path.name}: {exc}", "warn")
    return
if size > MAX_HEX_VIEW_SIZE:
    self._message(
        f"file too large for hex view: {path.name} "
        f"(> {MAX_HEX_VIEW_SIZE} bytes)",
        "warn",
    )
    return
try:
    data = path.read_bytes()
except OSError as exc:
    self._message(f"cannot read {path.name}: {exc}", "warn")
    return
```

**偏离 plan-c 登记**：plan-c 原设计同步 `read_bytes()`（与 `open_diff` 同步读先例一致）。W2 改为 stat 预检 + 同步读，仍不引入 worker 注入（避免扩大接线面），依据：`open_diff`（`overlay_flows.py:132`）同样在 overlay_flows 里同步 `Document.open`，故保持同步读与既有先例一致。

**测试**：在 `tests/test_overlay_flows_hex.py` 补 `test_open_hex_view_stat_precheck_rejects_without_read`：
```python
def test_open_hex_view_stat_precheck_rejects_without_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file beyond the size gate is refused via stat, read_bytes never called."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 8)
    monkeypatch.setattr("yate.flows.overlay_flows.MAX_HEX_VIEW_SIZE", 4)
    read_called: list[bool] = []
    original_read_bytes = big.read_bytes
    def fake_read_bytes() -> bytes:
        read_called.append(True)
        return original_read_bytes()
    monkeypatch.setattr(big, "read_bytes", fake_read_bytes)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(big)

    assert app.pushed == []
    assert read_called == []  # read_bytes never called
    assert messages[0][0].startswith("file too large for hex view: big.bin")
```

**验收**：
```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_overlay_flows_hex.py::test_open_hex_view_stat_precheck_rejects_without_read -q
```

### W3: 补 async 二进制分支单测

**定位**：`yate/flows/document_flows.py:230-236`（`_open_document_async` 二进制分支）

**问题**：零单测（覆盖率 miss）。

**测试**：在 `tests/test_overlay_flows_hex.py` 补 `test_binary_open_async_pushes_hex_screen`
（主代理修正：DocumentFlows 的 async 公共入口是 `open_path_async`（document_flows.py:285），
不存在 `open_document_async`；二进制移交后 `open_path_async` 返回 `False` 且不报消息）：
```python
def test_binary_open_async_pushes_hex_screen(tmp_path: Path) -> None:
    """An async binary open with a bound opener forwards the path to it."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    session = EditorSession(YateConfig())
    opened: list[Path] = []
    messages: list[tuple[str, str]] = []
    flows = _make_doc_flows(
        session, messages, open_hex_view=opened.append
    )

    async def scenario() -> bool:
        return await flows.open_path_async(binary)

    result = asyncio.run(scenario())

    assert opened == [binary]
    assert messages == []
    assert result is False  # hex handoff reports "not a document" to callers
```

**验收**：
```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_overlay_flows_hex.py::test_binary_open_async_pushes_hex_screen -q
```

### W4: 空会话 `:hex` 守卫

**定位**：`yate/flows/overlay_flows.py:211-222`

**当前逻辑**：
```python
def toggle_hex_view(self) -> None:
    """Toggle between text view and hex view for the active document."""
    if isinstance(self._current_screen(), HexScreen):
        self._pop_screen()
        return
    doc = self.session.doc
    # session.doc is a non-optional property (raises on empty docs) --
    # the only guard needed is the unsaved-buffer one.
    if doc.resolved_path is None:
        self._message("cannot hex view an unsaved buffer", "warn")
        return
    self.open_hex_view(doc.resolved_path)
```

**问题**：空会话（`session.docs` 为空）执行 `:hex` → `session.doc` 抛 IndexError 穿透 `run_command`。

**新逻辑**：
```python
def toggle_hex_view(self) -> None:
    """Toggle between text view and hex view for the active document."""
    if isinstance(self._current_screen(), HexScreen):
        self._pop_screen()
        return
    if not self.session.docs:
        self._message("no document open", "warn")
        return
    doc = self.session.doc
    # session.doc is a non-optional property (safe after the docs-empty
    # guard above); the only remaining guard is the unsaved-buffer one.
    if doc.resolved_path is None:
        self._message("cannot hex view an unsaved buffer", "warn")
        return
    self.open_hex_view(doc.resolved_path)
```

**注释修正**：`overlay_flows.py:217-218` 的注释「session.doc is a non-optional property (raises on empty docs) -- the only guard needed is the unsaved-buffer one」更正为「session.doc is a non-optional property (safe after the docs-empty guard above); the only remaining guard is the unsaved-buffer one」。

**测试**：在 `tests/test_overlay_flows_hex.py` 补 `test_toggle_hex_view_empty_session_warns`：
```python
def test_toggle_hex_view_empty_session_warns() -> None:
    """:hex on an empty session (no docs) warns and does not crash."""
    session = EditorSession(YateConfig())
    assert session.docs == []
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages, session=session)

    flows.toggle_hex_view()

    assert app.pushed == []
    assert app.pops == 0
    assert messages == [("no document open", "warn")]
```

**验收**：
```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_overlay_flows_hex.py::test_toggle_hex_view_empty_session_warns -q
```

### S1: 登记待办（不修）

**定位**：`yate/editor_view/hexview.py:69`（`self._path` 仅写不读）

**处理**：在 plan-e 末尾「遗留待办」段登记，后续可渲染文件名表头或删参。

## 输出

- `_CONTENT_WIDTH` 公式修正为 62；
- stat 预检尺寸闸门（避免大文件整读）；
- async 二进制分支单测覆盖；
- 空会话 `:hex` 守卫；
- S1 登记待办。

## 验收命令（全量回归）

```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_hex_view.py tests/test_overlay_flows_hex.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/editor_view/hexview.py yate/flows/overlay_flows.py tests/test_overlay_flows_hex.py tests/test_hex_view.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

通过判定标准：
- pytest 退出码 0，所有用例通过；
- pyright 零诊断；
- 架构测试无新增违规。

## 风险清单

| 风险 | 缓解 |
|---|---|
| stat 预检引入新 OSError 路径 | 显式 try/except stat，报 "cannot stat" 警告 |
| 空会话守卫与既有 `session.doc` 语义冲突 | 守卫在 `session.doc` 之前，不改变既有语义 |
| async 用例与既有 sync 用例重复 | 同构但走 async 路径，覆盖 :230-236 |

## 回滚路径

恢复 `hexview.py` / `overlay_flows.py` 的原始版本 + 删除新增测试即可回滚。

## 触碰架构边界

- 无（本波次只修复既有逻辑，不新增 import 连线）。

## 遗留待办

- **S1**：`hexview.py:69` `self._path` 仅写不读——后续可渲染文件名表头或删参（登记待办，本波次不修）。
- **S2**（复审 2026-10-24 新增，SUGGESTION）：`overlay_flows.py:210-212` read 兜底行未覆盖——
  补目录路径用例（`open_hex_view(tmp_path)` → "cannot read"）可同时盖行并锁定目录语义。
- **S3**（复审 2026-10-24 新增，SUGGESTION）：stat/read 间残留 TOCTOU 窗口（stat 后文件
  增长则超限不再复检）——read 后补一行 `len(data) > MAX` 复检可彻底关闭；W2 主害已除。
- **既有 flake（非本分支改动）**：`tests/test_app_panes.py::test_split_independent_cursors_and_navigation`
  并行负载下偶发 `assert 0 == 2`，`-n 1` 通过、重跑全绿；该文件未被本任务触碰，
  建议另立 issue 修用例（复审记录，2026-10-24）。

## 【执行】【审核】迭代记录段

### 【执行】wave-5（2026-10-24）

W1-W4 全部落地，S1 按纪律登记未修。验收命令实测：

- `pytest tests/test_hex_view.py tests/test_overlay_flows_hex.py -q -n auto` → 20 passed，EXIT=0；
- `pytest tests/test_hex_view.py::test_hex_view_full_line_width_is_62` 等 4 项单项验收
  （合并一条 pytest 调用，逐项可见）→ 4 passed，EXIT=0；
- `pyright yate/editor_view/hexview.py yate/flows/overlay_flows.py
  tests/test_overlay_flows_hex.py tests/test_hex_view.py` → 0 errors / 0 warnings，EXIT=0；
- `pytest tests/test_architecture.py -q` → 36 passed，EXIT=0；
- 全量 `pytest tests/ -q -n auto` → EXIT=0（1 个既有 skip，无失败）。

偏离记录（3 处，均为计划草稿实现层适配，设计不变）：

1. **W2 测试草稿的 Path patch 方式不可行**：草稿
   `monkeypatch.setattr(big, "read_bytes", fake)` 实测报
   `AttributeError: 'WindowsPath' object attribute 'read_bytes' is read-only`
   （Path 实例属性只读）。改为类级 patch
   `monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)`（pytest 标准做法，
   自动还原），测试意图「read_bytes never called」不变。
2. **既有 unreadable 测试断言伴随更新**（独占文件清单内）：W2 后 missing file
   死在 stat 预检，`test_open_hex_view_unreadable_path_reports` 断言由
   `cannot read nope.bin` 改为 `cannot stat nope.bin`（不改则全量必失败）。
3. **W1 测试的 import 位置**：草稿为函数内 import，按该测试文件顶部统一
   import 风格并入 `from yate.editor_view.hexview import _CONTENT_WIDTH, ...`，
   断言内容不变。

### 【审核】第二轮复审（2026-10-24，提交 f3ffd60）

python-code-review + pr-review 双视角复审：**PASS**。W1-W4 逐项闭环
（W1 公式复算 62 成立；W2 全仓 grep 无 "cannot read" 文案遗漏依赖，目录路径经
read 兜底不回归；W3 覆盖率 miss 自 230-236 收缩为 235；W4 探针路径已堵；
S1 确认未修且登记合规；plan-e 偏离回填核实无误）。五条硬门槛实测：
pyright 0 errors（EXIT=0）；pytest 全量 2958 passed / 9 skipped（EXIT=0）；
架构测试 36 passed（EXIT=0）；覆盖率 91.95% ≥75（首跑 1 failed 经 `-n 1`
复核定性为既有用例并行 flake，重跑全绿，登记遗留待办）；冒烟 114/114 场景
1379/1379 checks（EXIT=0）。新增 2 条 SUGGESTION（S2/S3）登记遗留待办，
不阻塞合并。
