# plan-a：`editor_core` 纯文本层修复

- 波次：wave-1（与 plan-b 并行）
- 覆盖：W-10 / W-12 / S-14 / S-17 / S-18 / S-20
- 独占文件清单：
  - `yate/editor_core/project_search.py`
  - `yate/editor_core/search.py`
  - `yate/editor_core/buffer.py`
  - `yate/editor_core/diff.py`
  - `yate/editor_core/document.py`
  - `tests/test_project_search.py`
  - `tests/test_editor_core.py`
  - `tests/test_editor_core_diff.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-10：[project_search.py](../../yate/editor_core/project_search.py) `compile_query`
  第 62-63 行用 `rf"(?:(?<=\W)|^){pattern}(?=\W|$)"`，`pattern` 未分组。
- W-12：同文件 `_search_one_file` 第 145-152 行先 `read_bytes()` 再比较
  `max_file_bytes`。
- S-17：[search.py](../../yate/editor_core/search.py) `replace_all` 第 151-163 行
  直接写 `buffer.lines[row] = "".join(out)`。
- S-18：[diff.py](../../yate/editor_core/diff.py) `DiffResult.align` 第 54-61 行
  直接索引 `self._row_map[row]`。
- S-14：[buffer.py](../../yate/editor_core/buffer.py) `paste` 末行分支第 1050-1059 行
  无条件 `move_line_end(); move_left()`。
- S-20：[document.py](../../yate/editor_core/document.py) `_decode` 第 87-95 行
  以 `"utf-8"` 优先，BOM 文件会把 `\ufeff` 留在首行。

## 二、分步修改

### 步骤 A1：W-10 整词搜索分组

**文件**：`yate/editor_core/project_search.py`

第 62-63 行改为：

```python
    if whole_word:
        pattern = rf"(?:(?<=\W)|^)(?:{pattern})(?=\W|$)"
```

理由：非捕获分组只约束锚点优先级，不改变 `re.escape` 结果，也不引入新捕获组
（替换串的 `\1` 语义保持不变）。

### 步骤 A2：W-12 先查大小再读文件

**文件**：`yate/editor_core/project_search.py`

`_search_one_file` 第 145-152 行改为：

```python
    try:
        if path.stat().st_size > max_file_bytes:
            return [], {}
        data = path.read_bytes()
    except OSError:
        log.debug("project search skipped unreadable file %s", path)
        return [], {}
    if len(data) > max_file_bytes:
        # the file grew between stat and read: keep the post-read guard
        return [], {}
```

### 步骤 A3：S-17 多行替换走 `replace_range`

**文件**：`yate/editor_core/search.py`

把第 145-163 行的逐行写回改为“先构造 `new_lines`，再决定写回方式”：

1. `before = buffer.snapshot()` 保留在非多行分支。
2. 对每个有匹配的行构造 `replacement_line`；把结果收集到 `new_lines`
   （`new_lines = list(buffer.lines)`，仅改写命中行）。
3. 若 `any("\n" in line for line in new_lines)`：
   - 用 `last = len(buffer.lines) - 1`；
   - `buffer.replace_range((0, 0), (last, len(buffer.lines[last])), "\n".join(new_lines))`；
   - 跳过手工 `buffer.commit`（`replace_range` 已生成一个 undo step）。
4. 否则维持原路径：逐行写回、清 anchor、钳制光标、`buffer.commit(before, "step")`。
5. 最后仍执行 `self.update(self.query, buffer)` 并返回 `count`。

注意：`replace_range` 会调用 `_ensure_writable()`；`replace_all` 的只读拒绝语义
由调用方/既有 `BufferReadOnlyError` 传播保持。

### 步骤 A4：S-18 `align` 越界校验

**文件**：`yate/editor_core/diff.py`

`align` 函数体改为：

```python
        if not 0 <= row < len(self._row_map):
            raise IndexError(f"row {row} is outside 0..{len(self._row_map) - 1}")
        return self._row_map[row]
```

### 步骤 A5：S-14 末行空行寄存器粘贴光标

**文件**：`yate/editor_core/buffer.py`

第 1056-1060 行改为：

```python
                self.set_cursor((r, len(self.lines[r])))
                self.insert_text("\n" + text[:-1], kind="step")
                if text[:-1]:
                    self.move_line_end()
                    self.move_left()
                return
```

### 步骤 A6：S-20 BOM 解码

**文件**：`yate/editor_core/document.py`

`_decode` 改为先识别 BOM：

```python
    @staticmethod
    def _decode(raw: bytes) -> tuple[str, str]:
        if raw.startswith(b"\xef\xbb\xbf"):
            try:
                return raw.decode("utf-8-sig"), "utf-8-sig"
            except UnicodeDecodeError:
                pass
        for enc in ("utf-8", locale.getpreferredencoding(False), "cp1252"):
            ...
```

`save()` 用 `self.encoding` 编码，因此 `utf-8-sig` 会在回写时恢复 BOM，形成
字节级往返一致。

## 三、新增测试

### `tests/test_project_search.py`

1. `test_compile_query_whole_word_groups_a_regex_alternation`
   - 输入：`compile_query(r"foo|bar", use_regex=True, whole_word=True)`
   - 断言：`xbar` 不命中、`foobar` 不命中、`foo bar` 命中两段。
2. `test_search_files_stats_before_reading_an_oversized_file`
   - 准备：文件写入 10 字节；`monkeypatch.setattr(Path, "read_bytes", _boom)`
     （`_boom` 抛 `AssertionError`）。
   - 调用：`search_files([path], "x", max_file_bytes=1)`
   - 断言：返回 `[]` 且 `read_bytes` 未被调用。

### `tests/test_editor_core.py`

3. `test_replace_all_with_multiline_replacement_splits_rows`
   - 准备：`TextBuffer("cat dog")`，`engine.update("cat", buf)`
   - 操作：`engine.replace_all(buf, "x\ny")`
   - 断言：`buf.lines == ["x", "y dog"]`、`buf.line_count == 2`、返回 1。
   - 追加：`buf.undo()` 后文本恢复 `"cat dog"`（单步撤销）。
4. `test_paste_linewise_empty_register_at_last_line_keeps_cursor`
   - 准备：`TextBuffer("abc")`，`buf.register = "\n"`，光标行 0。
   - 操作：`buf.paste(below=True)`
   - 断言：`buf.lines == ["abc", ""]`、`buf.cursor == (1, 0)`。
5. `test_open_strips_bom_and_save_keeps_it`
   - 准备：`path.write_bytes(b"\xef\xbb\xbfhello\n")`
   - 操作：`doc = Document.open(path)`；`doc.buffer.insert_text("x")`；`doc.save()`
   - 断言：`doc.buffer.lines[0] == "hello"`、`doc.encoding == "utf-8-sig"`、
     `path.read_bytes().startswith(b"\xef\xbb\xbf")`。

### `tests/test_editor_core_diff.py`

6. `test_align_rejects_out_of_range_rows`
   - 准备：`result = diff_lines(["a", "b"], ["a", "b"])`
   - 断言：`pytest.raises(IndexError)` 覆盖 `align(-1)` 与 `align(result.a_lines)`。

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_project_search.py tests/test_editor_core.py tests/test_editor_core_diff.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core tests/test_project_search.py tests/test_editor_core.py tests/test_editor_core_diff.py
```

通过判定：两条命令退出码均为 0；pytest 输出无 failed/error。

## 五、风险与回滚

- `replace_range` 整段替换会重置光标；测试只要求行结构正确与单步撤销，
  不要求保留原光标列（`replace_all` 之后光标本来就会被钳制）。
- `_decode` 返回 `"utf-8-sig"` 会让新保存的 BOM 文件继续带 BOM；无 BOM 文件走
  原 `"utf-8"` 路径，行为不变。
- 回滚：本子计划单独提交，失败时回滚该提交即可；无跨文件不可逆状态。
