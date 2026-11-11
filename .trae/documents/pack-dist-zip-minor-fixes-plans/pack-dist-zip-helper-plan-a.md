# 子计划 a：归档助手 8 项实质修复（wave-1）

> 路径基准：本目录 `../../../tools/pack/zip_dist.py` 指仓库根同名文件；
> 代码块内命令相对基准是仓库根。唯一规范来源：本文件 +
> `../pack-dist-zip-minor-fixes-plan.md` §2/§3/§4 +
> `../pack-dist-zip-minor-fixes-issue.md` F1–F9。

## 1. 输入

- 现状取证：`tools/pack/zip_dist.py` 220 行（`_stage_files:57-75`、
  `_write_archive:94-128`、`_checksum_bytes:140-159`、`archive_stage:162-202`、
  `main:205-221`）；`tests/test_pack_zip.py` 232 行（17 个用例）。
- 目标：F1 非 ASCII stage 名、F3 symlink 条目、F4 0600 权限、F5 并发锁、
  F6 两次 replace 失败回滚、F7 dist-root 落 stage 内、F8 epoch 用例 mtime、
  F9 全角空格同名行，全部实质修复并有回归用例。

## 2. 独占文件清单

只改 `tools/pack/zip_dist.py`、`tests/test_pack_zip.py`。其它文件（含
`tests/test_pack_spec.py`、`pack/` 三脚本、文档）由别的子计划独占。

## 3. 具体修改

### 3.1 `_stage_files` → `list[tuple[Path, str, bool]]`

第三项为 `is_link`。逐个 `sorted(root.rglob("*"))`：
- `path.name in _TEMP_NAMES` → `continue`；
- `arcname = f"{stage_name}/{path.relative_to(root).as_posix()}"`；
- `path.is_symlink()` → `entries.append((path, arcname, True))`、`continue`
  （**不** `resolve()`、**不** `read_bytes()`）；
- 非普通文件 → `continue`；普通文件仍 `real = path.resolve()` +
  `if not real.is_relative_to(root): raise ZipDistError(...)`，追加
  `(path, arcname, False)`。
docstring 英文写明「symlink targets are recorded as link entries, never
followed」。

### 3.2 `_write_archive`

- `subdirs` 循环改 `for _, arcname, _ in entries`；
- 文件循环改 `for path, arcname, is_link in entries`；
- `is_link` 分支：`ZipInfo(arcname, date_time=time.localtime(path.lstat().st_mtime)[:6])`、
  `compress_type = zipfile.ZIP_DEFLATED`、`create_system = 3`、
  `external_attr = ((0o777 | stat.S_IFLNK) << 16)`、
  `zf.writestr(info, os.fsencode(os.readlink(path)))`；
- 普通文件分支保持现状（`external_attr`、`_unix_mode`、真实 mtime 不变）。

### 3.3 `_checksum_bytes`（F1 + F9）

```python
fields = line.decode("utf-8", errors="surrogateescape").split()
if len(fields) >= 2 and fields[-1].lstrip("*") == archive_name:
    continue
...
lines.append(f"{digest}  ".encode("ascii") + os.fsencode(archive_name))
```
`str.split()` 用 Unicode 空白，尾随全角空格不再破坏末列匹配；
`surrogateescape` 保证任意字节可逆；`os.fsencode` 让非 ASCII stage 名不再
抛 `UnicodeEncodeError`。docstring 同步更新（保留 LF 契约说明）。

### 3.4 `archive_stage`（F5 + F6 + F7 + F4）

1. `root = stage.resolve()` 之后、`dist_root.mkdir` 之前（F7）：
   ```python
   resolved_dist = dist_root.resolve()
   if resolved_dist == root or resolved_dist.is_relative_to(root):
       raise ZipDistError(f"dist root must not be inside the stage: {dist_root}")
   ```
2. `dist_root.mkdir(...)` 之后加锁（F5）：
   ```python
   lock_path = dist_root / f".{stage_name}.lock"
   try:
       lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
   except FileExistsError as exc:
       raise ZipDistError(
           f"another archive is in progress for {stage_name}: {lock_path}"
       ) from exc
   os.close(lock_fd)
   ```
   创建失败时**不得**删除他人锁（故锁创建放在 `try/finally` 之外）。
3. `try` 内（`_write_archive` / `_digest` / `sums_tmp.write_bytes` 之后）：
   `os.chmod(zip_tmp, 0o644)`、`os.chmod(sums_tmp, 0o644)`（F4）。
4. 事务化两次 replace（F6）：
   ```python
   backup: Path | None = None
   if archive.exists():
       fd3, raw3 = tempfile.mkstemp(prefix=f".{stage_name}.", suffix=".zip.bak", dir=dist_root)
       os.close(fd3)
       backup = Path(raw3)
       os.chmod(backup, 0o644)
       os.replace(archive, backup)
   os.replace(zip_tmp, archive)
   try:
       os.replace(sums_tmp, sums_path)
   except OSError:
       if backup is not None:
           os.replace(backup, archive)
           backup = None
       else:
           archive.unlink(missing_ok=True)
       raise
   ```
   备份操作必须紧邻两次 replace（前期失败时旧 zip 不动）。
5. `finally`：`zip_tmp.unlink(missing_ok=True)`；`sums_tmp` / `backup` 非空时
   `unlink(missing_ok=True)`；`lock_path.unlink(missing_ok=True)`。
6. docstring 改为「a failure before the swap leaves the previous archive
   untouched; a checksum-swap failure restores the previous archive; all
   temporary/lock files are cleaned up」。
7. **不改** `main()` 的 argparse、输出格式与异常捕获表；不改 CLI 退出码。

## 4. 测试用例（每条三要素，既有 17 个用例不删不改语义）

| 用例名 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_archive_stage_when_stage_name_has_non_ascii_chars_writes_matching_checksum_row` | `tmp_path` 下建 stage 名 `yate-0.2.18-发布` | `archive_stage` | 不抛异常；校验文件末行 `os.fsencode(stage.name)` 结尾；同名条目恰好 1 行且 hash == `result.digest` |
| `test_archive_stage_when_checksum_row_has_trailing_unicode_space_replaces_it` | 预置 `b"dead  <archive_name>\xe3\x80\x80\n"`（全角空格） | `archive_stage` | 同名行仅 1 行且 hash 为新 digest；其它行保留 |
| `test_archive_stage_when_stage_contains_symlink_records_link_entry` | 在 stage 内 `os.symlink`（不支持则 `pytest.skip`）+ stage 外目标文件 | `archive_stage` | zip 含该链接条目，`external_attr >> 16` 含 `stat.S_IFLNK`，条目 data == 链接文本，目标文件内容不在包内 |
| `test_archive_stage_when_symlink_points_outside_stage_does_not_read_target` | 链接指向 stage 外文件 | 同上 | 外部目标不读取、不进包；`ZipFile.testzip() is None` |
| `test_archive_stage_when_archive_finishes_sets_readable_permissions` | stage fixture | 同上 | POSIX：`stat.S_IMODE(result.path.stat().st_mode) == 0o644`；Windows：产物可写且 `stat.S_IWRITE` 位存在；校验文件同样断言 |
| `test_archive_stage_when_lock_file_exists_raises_and_keeps_lock` | 预置 `dist/.<stage>.lock` | `archive_stage` | `pytest.raises(ZipDistError, match="in progress")`；锁文件仍存在；无 zip / tmp / bak 产生 |
| `test_archive_stage_when_checksum_replace_fails_restores_previous_zip` | 预置旧 zip（字节 `b"old"`）+ 旧校验行；monkeypatch `zip_dist.os.replace` 令 `dst == sums_path` 抛 `OSError("mock failure")` | `archive_stage` | 抛 `OSError`；旧 zip 字节仍 `b"old"`；校验文件不变；无残留 tmp / bak / lock |
| `test_archive_stage_when_dist_root_is_inside_stage_raises_zip_dist_error`（参数化 `stage` 与 `stage/nested`） | 正常 stage | `archive_stage(stage, inside)` | `pytest.raises(ZipDistError, match="inside the stage")`；不创建 nested 目录、不产 zip / lock |
| `test_archive_stage_when_directory_entries_are_written_uses_fixed_epoch`（既有，改） | `os.utime(stage / "yate.exe", (1700000000, 1700000000))` | 归档 | 目录条目仍 `(1980,1,1,0,0,0)`；`file_info.date_time == time.localtime(1700000000)[:6]`（F8）；`create_system == 3` |

`monkeypatch` 注入失败、不依赖真实不可写目录；临时目录全部用 `tmp_path`。

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
```
四条退出码 0、pyright 零诊断；预计 `test_pack_zip.py` 用例数 17→25。
局部覆盖率运行须加 `--cov-fail-under=0`。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| symlink 条目影响 Windows `Expand-Archive` | 正常 Windows 产物无链接；E2E 验收 3 不经过链接 | 还原跳过（F3 不闭环） |
| 锁残留致后续归档永久失败 | 错误信息带锁路径，finally 清理本次锁；文档写明手工清理 | 删除锁文件 |
| 备份/回滚引入新失败面 | monkeypatch 用例断言旧 zip 字节恢复、无残留 | `git revert` F6 段 |
| `surrogateescape` 与 `os.fsencode` 跨平台编码差异 | 单测覆盖非 ASCII 名 + 全角空格；字节可逆 | 还原 ascii（F1/F9 不闭环） |
| `entries` 三元组类型改动漏改调用点 | `_write_archive` 与 `subdirs` 解包同步改；pyright strict 兜底 | 按诊断修正 |

回滚：`git revert` 本波提交；wave-2 / wave-3 排在 wave-1 之后串行，避免
依赖半实现状态。
