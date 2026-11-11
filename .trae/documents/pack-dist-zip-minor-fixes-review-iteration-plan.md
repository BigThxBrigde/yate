# M1 迭代修复方案（review-iteration，2026-11-11）

> 来源记录：[`../reviews/2026-11-11-fix-all-minor-review.md`](../reviews/2026-11-11-fix-all-minor-review.md)
> （blocker 0 / **major 1 (M1)** / minor 6）。唯一规范来源：本文件 +
> 来源记录 + `.trae/rules/` 8 份必读规则 +
> `pack-dist-zip-minor-fixes-plan.md`（本轮主计划）。
> 无人值守下【批准】按通过处理，不冒充用户确认；登记见
> `pack-dist-zip-progress.md`。路径基准：本文件在 `.trae/documents/`，
> 代码块内命令相对基准为仓库根。

## 1. 目标与非目标

**目标**：把 M1（F5 引入的锁残留回归）修至归零，同批补评审建议的 m2 / m4
两处一行守卫；第二轮评审达到 0 blocker / 0 major；主代理收尾全量门禁全绿。

**裁定为登记待办（不阻塞）**：m1（回滚二次失败掩盖原始异常，需双重
`OSError`）、m3（symlink 用例为 monkeypatch，Windows 权限限制）、m5（跨
stage 并发共享校验文件丢更新，脚本人工串行）、m6（陈旧锁无 PID/TTL 自愈，
设计层缺口）。四条 minor 按 §二.6 登记，不扩大本轮改动面。

## 2. M1 根因与备选方案

现状 `tools/pack/zip_dist.py:207-225`：锁以 `O_CREAT|O_EXCL` 创建并
`os.close` 后，`archive` / `sums_path` 赋值、`_stage_files()`、空 stage
判错、`tempfile.mkstemp()` 都在 **try 之前**；`finally` 的
`lock_path.unlink(missing_ok=True)`（:259）因此不覆盖三条失败路径，
残留 `.<stage>.lock` 使后续重试永久报 in-progress。

| 方案 | 内容 | 裁决 |
| --- | --- | --- |
| A（选中） | 锁创建成功后立即进入大 `try`：`zip_tmp` / `sums_tmp` / `backup` 全部初始化为 `Path \| None`，`_stage_files` / 空 stage 判错 / 两个 `mkstemp` / 归档 / swap 全部移入 try；`finally` 对三个可选临时文件判空 `unlink(missing_ok=True)` 后无条件删锁 | 选中：一处 `try` 覆盖所有失败路径，`lock_created` 无需额外标志；锁创建失败仍在小 `try/except FileExistsError` 中不删他人锁 |
| B | 把 stage 校验与 `_stage_files` 整体移到加锁之前 | **否决**：`_stage_files` 是重活（遍历 stage），提前到锁外会让两个并发进程同时扫描并在锁外产生其它临时状态；且 `mkstemp` 仍在锁外，M1 未全闭环 |
| C | 用 `lock_created: bool` 标志 + 把大 `try` 起点提到锁创建前 | **否决**：可行但多一个易错状态位；`except FileExistsError` 会覆盖整个大 try，其它位置抛同名异常会被误转成 in-progress 文案 |

## 3. 分步实施（独占文件清单）

| 步骤 | 文件 | 改动 |
| --- | --- | --- |
| R1 | `tools/pack/zip_dist.py` | `archive_stage` 的 `try` 起点前移；三个临时 Path 改可选并在 finally 判空清理；删锁保持无条件；docstring 不变（修后与「all temporary/lock files are cleaned up」一致） |
| R1 | `tests/test_pack_zip.py` | 补 3 条「失败后无锁残留」用例；既有空 stage 用例补 `*.lock` 断言 |
| R1 | `tests/test_pack_spec.py` | m2：`test_bat_wrapper_when_mapping_scanned_keeps_existing_mappings` 加 `bat.index("if errorlevel 1") < bat.index("exit /b %ERRORLEVEL%")` |
| R1 | `tests/test_app_panes.py` | m4：`test_notify_focus_when_leaf_was_closed_returns_silently` 在遍历 `stale_ids` 前加 `assert stale_ids` |
| R2 | 主代理 | 评审记录追加第二轮章节、方案/进度/总纲回填、提交、记忆更新 |

### 3.1 `archive_stage` 结构（修后）

```python
    lock_path = dist_root / f".{stage_name}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ZipDistError(
            f"another archive is in progress for {stage_name}: {lock_path}"
        ) from exc
    os.close(lock_fd)
    archive = dist_root / f"{stage_name}.zip"
    sums_path = dist_root / "SHA256SUMS.txt"
    zip_tmp: Path | None = None
    sums_tmp: Path | None = None
    backup: Path | None = None
    try:
        entries = _stage_files(root, stage_name)
        if not entries:
            raise ZipDistError("stage has no files to archive")
        fd, raw = tempfile.mkstemp(prefix=f".{stage_name}.", suffix=".zip.tmp", dir=dist_root)
        os.close(fd)
        zip_tmp = Path(raw)
        ...  # _write_archive / _digest / sums_tmp / chmod / copyfile / swap（原样）
    finally:
        if zip_tmp is not None:
            zip_tmp.unlink(missing_ok=True)
        if sums_tmp is not None:
            sums_tmp.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
    return ArchiveResult(archive, size, digest, sums_path)
```
不变：`main()` 参数表与异常捕获表、CLI 输出、退出码、`_stage_files` /
`_write_archive` / `_checksum_bytes`、F1–F16 其它修复逻辑。

### 3.2 新增用例（三要素）

| 用例名 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_archive_stage_when_stage_is_empty_releases_lock` | 空 stage 目录 + `tmp_path` dist | `archive_stage` | `pytest.raises(ZipDistError, match="no files")`；`list(dist.glob(".*.lock")) == []`；可立即重试（补一个文件后 `archive_stage` 成功） |
| `test_archive_stage_when_stage_files_reject_entry_releases_lock` | 正常 stage + monkeypatch `zip_dist._stage_files` 抛 `ZipDistError("stage entry escapes stage root")` | 同上 | 抛该错；无 `.*.lock` / `*.tmp` / `*.bak` 残留 |
| `test_archive_stage_when_mkstemp_fails_releases_lock` | 正常 stage + monkeypatch `zip_dist.tempfile.mkstemp` 第一次抛 `OSError("disk full")` | 同上 | 抛 `OSError`；无 `.*.lock` / `*.tmp` / `*.bak` 残留 |
| 既有 `test_archive_stage_when_stage_empty_raises_zip_dist_error` | — | — | 补 `assert list(dist.glob(".*.lock")) == []` |

## 4. 验收命令（逐条记录退出码）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py tests/test_pack_spec.py tests/test_app_panes.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1
git diff --check master...HEAD
```
全部退出码 0；再加「三条失败路径各自无锁残留」由新增用例断言。全量七项门禁
由主代理收尾统一跑。第二轮 `code-review-expert` 复核 M1 / m2 / m4 与门禁，
直至 0 blocker / 0 major。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 三个可选 Path 判空漏一项致临时文件残留 | 新增用例断言 `*.tmp` / `*.bak` / `.*.lock` 全空 | `git revert` R1 |
| `mkstemp` monkeypatch 影响 `os.close` 之后的 fd | 桩只抛第一次调用，且断言无残留 fd 相关产物 | 调整桩 |
| m4 的 `assert stale_ids` 若构造场景偶发为空导致用例红 | 先读守卫用例实际取 id 逻辑，断言放在遍历前；四次 `-n 1` 复核 | 修用例构造，不删断言 |
| m2 顺序断言因 bat 文本变化抛 `ValueError` | 先读 bat 真实文本，两个标记均存在 | 调整标记，不删断言 |

回滚总路径：R1 四个文件单独提交，`git revert` 即回到评审时状态；
F1–F16 其它修复与合并模拟结论不受影响。

## 6. 第二轮迭代（N1 / m1 / N2 / N3）

来源：评审记录 §七（blocker 0 / major 1 N1 / minor 2）。按 §二.6 再次迭代。

| 项 | 裁定 | 处置 |
| --- | --- | --- |
| N1（major） | 实质修复 | `finally` 内三个临时文件 `unlink` 每项各包 `try/except OSError` 并加英文注释「清理失败不得掩盖原始异常或跳过删锁」；`lock_path.unlink` 独立包裹，确保任一 unlink 失败后锁仍释放 |
| m1（第一轮 minor） | 同批闭环 | swap 的 `except OSError` 内回滚动作再包 `try/except OSError`，回滚失败时 `pass` 后 `raise` 保留原始 swap 异常，不被回滚异常替换 |
| N2（minor） | 同批闭环 | `fail_once` 改名为 `fail_mkstemp`（无条件抛错） |
| N3（minor） | 同批闭环 | 既有 `test_archive_stage_when_stage_empty_raises_zip_dist_error` 恢复为只断言抛错；新增 `test_archive_stage_when_stage_is_empty_releases_lock` 专职覆盖锁释放与重试成功 |
| m3 / m5 / m6 | 登记待办 | 真实 symlink（Windows 权限）、跨 stage 并发校验文件、陈旧锁 PID/TTL 自愈，均为设计层/平台限制，按 §二.6 登记不阻塞 |

新增 2 条用例：`test_archive_stage_when_zip_tmp_unlink_fails_still_releases_lock`
与 `test_archive_stage_when_backup_unlink_fails_still_releases_lock`，
用 monkeypatch 定向让 `.tmp` / `.bak` 的 `Path.unlink` 抛 `PermissionError`，
断言 `list(dist.glob(".*.lock")) == []`（`Path.unlink` 桩按后缀定向，
不影响 `.lock` 的删除）。验收命令沿用 §4 五条，另加这两条用例单独跑。
第三轮 `code-review-expert` 限定复核 N1/m1/N2/N3 与门禁，直至
0 blocker / 0 major。

## 7. 回填与提交纪律

评审记录追加「第二轮迭代复核」章节（只追加、不覆盖既有事实）；
`overview.md` §六 登记 M1 迭代；`progress.md` 登记修复与复评结论；
主代理收尾跑全量门禁、更新记忆（用户显式要求「更新记忆」）、逐步提交，
只提交不推送、不自动合流。

## 8. 迭代结果（回填）

三轮评审收敛至 0 blocker / 0 major / 3 minor：M1（大 `try` 覆盖所有失败
路径）、N1（`finally` 每项 `unlink` 异常隔离 + 锁清理独立）两轮 major
修复，m1（回滚失败保留原异常）、m2/m4/N2/N3 同批闭环；新增 5 条回归
用例（3 条锁残留 + 2 条 unlink 失败仍释放锁）均经修复前版本反证非空跑。
主代理收尾八项门禁前七项全 0、第 8 项经单独重跑 0（safe-delete 钩子）；
覆盖率 92.93%、冒烟 121/121·1464。m3/m5/m6/N4/N5/N6 登记待办；
索引 #75 已登记，工作树干净、未推送、未合流。
