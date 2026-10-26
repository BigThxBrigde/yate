# perf-audit-fixes-highlighting-plan-j（成员 D1：P2，依赖 plan-d 的 P2-API）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P2。

## 一、目标

**P2（major）**：渲染路径同步重分词——每次编辑推进 `content_version` 后，
`_rebuild_tokens_on_edit`（editor_view/highlighting.py:254-312）在渲染路径对
全部行做 diff（257 行集合推导全行扫 `snapshot[i] != lines[i]`）、整表重建
`rebuilt`/`states`（273 起）、`tuple(lines)` 整表快照拷贝（310 行）。行级 O(1)
复用（281-294）只省分词不省 diff 与拷贝。10 万行文件每键数十毫秒（主循环）。

前置依赖：plan-d（Wave b 的 B1）已落地 `TextBuffer.take_dirty_range()` 契约
（总纲 §三 B1 行；含所有内容变更路径的区间维护）。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_view/highlighting.py`

关联测试（可改/可新增用例）：
- `tests/test_highlighting.py`、`tests/test_highlight.py`、
  `tests/test_syntax_engine.py`、`tests/test_app_render.py`

## 三、实施要点

1. `_rebuild_tokens_on_edit` 开头调 `buf.take_dirty_range()`：
   - None（无区间记录，如 out-of-band version bump）：沿用现有"无变更早退"
     逻辑（259-266 行语义保持）；
   - 有区间 `(lo, hi)`：diff 限定在该区间（区间外行视为未变直接复用 token/
     state——与现 257 行全量 diff 的差异仅在于跳过区间外比较，结果等价；
     区间外的行既有 `rebuilt = list(tokens[:first])` 式复用天然覆盖）；
2. `first = min(changed)` 的下界受 `lo` 约束（区间前行必然未变）；
   `changed.update(range(common, cur_count))`（行数增长部分）保持；
3. 整表快照（310 行 `tuple(lines)`）：改区间快照——仅记录上次同步时区间外的
   "行内容指纹不可行"（行会整体移动），改用轻量方案：快照仍存全行列表引用
   `list(lines)`（引用拷贝 O(N) 但无元素拷贝——tuple(lines) 本身就是引用拷贝，
   不可免），**消除的是 257 行的全量逐行比较与 273 行的整表列表重建**；
   若实测发现引用拷贝仍可免（如改存 `(version, dirty_range, 区间外复用)` 的
   版本化方案），按实现取简，行为不变即可；
4. 后台 worker 全量重算替换缓存后，同步路径的区间状态重置（对齐现有
   `_hl_version` 失效机制）；
5. 多次编辑合并区间由 buffer 侧维护（plan-d 契约），本文件只消费。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_highlighting.py tests/test_highlight.py tests/test_syntax_engine.py tests/test_app_render.py -q
```

补用例：单行编辑后同步分词结果与全量 diff 路径一致（对照断言）；行插入/删除
（区间外行平移）后 token 复用正确；undo 后（buffer 区间来自 _restore）重分词
正确。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

区间 diff 与防抖 worker 缓存交互（worker 替换缓存后区间状态过期）——重置点
对齐现有 version 机制，测试护栏覆盖。回滚：本成员产物单独提交，可独立 revert；
若 plan-d 的 take_dirty_range 未按契约落地，本成员停下上报主代理（不得自行改
buffer.py）。
