# wave-2 / plan-e：`build_row_text` 的 `sort_key` 形参

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #11。
> 所属波次 `wave-2: plan_d ∥ plan_e ∥ plan_f`，文件与同波另两个子计划互不重叠。

## 输入

- AST 事实：`yate/editor_components/file_manager/model.py:177` 的 `sort_key` 形参在
  函数体内无 `Load` 引用；函数体只消费 `entry` / `stat` / `accent` / `marked` /
  `dir_child_count` / `icon_palette`。
- docstring 自述「*sort_key* is reserved for a later sort-column indicator and does
  not affect the rendering」——明确不影响渲染。
- 调用点清单（**8 处，全部为 `sort_key=` 关键字实参**）：
  `yate/editor_components/file_manager/screen.py:422`、
  `tests/test_file_manager_model.py:115`、`:123`、`:131`、`:140`、`:178`、`:190`、`:196`。

## 独占文件清单（只改这些文件）

- `yate/editor_components/file_manager/model.py`
- `yate/editor_components/file_manager/screen.py`
- `tests/test_file_manager_model.py`

## 具体修改

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/editor_components/file_manager/model.py:184` | `sort_key: SortKey,` | 删除该形参 |
| `yate/editor_components/file_manager/model.py:200-201` | docstring「*sort_key* is reserved ... does not affect the rendering.」 | 删除该句 |
| `yate/editor_components/file_manager/model.py` 导入区 | `SortKey` 导入 | **先复核**：若同文件其它函数仍用 `SortKey` 则保留；无引用则删除（pyright strict） |
| `yate/editor_components/file_manager/screen.py:422` | 调用中的 `sort_key=...` 关键字实参 | 删除该实参 |
| `tests/test_file_manager_model.py` 上述 7 处 | 调用中的 `sort_key=...` 关键字实参 | 删除该实参 |

- 函数名、返回类型 `Text`、其余 6 个形参与整个函数体 **一行不改**。
- 若调用点因删 `sort_key=...` 产生未使用局部名（如构造的排序键对象），
  **不要顺手删除**：本子计划只改调用点实参，未使用局部名属另案（登记表已登记）。
- 注意 `sort_key` 可能由 `self._sort_key` 表达式传入；删除实参即可，不动其它状态。

## 测试用例与验证方案

不新增用例；既有 `tests/test_file_manager_model.py` 共 7 处调用覆盖了标记行、
目录子项徽章、文件大小、图标调色板等全部渲染分支，断言为 `Text` 的 span 内容，
删除前后必须逐字一致。另跑 `tests/test_file_manager*.py` 系列确认屏级调用链。

**验证方案**：局部 pytest 全绿（退出码 0）+ pyright 全仓零诊断 + `git diff` 自查
只含签名、实参与 docstring 删除。

## 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_file_manager_model.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pytest tests/ -q -k file_manager --cov-fail-under=0
git diff --check
```

## 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 8 处关键字实参漏改 → `TypeError` | 调用点清单逐处核对 + 局部 pytest + pyright | `git revert` 本波提交 |
| `SortKey` 导入误删 | 先复核同文件其它引用，再删；pyright 零诊断兜底 | 恢复导入或 revert |
| 未来排序指示器扩展点消失 | issue 目标 1 明确要求删除未使用形参；docstring 自述当前不影响渲染，扩展点可在需要时按新签名重加 | 同上 |
