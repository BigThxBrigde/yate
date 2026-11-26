# plan-b：`build_content_changes` 线格式单测（wave-1）

> 主计划：[`../lsp-incremental-sync-acceptance-plan.md`](../lsp-incremental-sync-acceptance-plan.md)
> 独占文件：`../../../tests/test_lsp_diff.py`（**只改这一文件**）。
> 产品源码：`yate/` 零改动。

## 一、输入

- `../../../yate/editor_lsp/diff.py:260-287`：`build_content_changes(old_lines, new_lines)` 把 `ChangePatch` 转成 `{range, rangeLength, text}`。
- `../../../tests/test_lsp_diff.py:245-252`：跨行 splice 的既有 patch 断言（start `(0,1)`、end `(1,0)`、`range_length_utf16 == 2`、`text == "Xb"`）；断言在测试侧，`diff.py:245-252` 只是构造 `ChangePatch`。
- `../../../tests/test_lsp_diff.py:37`：当前只导入 `ChangePatch, build_change_patches`；`:93-103` 有 `_patch_to_wire` 但仅服务 `build_change_patches` 路径。

## 二、具体修改

### 2.1 导入

将 `:37` 改为：

```python
from yate.editor_lsp.diff import (
    ChangePatch,
    build_change_patches,
    build_content_changes,
)
```

### 2.2 新增用例 1：`test_build_content_changes_emits_range_length_and_text`

- **前置/arrange**：无 fixture；`old = ["ab", "cd"]`，`new = ["aXbcd"]`。
- **act**：`changes = build_content_changes(old, new)`。
- **assert**：
  - 精确等于：
    ```python
    [{
        "range": {
            "start": {"line": 0, "character": 1},
            "end": {"line": 1, "character": 0},
        },
        "rangeLength": 2,
        "text": "Xb",
    }]
    ```
  - `apply_changes(old, changes) == new`（复用本文件 `:77-90` 的服务器模拟器，证明线格式级联可用）。
  - 这是 `rangeLength` 在 wire dict 层的唯一直接断言，钉死「deprecated 但照发」的既定决策。

### 2.3 新增用例 2：`test_build_content_changes_is_empty_for_equal_snapshots`

- **arrange**：两组相等快照 `["a", "b"]` 与 `["a", "b"]`、`[]` 与 `[]`。
- **act/assert**：`build_content_changes(...) == []`，对应 `sync.py:134-138` 的空补丁早退契约。

## 三、详细验证方案

| 验证目标 | 命令 | 通过标准 |
|---|---|---|
| 线格式字段与空补丁契约 | `.venv\Scripts\python.exe -m pytest tests/test_lsp_diff.py -q -k "build_content_changes" -n 1` | 退出码 0；2 条新用例全过 |
| 类型检查 | `.venv\Scripts\python.exe -m pyright tests/test_lsp_diff.py` | 0 errors / 0 warnings |

## 四、风险与回滚

- 精确 dict 断言对字段增减敏感：这是有意的契约钉死；若未来 LSP 线格式调整须同步本用例与主计划。
- `apply_changes` 是跨文件公共工具（本文件模块 docstring `:24-27` 已声明），本子计划只复用不改名。
- 回滚：`git revert` 本子计划提交；`yate/` 无 diff。

## 五、报告要求

交付时列出：改动清单、执行命令与退出码、未解决项；不得声称未执行的门禁。
