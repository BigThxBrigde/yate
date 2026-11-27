# P2：O(k) diff3 区域分类（计划 d）

> **实施状态**：✅ 已实施 —— 2026-11-20（`78168722`，O(k) 游标 + 等价用例）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/editor_core/diff.py:133-200` 对每个区域调用 `_side_span`（`:261-297`）和四次 `any(...)`（`:161-169`）；两者都从头开始扫描按基线行排序的序列，复杂度为 O(k^2)。按契约，difflib opcodes 有序且互不重叠；`_merge_spans`（`:250-258`）也返回排序并合并后的区间。

## 独占文件

- `../../../yate/editor_core/diff.py`
- `../../../tests/test_editor_core_diff.py`

## 设计

1. 保持 `diff3_regions`、`_merge_spans`、`_side_span`、`MergeRegion` 的公开形态和区域顺序不变。
2. 每侧预计算一次按基线顺序排列的非相等区间 `[(i1, i2, j1, j2), ...]`（已在 `:150-151` 处生成）。
3. 用单调游标替换每一侧的重复扫描；当 `classify` 按递增的基线顺序访问区域时，游标在这些有序的区间/opcodes 上前进。对于区域 `[start, end)`：
   - 非空区间的触及判定：`s < end and e > start`；零长度区间（纯插入）的判定：`s <= start < e or s == start`（逐字保留当前的两条子句规则）；
   - 相应侧的区间必须复现 `_side_span` 的结果：相等 opcodes 按偏移量映射，非相等 opcodes 贡献其完整的 `j1:j2` 片段，并由 `pieces[0][0] .. pieces[-1][1]` 限定结果边界。
4. 可用一个小型显式游标辅助函数（模块私有函数，不引入新的类协议）持有该单调索引；嵌套不超过 3 层，使用 guard 子句提前返回。如果逐字节保留 `_side_span` 更简单，则将其保留为测试所用的参考实现，但不要在 `classify` 中调用它。
5. 对重叠/相邻区间、在开头/中间/结尾的插入，或完全相同的编辑，行为均不改变。

## 测试（位于 `../../../tests/test_editor_core_diff.py`）

- `test_diff3_cursor_classification_matches_reference_for_generated_inputs`：以确定方式（固定种子）生成 100 组小型 base/local/remote 行序列三元组，包括空序列、在 0/中间/结尾的纯插入、删除以及重叠编辑；将新的 `diff3_regions` 输出与一个复制了旧 `classify` + `_side_span` 逻辑的本地参考函数逐字段比较。断言完整区域列表一致且没有异常。
- `test_diff3_regions_keeps_zero_length_insertion_semantics`：保持 `:120-159` 处的六个现有测试不变（本地在开头插入、远端在中间插入、在文件末尾插入、冲突、不相交、完全相同）。
- `test_diff3_regions_classify_is_linear_in_region_count`：构造 400 处不相交的单行改动；如有需要，用 monkeypatch 的 spy 统计 opcode/区间访问次数；断言访问次数以某个小常数乘以区域数为上界（不存在二次重复扫描）。若 spy 不可行，则断言输出正确，并辅以不依赖时钟的结构检查（游标辅助函数每个区域调用一次）。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_core_diff.py tests/test_diff_integration.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core/diff.py tests/test_editor_core_diff.py
```

## 风险 / 回滚

风险：零长度区间以及在 EOF 处插入的边界。回滚：恢复 `classify` 内部的 `_side_span` 调用；此时生成输入等价性测试也应针对恢复后的实现通过。
