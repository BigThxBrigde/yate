# P1：通过逐行索引诊断 `diagnostic_at`（计划 a）

> **实施状态**：✅ 已实施 —— 2026-11-20（`ac4eda02`，目标测试与 pyright exit 0）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/editor_lsp/manager.py:763-773` 在每次发布时重建 `_diagnostics_by_row[uri][row]`；`:780-784` 的 `diagnostics_for` 复制整张表，`:793-808` 的 `diagnostic_at` 扫描它。热点路径是 `../../../yate/editor.py:447-453,499-503` -> `../../../yate/flows/lsp_sync.py:95-101`。

## 独占文件

- `../../../yate/editor_lsp/manager.py`
- `../../../tests/test_lsp.py`

## 设计

1. 保持 `_diagnostics` 为唯一事实来源，并保持 `_index_diagnostics` / `_forget_diagnostics` 不变。
2. 将 `diagnostic_at` 重写为：
   - 当 `doc.path is None` 时返回 `None`（与 `diagnostics_for` 一致）；
   - 解析 `uri = self._uri(doc)`，并以 `self._diagnostics_by_row.get(uri, {}).get(row, ())` 作为候选集合；
   - 逐字沿用**现有的**覆盖判定谓词：单行 `d.start_col <= col < max(d.end_col, d.start_col + 1)`；首行 `col >= d.start_col`；末行 `col <= d.end_col`；中间行始终覆盖；
   - 保留 `best is None or d.severity < best.severity`，使数值最小（最严重）的 severity 胜出；并列时保留第一个被索引的诊断（发布顺序，与旧列表顺序一致）。
3. 不改动 `diagnostics_for`、`diagnostics_on_line`、`counts_for` 以及任何公开签名。不新增缓存：索引在每次发布时已经重建。

## 测试（位于 `../../../tests/test_lsp.py`，紧邻 `:916` 处的 `test_diagnostics_delivery_and_queries`）

- `test_diagnostic_at_matches_linear_reference_for_multirow_matrix`：发布一组由单行、多行（3 行）、零宽（`end_col == start_col`）以及 `doc.path is None` 诊断构成的矩阵；对 `(row, col)` 网格上的每个点，将 `manager.diagnostic_at(doc, row, col)` 与一个本地参考函数比较，该参考函数实现旧逻辑——对 `diagnostics_for(doc)` 执行完全相同的旧循环。断言返回对象的 `severity`、`start_row` 和 `start_col` 相等（在适用处两者均为 `None`）。
- `test_diagnostic_at_prefers_most_severe_on_same_row`：在同一行发布 severity 分别为 3、1、2 的三条诊断；断言返回的那条 severity 为 1；再加入一对相同 severity 的诊断，断言先发布的那条胜出。
- `test_diagnostic_at_large_d_uses_row_index`：在第 0 行发布 2000 条诊断，另在第 40 行发布一条、再发布一条跨越第 38-42 行的诊断；断言 `diagnostic_at(doc, 40, 0)` 返回那条跨行诊断；在调用期间 monkeypatch `manager.diagnostics_for` 使其抛出 `AssertionError("full table copy used")`，并断言没有异常抛出（证明热点路径不再复制整张表）。
- 保持 `test_diagnostics_row_index_multi_row_and_rebuild`（`:949`）和 `test_diagnostics_index_cleared_with_table`（`:1018`）不变；它们用于验证重建/失效。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q
.venv\Scripts\python.exe -m pyright yate/editor_lsp/manager.py tests/test_lsp.py
```

通过：exit code 0，整个矩阵上新旧行为等价，`diagnostic_at` 中不发生整表复制。

## 风险 / 回滚

风险：多行边界语义或并列裁决发生偏移。回滚：恢复原始的 `diagnostic_at` 函数体；逐行索引与测试可以保留。
