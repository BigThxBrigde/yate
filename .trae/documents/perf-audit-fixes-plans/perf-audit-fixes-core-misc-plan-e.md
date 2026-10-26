# perf-audit-fixes-core-misc-plan-e（成员 B2：P12 + P18 + P16）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Minor P12/P18/P16。

## 一、目标

1. **P12（minor）**：`Search.replace_current`（search.py:129-131）单行替换后
   `self.update(self.query, buffer)` 全文档重扫；
2. **P18（minor）**：词移动（words.py:15-49）扫描循环每字符一次
   `_WORD_CHARS.match(ch)` 调用，线性斜率比整段匹配高一个量级；
3. **P16（minor）**：`ChunkedBinaryFile.read`（chunked.py:318-329）对读到的每块
   遍历整个 `_dirty` 字典；`apply_edit`（332-340）只增不清 → O(编辑数²)。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_core/search.py`
- `yate/editor_core/words.py`
- `yate/editor_core/chunked.py`

关联测试（可改/可新增用例）：
- `tests/test_project_search.py`、`tests/test_chunked.py`、
  `tests/test_hex_view.py`、`tests/test_app_find.py`、
  `tests/test_app_find_replace.py`

## 三、实施要点

### P12（search.py）
1. `replace_current` 替换后不再调 `self.update(...)` 全扫；
2. 改为：该行重扫（对该行 `pattern.finditer` 重建该行匹配）；同 row 后续匹配
   按列差 `len(replacement) - (match.end - match.start)` 平移；后续行不变；
3. `index`（活动匹配索引）语义保持：替换点之后的匹配序号相应调整，以现有
   行为测试为准（替换后通常仍指向"下一个"匹配——对齐现状）。

### P18（words.py）
1. `next_word_start` / `prev_word_start` / `word_end` 等扫描循环改为整段贪心：
   `m = _WORD_CHARS.match(line, i)` 一次吃掉整个词段（或 `_WORD_RE.findall` 带
   位置推进），把每字符一次正则调用降为每词一次；
2. 语义零变化：词边界判定结果必须与逐字符版完全一致（名下测试 + vim 词移动
   行为测试护栏）；
3. 非词字符段同理（若当前用非词匹配驱动，同样整段化）。

### P16（chunked.py）
1. `_dirty: dict[int, int]`（offset → byte）改为按块分桶：
   `dict[int, dict[int, int]]`（block_index → {offset: byte}）；
2. `read` 路径：只查当前块索引的桶（无桶即整块干净）；
3. `apply_edit` 写入对应块桶；保存（flush/write-through）成功后按现有清空
   语义清理对应桶（确认现有保存路径对 `_dirty` 的清理点，行为对齐）；
4. 对外行为（读到的字节含脏覆盖、保存落盘）零变化。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_project_search.py tests/test_chunked.py tests/test_hex_view.py tests/test_app_find.py tests/test_app_find_replace.py -q
```

补用例：P12 连续 replace_current 的匹配序列与活动索引语义；P16 多块脏字节读
与保存后清空；P18 词移动结果与逐字符版一致（可加对照断言）。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

P12/P16 均为索引/缓存重构，行为护栏充分（5 个测试文件）；P18 语义一致性靠
对照测试。回滚：本成员产物单独提交，可独立 revert。
