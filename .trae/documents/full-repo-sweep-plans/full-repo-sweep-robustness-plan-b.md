# B1：`move_entry` 的自我嵌套守卫（计划 b）

> **实施状态**：✅ 已实施 —— 2026-11-20（`ac4eda02`，负向用例先红后绿）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/services/workspace.py:519-545` 的 `copy_entry` 会拒绝把目录复制到自身子树中；`:547-559` 的 `move_entry` 只检查 `target.exists()`。剪切/粘贴在 `../../../yate/editor_components/file_manager/screen.py:1007` 处到达它。

## 独占文件

- `../../../yate/services/workspace.py`
- `../../../tests/test_workspace_file_manager.py`

## 设计

1. 在 `move_entry` 中，计算 `target = dest_dir / src.name` 之后，复用 `copy_entry` 的祖先测试：当 `src.is_dir()` 且 `target.resolve().relative_to(src.resolve())` 未抛出 `ValueError` 时，抛出 `OSError(f"cannot move {src.name} into itself")`。把该守卫放在 `target.exists()` 检查**之前**，这样即使目标路径尚不存在，递归目标也会被拒绝。
2. 保持现有的 `FileExistsError` 语义和 `shutil.move` 跨卷行为不变。
3. 更新 `move_entry` 的 docstring，说明新的 `OSError` 情形（按 `../../rules/misc-rules.md` §四，使用英文）。

## 测试（在 `../../../tests/test_workspace_file_manager.py` 中先写负向用例）

- `test_move_entry_rejects_moving_dir_into_own_subtree`：创建 `src/child`；调用 `workspace.move_entry(src, src / "child")`；断言 `pytest.raises(OSError, match="cannot move src into itself")`；断言 `src` 和 `src/child` 仍然存在（无部分变更）。
- `test_move_entry_rejects_self_nesting_across_mocked_volume`：同样的目录树，`monkeypatch.setattr(shutil, "move", fake_move)`，其中 `fake_move` 一旦被调用就抛出 `AssertionError`；断言抛出了 `OSError` 且 `fake_move` 从未被调用（在不使用真实卷的情况下覆盖跨卷递归分支）。
- `test_move_entry_same_dir_target_still_raises_file_exists_error`：保持 `:113` 处的现有行为（目标名已存在时抛出 `FileExistsError`）；断言一次普通的不相关移动仍返回预期的目标路径。

顺序：先添加这两个负向测试，运行该文件并观察到恰好这两个失败，然后实现守卫并重新运行（先红后绿的证据必须记录在波次提交信息正文中）。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_workspace_file_manager.py -q
.venv\Scripts\python.exe -m pyright yate/services/workspace.py tests/test_workspace_file_manager.py
```

## 风险 / 回滚

风险：对符号链接目标执行 `resolve()` 可能改变用户可见的错误信息；该守卫与 `copy_entry` 保持一致，因此行为仍然一致。回滚：从 `move_entry` 中移除祖先检查。
