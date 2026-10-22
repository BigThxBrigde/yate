# plan-b：LSP / 键弦 / 键位记法 / 语法后端 / 终端后端修复

- 波次：wave-1（与 plan-a 并行）
- 覆盖：W-05 / W-07 / W-11 / W-13 / S-12 / S-13 / S-19
- 独占文件清单：
  - `yate/editor_lsp/parsing.py`
  - `yate/editor_lsp/protocol.py`
  - `yate/keyproto/frames.py`
  - `yate/keymaps/keys.py`
  - `yate/editor_syntax/ts_backend/languages.py`
  - `yate/editor_term/pty_proc.py`
  - `tests/test_lsp_parsing.py`
  - `tests/test_lsp.py`
  - `tests/test_keyproto.py`
  - `tests/test_key_notation.py`
  - `tests/test_ts_backend.py`
  - `tests/test_pty_proc.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-11：[parsing.py](../../yate/editor_lsp/parsing.py) `_range_to_buffer_cols`
  第 115-123 行只对取列做保护，返回的 `r0/r1` 未钳制；`_from_utf16` 对 ASCII
  列也不钳制。
- S-19：[protocol.py](../../yate/editor_lsp/protocol.py) `uri_to_path` 第 161-173 行
  先用 `urlparse`，`C:\foo\bar` 被解析成 scheme=`c`。
- W-05：[frames.py](../../yate/keyproto/frames.py) `char_text` 第 94-97 行直接
  `chr(self.char)`。
- W-07：[keys.py](../../yate/keymaps/keys.py) `parse_key` 第 93-107 行
  `modifiers = set(tokens[:-1])` 后只识别 shift/alt/ctrl，未知修饰词被静默忽略。
- S-12：[languages.py](../../yate/editor_syntax/ts_backend/languages.py)
  `load_language` 第 240-277 行接受任意名称；`drop_language` 第 280-295 行对
  `BUILTIN_PACKS` 名直接返回。
- W-13：[pty_proc.py](../../yate/editor_term/pty_proc.py) 读循环第 600-620 行
  `read_bytes` 只初始化一次，失败读会复用上一次计数。
- S-13：同文件第 511-518 行第二条 `CreatePipe` 失败时，第一条管道未关闭。

## 二、分步修改

### 步骤 B1：W-11 钳制 LSP 返回的行列

**文件**：`yate/editor_lsp/parsing.py`

`_range_to_buffer_cols` 改为：

```python
    r0, c0, r1, c1 = rng
    lines = doc.buffer.lines
    last = len(lines) - 1
    r0 = max(0, min(r0, last))
    r1 = max(0, min(r1, last))
    line0 = lines[r0]
    line1 = lines[r1]
    col0 = min(max(0, _from_utf16(line0, c0)), len(line0))
    col1 = min(max(0, _from_utf16(line1, c1)), len(line1))
    return (r0, col0, r1, col1)
```

（`lines` 由 `TextBuffer` 保证至少一行。）

### 步骤 B2：S-19 容忍裸 Windows 盘符路径

**文件**：`yate/editor_lsp/protocol.py`

`uri_to_path` 开头加盘符前缀判定：

```python
    if len(uri) >= 2 and uri[0].isascii() and uri[0].isalpha() and uri[1] == ":":
        return Path(uri)
```

放在 `urlparse` 之前；`file://` URI 的 scheme 长度大于 1，不受影响。

### 步骤 B3：W-05 `char_text` 校验码点

**文件**：`yate/keyproto/frames.py`

```python
    @property
    def char_text(self) -> str:
        """Return the frame's UCS character as text (``""`` when absent)."""
        if not 0 < self.char <= 0x10FFFF:
            return ""
        return chr(self.char)
```

### 步骤 B4：W-07 拒绝未知修饰词

**文件**：`yate/keymaps/keys.py`

`parse_key` 中 `modifiers = set(tokens[:-1])` 之后加：

```python
    unknown = modifiers - {"shift", "alt", "ctrl"}
    if unknown:
        raise ValueError(f"unknown modifier(s) in spec: {spec!r}")
```

再解析 key 名；保持已有的 shift/ctrl 不支持组合的显式 `raise`。

### 步骤 B5：S-12 拒绝覆盖内置 tree-sitter 语言

**文件**：`yate/editor_syntax/ts_backend/languages.py`

`load_language` 在 `key = name.lower()` 之后加：

```python
    if key in BUILTIN_PACKS:
        raise ValueError(
            f"cannot replace the built-in tree-sitter language {name!r}"
        )
```

同步更新 docstring 一句：内置语言由 `BUILTIN_PACKS` 拥有，扩展不得覆盖。

### 步骤 B6：W-13 / S-13 ConPTY 修正

**文件**：`yate/editor_term/pty_proc.py`

1. 第 515-518 行第二条 `CreatePipe` 失败时关闭第一条管道：

```python
        if not k["CreatePipe"](ctypes.byref(out_read), ctypes.byref(out_write), None, 0):
            k["CloseHandle"](in_read)
            k["CloseHandle"](in_write)
            raise PtyProcessError("CreatePipe (output) failed")
```

2. 读循环第 616-620 行改为：

```python
                count = read_bytes.value
                if ok and count:
                    self._owner.emit_output(buffer.raw[:count])
                if not ok or count == 0:
                    break
```

## 三、新增测试

### `tests/test_lsp_parsing.py`

1. `test_range_to_buffer_cols_clamps_negative_and_past_end_rows`
   - 准备：`Document(TextBuffer("aaa\nbbb\nccc\nddd"))`（4 行）。
   - 断言：`_range_to_buffer_cols((-1, 0, 9, 0), doc) == (0, 0, 3, 0)`。
2. `test_range_to_buffer_cols_clamps_columns_to_the_line_length`
   - 断言：`_range_to_buffer_cols((0, 99, 1, 99), doc)` 的列等于两行长度。

### `tests/test_lsp.py`

3. `test_uri_to_path_keeps_a_bare_windows_drive_path`
   - 断言：`protocol.uri_to_path("C:\\foo\\bar") == Path("C:\\foo\\bar")`
     （跨平台按 `Path` 字符串比较）。
   - 追加：`protocol.uri_to_path("D:/work/x.py") == Path("D:/work/x.py")`。

### `tests/test_keyproto.py`

4. `test_win32_frame_char_text_rejects_out_of_range_codepoints`
   - 断言：`Win32InputFrame(1, 0, 0x110000, 0, 0, 0).char_text == ""`；
     `char=-1` 同样为 `""`；`char=0x41` 为 `"A"`。

### `tests/test_key_notation.py`

5. `test_parse_key_rejects_unknown_modifiers`
   - 参数化：`"<meta-s>"` / `"<cmd-s>"` / `"<ctr-s>"`。
   - 断言：`pytest.raises(ValueError, match="unknown modifier")`。

### `tests/test_ts_backend.py`

6. `test_load_language_refuses_a_builtin_pack_name`
   - 准备：`ts = tree_sitter()` 可用时，构造一个最小 `Language`；不可用则
     `pytest.skip`。
   - 断言：`load_language("python", lang, "(identifier) @variable")` 抛
     `ValueError`，且 `_LANGS["python"]` 原对象未被替换。
   - 追加：随后 `drop_language("python")` 仍是 no-op（不删除内置项）。

### `tests/test_pty_proc.py`（均带 `@pytest.mark.skipif(os.name != "nt", ...)`）

7. `test_conpty_read_loop_does_not_repeat_a_stale_count`
   - 准备：真实 `PtyProcess` 的 `_ConPty`，`_out_read = 0x1000`，`_proc_info=None`；
     把 `_owner.emit_output` 换成记录器；`_kernel32["ReadFile"]` 第一次写回
     3 字节并返回 1，第二次返回 0 且不写 `written`。
   - 断言：`impl.read_loop()` 后记录器只收到一次 `b"abc"`。
8. `test_conpty_second_create_pipe_failure_closes_the_first_pair`
   - 准备：把 `_kernel32` 换成 fake：`CreatePipe` 第一次成功（写入两个句柄值），
     第二次返回 0；`CloseHandle` 记录参数。
   - 断言：`_spawn_locked()` 抛 `PtyProcessError`，记录器包含第一条管道的
     `in_read` / `in_write` 两个句柄。

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_parsing.py tests/test_lsp.py tests/test_keyproto.py tests/test_key_notation.py tests/test_ts_backend.py tests/test_pty_proc.py -q
.venv\Scripts\python.exe -m pyright yate/editor_lsp yate/keyproto yate/keymaps/keys.py yate/editor_syntax/ts_backend yate/editor_term tests/test_lsp_parsing.py tests/test_lsp.py tests/test_keyproto.py tests/test_key_notation.py tests/test_ts_backend.py tests/test_pty_proc.py
```

通过判定：两条命令退出码均为 0。

## 五、风险与回滚

- `_from_utf16` 对负列返回 0，钳制只补正行号与超长列；不改变合法输入行为。
- `load_language` 拒绝内置名会让尝试覆盖的扩展在 `setup` 阶段失败；loader 的
  A13 快照-回滚路径已覆盖，属预期行为。
- ConPTY 两条测试仅 Windows 实机执行；POSIX CI 自动跳过。
- 回滚：本子计划单独提交；无持久化状态。
