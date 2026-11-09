# 子计划 a：共享 zip 归档助手 + 运行时单测（wave-1）

> 路径以本文件所在目录 `.trae/documents/pack-dist-zip-plans/` 为基准：
> `../../../tools/pack/zip_dist.py` 即仓库根 `tools/pack/zip_dist.py`；
> 代码块内命令的相对基准是仓库根。唯一规范来源：本文件 +
> `../pack-dist-zip-plan.md` §4 数据契约 + `.trae/rules/` 8 份规则。

## 1. 输入

- 主计划 §3 选型 A（共享 stdlib `zipfile` 助手，否决 `Compress-Archive` 分叉）。
- 主计划 §4 数据契约：CLI 参数、两行 stdout、退出码、zip 顶层目录、Unix mode、
  校验文件 upsert、临时文件原子替换、临时文件名排除。
- 现状取证：`../../../tools/pack/__init__.py:1-14`（惰性包根）、
  `../../../tools/pack/cli.py:41-47`（子命令表冻结，不改）、
  `../../../pyproject.toml:115-125`（pyright strict `include` 含 tools/tests）、
  `../../../tests/test_architecture.py:610,899,1417,1496`（守卫面）。

## 2. 独占文件清单（只改这三个，其它任何文件不得触碰）

| 文件 | 动作 |
| --- | --- |
| `../../../tools/pack/zip_dist.py` | 新建 |
| `../../../tools/pack/__init__.py` | 只改模块 docstring 一句（不改 `__all__` / `__version__`） |
| `../../../tests/test_pack_zip.py` | 新建 |

## 3. 具体修改（定位到文件 / 符号）

### 3.1 `tools/pack/__init__.py`

模块 docstring（第 3-4 行「everything that has to be generated *before* a
build lives here」）后补一句英文：`Post-build helpers (the --dist zip archive)
live here too, so both platform build scripts call one implementation.`；
不改 `__all__`（保持 `["__version__"]`），不新增 re-export（架构 §三.5 包根惰性）。

### 3.2 `tools/pack/zip_dist.py`（新文件，目标 < 250 行）

模块 docstring 英文，说明职责与调用方；首行可执行语句
`from __future__ import annotations`；imports 分组：stdlib
（`argparse`, `hashlib`, `os`, `stat`, `sys`, `tempfile`, `time`, `zipfile`,
`collections.abc.Sequence`, `pathlib.Path`, `typing.NamedTuple`），无第三方 /
无项目内 import、无相对导入、无 `Any` / `TYPE_CHECKING` / `# type: ignore`。
注释与 docstring 全英文（misc-rules §四）。

公共与私有符号（签名固定，便于 wave-2/3 引用）：

```python
#: Files the smoke test creates; they must never appear in the archive.
_TEMP_NAMES: frozenset[str] = frozenset({"smoke-out.txt"})

#: Executables that still need 0o755 on a Windows-produced archive.
_EXECUTABLE_NAMES: frozenset[str] = frozenset({"yate", "yate.exe"})

class ZipDistError(Exception): ...

class ArchiveResult(NamedTuple):
    path: Path
    size: int
    digest: str
    checksum_path: Path

def _stage_files(stage: Path) -> list[tuple[Path, str]]: ...
def _file_mode(path: Path) -> int: ...
def _unix_mode(path: Path, *, posix: bool) -> int: ...
def _write_archive(target: Path, entries: list[tuple[Path, str]], *, posix: bool) -> None: ...
def _digest(path: Path) -> str: ...
def _checksum_text(sums_path: Path, archive_name: str, digest: str) -> str: ...
def archive_stage(stage: Path, dist_root: Path, *, posix: bool | None = None) -> ArchiveResult: ...
def main(argv: Sequence[str] | None = None) -> int: ...

if __name__ == "__main__":
    raise SystemExit(main())
```

逐符号行为：

- `_stage_files(stage)`：`sorted(stage.rglob("*"))`，只取 `path.is_file()`，
  跳过 `path.name in _TEMP_NAMES`；arcname =
  `f"{stage.name}/{path.relative_to(stage).as_posix()}"`；返回
  `(path, arcname)` 列表。排序只为确定性输出（O(n log n)，遍历本身 O(n)，
  无更低复杂度的标准替代）；空列表由 `archive_stage` 判错。
- `_file_mode(path)`：`stat.S_IMODE(path.stat().st_mode)`（单函数便于测试注入
  POSIX mode，Windows 上不依赖真实权限位）。
- `_unix_mode(path, *, posix)`：`posix=True` 时返回 `_file_mode(path)`（保留
  `../../../pack/pack.sh:189` 的 `chmod 0755`）；否则
  `0o755 if path.name in _EXECUTABLE_NAMES else 0o644`。
- `_write_archive(target, entries, *, posix)`：`zipfile.ZipFile(target, "w",
  compression=zipfile.ZIP_DEFLATED)`；先写顶层目录条目 `f"{stage.name}/"`
  （`create_system=3`、`external_attr=((stat.S_IFDIR | 0o755) << 16)`），
  再对每个文件用 `zipfile.ZipInfo(arcname, date_time=
  time.localtime(path.stat().st_mtime)[:6])` 显式设 `compress_type`、
  `create_system = 3`、
  `external_attr = ((_unix_mode(path, posix=posix) | stat.S_IFREG) << 16)`，
  `zf.writestr(info, path.read_bytes())`；子目录条目同理以 `S_IFDIR` 写出
  （arcname 以 `/` 结尾）。显式 `external_attr` 是 issue §三硬要求。
- `_digest(path)`：`hashlib.sha256()` 流式 1 MiB 分块读，返回 `hexdigest()`。
- `_checksum_text(sums_path, archive_name, digest)`：文件存在则读
  `splitlines()`，只剔除「`parts = line.split()` 且 `len(parts) >= 2` 且
  `parts[-1].lstrip("*") == archive_name`」的行（兼容 sha256sum 的
  `*name` 二进制标记），其余行原样保留；末尾追加
  `f"{digest}  {archive_name}\n"`，返回全文。
- `archive_stage(stage, dist_root, *, posix=None)`：
  1. `posix = os.name == "posix" if posix is None else posix`；
  2. `stage.is_dir()` 假 → `raise ZipDistError(f"stage directory not found: {stage}")`；
  3. `dist_root.mkdir(parents=True, exist_ok=True)`；
  4. `archive = dist_root / f"{stage.name}.zip"`；
     `sums_path = dist_root / "SHA256SUMS.txt"`；
  5. `entries = _stage_files(stage)`，空 → `raise ZipDistError("stage has no files to archive")`；
  6. `fd, raw = tempfile.mkstemp(prefix=f".{stage.name}.", suffix=".zip.tmp", dir=dist_root)`
     → `os.close(fd)` → `zip_tmp = Path(raw)`；`sums_tmp: Path | None = None`；
  7. `try`：`_write_archive(zip_tmp, entries, posix=posix)`；
     `digest = _digest(zip_tmp)`；`size = zip_tmp.stat().st_size`；
     `fd2, raw2 = tempfile.mkstemp(prefix=".SHA256SUMS.", suffix=".tmp", dir=dist_root)`，
     `os.close(fd2)`，`sums_tmp = Path(raw2)`，
     用 `open(..., "w", encoding="ascii", newline="\n")` 写
     `_checksum_text(sums_path, archive.name, digest)`；
     `os.replace(zip_tmp, archive)`；`os.replace(sums_tmp, sums_path)`；
  8. `finally`：`zip_tmp.unlink(missing_ok=True)`；
     `sums_tmp` 非空则 `unlink(missing_ok=True)`；
  9. 返回 `ArchiveResult(archive, size, digest, sums_path)`。
  顺序固定「先 zip 后校验」：校验替换失败时已落盘的是完整 zip，重跑幂等补齐
  （主计划 §7 登记的已知边界）。
- `main(argv)`：`argparse.ArgumentParser(prog="python -m tools.pack.zip_dist", ...)`，
  必填 `--stage`（`type=Path`）、`--dist-root`（`type=Path`）；
  `try` 调 `archive_stage`，`except (ZipDistError, OSError, ValueError, zipfile.BadZipFile) as exc`
  → `print(f"error: zip archive failed: {exc}", file=sys.stderr)`、`return 1`；
  成功 `print(f"ZIP -> {result.path}  ({result.size / (1024 * 1024):.1f} MB)")`、
  `print(f"  SHA256 {result.path.name}: {result.digest}")`、`return 0`。
  `print()` 只在 CLI 边界（架构守卫 `test_no_debug_prints_in_library_modules`
  只扫 `yate/`；`tools/pack/cli.py:174,192` 同形态）。

### 3.3 `tests/test_pack_zip.py`（新文件）

静态导入 `from tools.pack import zip_dist`（`../../../tools/pack/__init__.py`
为惰性包根，pyright strict 可解析，无需 `spec_from_file_location`）。
fixture：

```python
@pytest.fixture
def stage(tmp_path: Path) -> Path:
    dist_root = tmp_path / "release"
    stage = dist_root / "yate-0.2.18-windows-x64"
    stage.mkdir(parents=True)
    (stage / "yate.exe").write_bytes(b"exe")
    (stage / "runtime").mkdir()
    (stage / "runtime" / "base.dll").write_bytes(b"dll")
    (stage / "SHA256SUMS.txt").write_text("abc  yate.exe\n", encoding="ascii")
    (stage / "smoke-out.txt").write_text("0.2.18\n", encoding="ascii")
    return stage
```

`dist_root` 由 `stage.parent` 取得；所有测试用 `tmp_path`，不写仓库内目录。

## 4. 详细测试用例（每条含 arrange / act / assert）

| 用例名 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_archive_stage_when_stage_has_files_writes_top_level_dir_and_excludes_smoke_output` | stage fixture | `zip_dist.archive_stage(stage, stage.parent)` | `namelist()` 含 `<stage>/`、`<stage>/yate.exe`、`<stage>/runtime/`、`<stage>/runtime/base.dll`、`<stage>/SHA256SUMS.txt`；任何名字不含 `smoke-out.txt`；返回 `result.path == <dist>/<stage>.zip`、`result.size == path.stat().st_size`、`result.digest == hashlib.sha256(path.read_bytes()).hexdigest()`；`result.checksum_path == <dist>/SHA256SUMS.txt` |
| `test_archive_stage_when_sums_file_has_other_platform_rows_preserves_them` | 预置 dist 根 `SHA256SUMS.txt` 两行 `<h1>  yate-0.2.18-linux-x64.zip` 与 `<h2>  yate-0.2.17-windows-x64.zip` | 同上 | 两行原样保留；新增且仅新增一行 `f"{result.digest}  {archive.name}"`；行数 = 3 |
| `test_archive_stage_when_rerun_replaces_zip_and_keeps_single_row` | 第一次归档后往 stage 追加 `runtime/extra.dll` | 第二次 `archive_stage` | dist 根仍只有一个同名 zip；其 `namelist()` 含 `extra.dll`；校验文件中末列 == archive.name 的行恰好 1 行且 hash 与第二次 digest 一致；stage 内 `SHA256SUMS.txt` 内容仍为 `abc  yate.exe\n` |
| `test_archive_stage_when_posix_mode_flag_set_marks_executable_bit` | stage fixture 中的 `yate.exe`；`monkeypatch.setattr(zip_dist, "_file_mode", lambda path: 0o755)` | `archive_stage(stage, stage.parent, posix=True)` | `<stage>/yate.exe` 的 `create_system == 3`，`(external_attr >> 16) & 0o777 == 0o755`；顶层目录条目带 `S_IFDIR` |
| `test_archive_stage_when_nt_mode_flag_set_marks_only_executables` | stage fixture | `archive_stage(stage, stage.parent, posix=False)` | `yate.exe` 位为 `0o755`；`SHA256SUMS.txt` 与 `runtime/base.dll` 位为 `0o644` |
| `test_archive_stage_when_write_fails_cleans_temp_files_and_keeps_old_zip` | 预置 `<dist>/<stage>.zip` 内容 `b"old"` 与旧校验行；`monkeypatch.setattr(zipfile.ZipFile, "writestr", ...)` 抛 `OSError("disk full")` | `with pytest.raises(OSError, match="disk full"): archive_stage(...)` | 旧 zip 字节仍为 `b"old"`；校验文件内容不变；`list(dist.glob("*.tmp")) == []`；无半截新 zip |
| `test_archive_stage_when_stage_missing_raises_zip_dist_error` | 不存在的 stage 路径 | `archive_stage(...)` | `pytest.raises(zip_dist.ZipDistError, match="stage directory not found")`；dist 根无 zip / tmp |
| `test_archive_stage_when_stage_empty_raises_zip_dist_error` | 空目录 stage | 同上 | `pytest.raises(zip_dist.ZipDistError, match="no files")` |
| `test_archive_stage_when_archived_zip_integrity_is_verified` | stage fixture | 归档 + `zipfile.ZipFile(path).testzip()` | 返回 `None`；`python -m zipfile -t` 等价性另由 wave-4 对真实产物跑一次 |
| `test_main_when_invoked_with_stage_prints_path_and_digest_and_returns_zero` | stage fixture + `capsys` | `zip_dist.main(["--stage", str(stage), "--dist-root", str(stage.parent)])` | 返回 0；stdout 含 `ZIP ->`、`<stage>.zip`、`MB`、`SHA256 <stage>.zip:`、与校验文件一致的 digest；`capsys.readouterr().err == ""` |
| `test_main_when_archive_fails_prints_readable_error_and_returns_one` | `monkeypatch.setattr(zip_dist, "archive_stage", ...)` 抛 `ZipDistError("boom")` | `zip_dist.main([...])` | 返回 1；stderr 含 `error: zip archive failed: boom`；stdout 为空 |
| `test_main_when_arguments_missing_exits_two` | 无 | `zip_dist.main([])` | `pytest.raises(SystemExit)` 且 `code == 2`（argparse） |

反/正路径覆盖：成功（1/2/3/9/10）、边界（4/5）、异常（6/7/8/11/12）。
`test_archive_stage_when_no_zip_switch_requested_*` 不在本文件：`--no-zip`
是脚本层开关，由 wave-3 静态守卫覆盖，避免越层造桩。

## 5. 可执行验收命令（Windows PowerShell，`.venv\Scripts\python.exe`）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py -q
.venv\Scripts\python.exe -m pyright tools/pack/zip_dist.py tests/test_pack_zip.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
```

判定：四条退出码全 0；pyright 零诊断；架构 37 用例全绿；既有
`test_pack_spec.py` 守卫不回归。局部覆盖率运行须加 `--cov-fail-under=0`
（本波不要求覆盖率）。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `tools/pack/` 包根惰性被破坏，导致 `-m` 连带加载 wiki | 只在 docstring 补一句，不动 `__all__` / import；验收命令实测 `python -m tools.pack.zip_dist --help` 退出 0 且无重模块导入错误 | 删除该句 |
| Windows 上 `stat.S_IMODE` 不含执行位，Linux 包解压后不可执行 | `_unix_mode` 双分支 + 测试用 `monkeypatch` 注入 POSIX mode 断言 `0o755` | 修 `_unix_mode`，不删测试 |
| `mkstemp` 的 fd 泄漏 / 临时文件残留 | 立即 `os.close(fd)`；`finally` 无条件 `unlink(missing_ok=True)`；单测断言 `*.tmp` 为空 | 补 finally |
| `ZipInfo` 时间戳 / 时区造成两平台 zip 不同 | 只用 `time.localtime(st_mtime)[:6]`，不追求字节一致；跨平台一致指命名 / 结构 / mode / 退出码 / 输出语义 | 改固定时间戳（会牺牲 mtime 保真） |
| 校验文件 CRLF 混入 | `open(newline="\n")` 显式 LF；读用 `splitlines()` | 固定 newline |
| pyright strict 诊断 | 全量注解（含 `sums_tmp: Path | None`）、无 `Any`；`ZipInfo` / `NamedTuple` 均为有 stub 的 stdlib 类型 | 按诊断补注解，不用 `# type: ignore` |

回滚路径：`git revert` 本波提交即移除助手与单测；wave-2 三脚本的调用行须一并
回退（故 wave-2 排在 wave-1 之后串行）。
