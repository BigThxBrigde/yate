# plan-a（W-A）：核心模型与 LSP — 8 条

- 波次：W-A（可并行起点）
- 独占文件（**只改这些**）：
  `yate/editor_core/diff.py`、`yate/editor_core/buffer.py`、`yate/editor_core/document.py`、
  `yate/editor_core/search.py`、`yate/editor_lsp/parsing.py`、`yate/editor_lsp/manager.py`；
  测试：`tests/test_editor_core_diff.py`、`tests/test_editor_core.py`、`tests/test_lsp_parsing.py`、
  `tests/test_lsp.py`、`tests/test_project_search.py`（不存在则新建同名文件）
- 输入：评审记录 §四 B-1、§五 M-1/M-2/M-3、§六 m-9/m-10/m-11/m-19

## 1. B-1（BLOCKER）`yate/editor_core/diff.py:247-271` 零长度 base 区间

**根因**：`SequenceMatcher` 的 `insert` opcode 在 base 侧区间为零长度 `(k, k)`；
`_merge_spans` 保留孤立零长度区间，`_side_span` 的两条跳过条件对 `(k, k)` 把所有 opcode 跳过 → `pieces` 空 → `raise`。

**修法（两处，均在 `diff.py`）**：

1. `_side_span` 顶部加零长度早退：
   - `start == end` 时遍历 `ops`，取第一个满足 `i1 <= start <= i2` 的 opcode：
     - `tag == "insert"`：返回 `(j1, j2)`（该侧插入块的真实区间）；
     - `tag == "equal"`：返回 `(j1 + start - i1, j1 + start - i1)`（折叠映射）；
     - `tag == "replace"`：返回 `(j1, j2)`。
   - 若遍历完仍未命中（不该发生），返回 `(0, 0)` 而非 `raise`——崩溃面在正常使用下不可接受，
     由调用方 `classify` 的 touched 判定兜底。
2. `classify`（:151-175）的 touched 判定补零长度口径：`base_start == base_end` 时
   用 `s <= base_start < e`（插入点落在变更区间内即算该侧 touched），使单侧纯插入被分类为
   `"local"` / `"remote"` 而不是 `"same"`（否则 `diffview` 拿不到该区域，插入行不着色）。

**回归测试**（`tests/test_editor_core_diff.py`，修复前必须红）：
- `test_diff3_regions_reports_a_local_insertion_at_start`
- `test_diff3_regions_reports_a_remote_insertion_in_the_middle`
- `test_diff3_regions_reports_an_insertion_at_end_of_file`
  断言：不抛异常；对应区域 `kind` 为 `local` / `remote`；`local_start/local_end`（或 remote 侧）
  恰好覆盖插入行；`base_start == base_end == k`。
- `test_diffview_opens_a_three_way_merge_with_a_one_sided_insertion`（`tests/test_diffview.py`
  若归属 W-B 则改由 W-B 补，此处只钉 L0 行为）

## 2. M-1（MAJOR）`yate/editor_core/buffer.py:1063-1067` 行式粘贴光标

**根因**：`insert_text(text[:-1] + "\n")` 后 `move_line_end()`/`move_left()` 作用于
被挤下去的**原行**（`_apply_text` 返回插入点之后的换行位置），与末行分支（:1052-1061）不一致。

**修法**：把 `move_line_end()`/`move_left()` 换成显式定位（与末行分支语义一致：
光标落在**粘贴块末行**的最后一个字符上）：

```python
block = text[:-1].split("\n")
self.insert_text(text[:-1] + "\n", kind="step")
last_row = target + len(block) - 1
self.set_cursor((last_row, max(0, len(self.lines[last_row]) - 1)))
```

`below=False`（`P`）时 `target = r`，公式同样成立（块占 `r … r+len(block)-1`）。

**回归测试**（`tests/test_editor_core.py`）：
- `test_linewise_paste_below_leaves_cursor_on_the_last_pasted_line`（三行文档、`(1,0)`、寄存器 `"aaa\n"` → 光标 `(2,2)`）
- `test_linewise_paste_above_leaves_cursor_on_the_last_pasted_line`（多行寄存器）
- `test_linewise_paste_with_count_appends_contiguous_blocks`（模拟 `3p`：连续三次 `paste(below=True)`
  后三块连续且块间无原行穿插）
- 既有 `tests/test_editor_core.py:1126` 附近的末行分支用例必须保持绿（不得改断言）

## 3. M-2（MAJOR）`yate/editor_lsp/parsing.py:215` 非列表 `diagnostics`

**修法**：`_parse_diagnostics` 在构建 `result` 前加

```python
if not isinstance(raw, list):
    log.warning("malformed diagnostics payload (%s); ignored", type(raw).__name__)
    return []
```

**回归测试**（`tests/test_lsp_parsing.py`）：
`test_parse_diagnostics_ignores_a_null_payload`（`None` → `[]`，不抛）、
`test_parse_diagnostics_ignores_a_dict_payload`。

## 4. M-3（MAJOR）`yate/editor_lsp/manager.py:136-137` 重注册泄漏 client

**修法**：摘除前先停：

```python
for key in [k for k in self._clients if k[0] == config.name]:
    client = self._clients.pop(key, None)
    if client is not None:
        self._spawn_bg(client.stop())
```

（`_spawn_bg` 已存在，:114 `_bg_tasks` 持有引用；`stop()` 幂等，失败只记日志。）

**回归测试**（`tests/test_lsp.py`，用现有 fake client 工厂）：
`test_reregistering_a_server_stops_the_old_client`（断言旧 client 的 `stop` 被调用恰好一次）。

## 5. m-9（MINOR）`yate/editor_core/search.py:100-101` 绕过 `set_cursor`

**修法**：改为 `buffer.set_cursor((match.row, match.end))` 再设 `buffer.anchor = (match.row, match.start)`；
若 `set_cursor` 会清 anchor，则先 `set_cursor` 再赋 anchor（顺序以实测为准），保证 `_goal_col` 被清空。

**回归测试**（`tests/test_project_search.py`）：
`test_search_jump_clears_the_vertical_goal_column`（先 `move_down` 建立 goal col，再跳转，随后 `move_down`
应落在匹配行的相邻行而非旧目标列）。

## 6. m-10（MINOR）`yate/editor_core/document.py:229-230` 先改 path 后写盘

**修法**：整个 `save()` 内先算局部 `target`：
`target = Path(path) if path is not None else self.path`；`target is None` → 现有 `ValueError`；
写盘（mkstemp → fdopen → `os.replace`）成功后**最后**执行 `self.path = target`。

**回归测试**（`tests/test_editor_core.py`）：
`test_failed_save_as_keeps_the_previous_path`（保存到不可写目录 → 抛 `OSError`，`doc.path` 仍是原路径）。

## 7. m-11（MINOR）`yate/editor_core/buffer.py:1030-1031` 无效赋值

**修法**：删除 `self.anchor = (r, 0)` 与 `self.cursor = (r, c)` 两行（`_delete_range` 不读 anchor，
且 `cursor` 赋值与当前值相同），保留 `self.cursor = (r, 0)` / `self.anchor = None`。

## 8. m-19（MINOR）`yate/editor_lsp/parsing.py:67,91,186` 缺 `Any` 理由

**修法**：三处签名补 `# noqa: Any - LSP wire payload, untyped server data`（行宽 ≤100，必要时拆行）。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_editor_core_diff.py tests/test_editor_core.py tests/test_lsp_parsing.py tests/test_lsp.py tests/test_project_search.py -q --cov-fail-under=0
```

判定：pyright 0/0/0；pytest exit 0；B-1 / M-1 / M-2 的新用例在修复前红、修复后绿（红绿证据写入回填段）。

## 风险与回滚

- B-1 的 touched 口径改动会影响 `diffview` 的区域集合：若既有 `tests/test_diffview.py` 变红，
  先核对是否属于"纯插入现在被正确上报"的预期变化，写入偏离记录；不得为了让旧断言通过而回退分类语义。
- M-1 的光标语义若与既有 pin 用例冲突，以 vim 行为为准并在偏离段说明。
- 回滚：单条 `git revert <sha>`；本计划不含跨条依赖。
