# 子计划 prfix-ws — B1：`copy_entry` 目录自嵌套守卫

**Worktree 根**：`../yate-file-manager`（分支 `feat/file-manager`，下述相对路径均以此为根）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 B1（先读该节全文）。

## 独占文件

- `yate/services/workspace.py`
- `tests/test_workspace_filemgr.py`

## 修改点

### 1. `yate/services/workspace.py` — `copy_entry`（约 478-492 行）

现状无自嵌套守卫；`shutil.copytree` 没有 `_destinsrc`，dest 在 src 子树内时递归复制自己
直到 `RecursionError`（`RuntimeError` 子类，`action_paste` 的
`except (FileExistsError, OSError)` 捕获不到 → 应用退出 + 磁盘垃圾树）。

在 `FileExistsError` 存在性检查**之前**插入（评审原文修法）：

```python
target = dest_dir / src.name
if src.is_dir():
    try:
        target.resolve().relative_to(src.resolve())
    except ValueError:
        pass
    else:
        # OSError, not ValueError: the screen's paste handler catches
        # (FileExistsError, OSError) and reports on the input line.
        raise OSError(f"cannot copy {src.name} into itself")
if target.exists():
    raise FileExistsError(f"{target.name} already exists")
```

与现状代码融合（变量名/结构以现状为准，语义不变）。docstring 同步说明该守卫。

### 2. `tests/test_workspace_filemgr.py` — 两条 L0 回归用例

1. **复制目录进自身子树**：建 `A`（内含 `sub/`），`workspace.copy_entry(A, A / "sub")`
   断言抛 `OSError`、`A` 原始内容不变、`A/sub` 下**无残留新目录**（守卫缺失时该用例
   RecursionError，先红）。
2. **正常复制不受影响**（防过挡）：目录 → 无关目标目录照常复制成功；文件路径行为不变。

## 执行纪律

1. 先加用例跑一次（`-k` 单选自嵌套用例），确认红；**只跑一次**，避免 tmp 垃圾树堆积；
   **不要**清理 `%TEMP%` 积压（主代理处理）。随后修实现转绿，附红证据摘要于汇报。
2. 自测：`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（0 诊断）+
   `.venv\Scripts\python.exe -m pytest tests/test_workspace_filemgr.py tests/test_workspace_filter.py -q`
   （全绿；本机 `-q` 无汇总行，按退出码判定）。
3. 完成后**不提交**，汇报：改动文件、diff 要点、红证据、自测退出码。
