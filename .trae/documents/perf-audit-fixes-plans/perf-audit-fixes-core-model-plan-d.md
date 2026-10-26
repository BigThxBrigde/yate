# perf-audit-fixes-core-model-plan-d（成员 B1：P1 + P13 + P14 + P2-API）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P1、§Minor P13/P14。

## 一、目标

1. **P1（major）**：快照式撤销每击键 2 次全文档行列表拷贝 + 最多 3 次全量比较
   （`_snapshot`:319-322、`_commit`:340-364）；四个早退路径在快照之后才返回
   （`delete_backward`:731-734、`delete_forward`:764-768、`move_line`:1152-1156、
   `join_lines`:1168-1171）；每 `_Edit` 持 before/after 双快照，20 万行文件撤销栈
   峰值 GB 级指针；
2. **P13（minor）**：多光标重映射 O(k²)（`_remap_after_insert`:86-90 每点全字典
   遍历；`_multi_points`:793 对列表做成员测试）与每点 O(N) 行拼接；
3. **P14（minor）**：`Document.modified`（document.py:190-194）每键 O(N) 回退
   比较 `tuple(self.buffer.lines) != self._saved_lines`；
4. **P2-API（接口契约，Wave d 的 plan-j 消费）**：buffer 暴露变更行区间。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_core/buffer.py`
- `yate/editor_core/document.py`

关联测试（可改/可新增用例）：
- `tests/test_editor_core.py`、`tests/test_document_chunked.py`、
  `tests/test_session.py`、`tests/test_clipboard.py`、
- `tests/test_textobjects.py`、`tests/test_vim_keymap.py`

## 三、实施要点

### P1：撤销改增量 delta（目标方案）
1. `_Edit` 结构改为记录变更区间：`(kind, weight, top_row, old_lines, bottom_row, new_lines, cursor_before, cursor_after, ...)`——具体字段按实现定，核心是
   只存**被改动行区间**的旧行列表与新行列表（替换行数可不同），外加光标/多光标
   状态对；行数少的编辑（绝大多数击键）只存 1-3 行；
2. undo/redo 用区间替换还原（旧行 ↔ 新行互换写回 `self.lines[row_a:row_b+1]`）；
3. char 合并（`_commit` kind=="char" 分支）：合并条件从 `top.after == before`
   全量比较改为"编辑区间相邻/重叠且均为单行内小编辑"的轻量判定（按实现定，
   保持现有合并粒度行为一致——以现有测试为准）；
4. `after == before` 无变化早退：改为比较变更前的操作是否实际改动了行/光标
   （多数方法已知是否产生编辑；无法便宜判定时才做区间比较）；
5. 四个早退卫语句前移到快照之前；
6. `content_version`/`content_edits` 推进语义不变（lines_changed 判定改为区间
   是否非空）；
7. **回退路线**（若撤销语义回归不可控）：保留快照结构，仅做"复用 before 元组 +
   变更区间比较 + 早退前移"，内存驻留问题登记待办。偏离必须登记总纲 §六。

### P13
1. `_multi_points`（793）：`if (r, c) not in points` 列表成员测试改 set；
2. `_remap_after_insert`（86-90）：重映射按行偏移运行增量——点先按行排序，
   一次遍历累计行偏移，避免每点全字典重遍历；列偏移仅影响首行同列点，
   单独小循环处理。

### P14（document.py）
- 删除 `tuple(self.buffer.lines) != self._saved_lines` 回退（190-194）；
  `modified` 用 `content_edits != self._saved_content_edits`（或等价 O(1) 判定）
  ——确认 `_saved_edits` 记录时同时记录当时 content_edits/content_version；
  行为一致性以现有测试为准（原回退是为覆盖"version 推进但文本还原"场景，
  若该场景有测试，改为比较 content_edits 计数即可覆盖：编辑再撤销 content_edits
  不回退——确认语义后按现有测试调整；有行为差异时在报告中显式登记）。

### P2-API（接口契约，签名冻结）
```python
def take_dirty_range(self) -> tuple[int, int] | None:
    """Return the inclusive row range edited since the last call, or None."""
```
- 所有内容变更路径维护 `_dirty_top/_dirty_bottom`（含 insert/delete/paste/
  undo/redo/_restore/fill_lines/extend_placeholders/replace 系/多光标系）；
  取走后清空；
- 区间合并语义：多次编辑取并集（min/max）；
- 该 API 供 plan-j 的高亮同步 diff 限定区间；**本成员不改 highlighting.py**。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_editor_core.py tests/test_document_chunked.py tests/test_session.py tests/test_clipboard.py tests/test_textobjects.py tests/test_vim_keymap.py -q
```

补用例：undo/redo 跨区间替换（行数增减）往返一致；char 合并粒度与改前一致；
多光标大批量点（≥50）重映射正确性；take_dirty_range 并集/取走清空语义；
modified 在"编辑后撤销"下的行为与改前对齐（有差异则登记）。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离（尤其 P1 是否走回退路线）与未解决项。

## 六、风险与回滚

撤销语义回归为最高风险：以名下 6 个测试文件为护栏，任何行为差异必须显式登记
或走回退路线。回滚：本成员产物单独提交，可独立 revert。
