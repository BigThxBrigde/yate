# plan-a：L0 Workspace 元数据与文件操作扩展（wave-1）

## 输入
总纲 `overview.md` §三（Entry 元数据/Q4/Q2 裁决）+ §四架构落点。
事实基线：`yate/services/workspace.py` 500 行；`Entry`（52-63）仅 path/name/is_dir；
`list_dir`（225-252）目录优先排序 key=`(not is_dir, name.lower())`；
`create_entry`（395-409）/`rename_entry`（411-418，同目录）/`remove_entry`（420-427）；
`IGNORED_NAMES`（12-25）；`show_hidden`（83）。

## 目标
为 file manager 提供 L0 支撑：条目元数据（size/mtime/权限）、人性化 size、
Windows 盘符虚拟层、跨目录复制/移动。全部纯 stdlib、零 UI 依赖（R4）。

## 独占文件清单
- `yate/services/workspace.py`（追加，不改既有函数行为）
- `tests/test_workspace_filemgr.py`（新建）

## 具体修改

### 1. `EntryStat` 数据类（追加在 `Entry` 之后，~workspace.py:63）
```python
@dataclass(frozen=True)
class EntryStat:
    path: Path
    size: int          # bytes; 目录 = 0
    mtime_ns: int      # st_mtime_ns；stat 失败 = 0
    mode: int          # st_mode
    nlink: int         # st_nlink
    owner: str | None  # pwd 展开名；Windows/未知 = None
    group: str | None  # grp 展开名；Windows/未知 = None
```
`owner`/`group`：模块内条件导入（try: import pwd, grp except ImportError: None），
POSIX 上 `pwd.getpwuid(st_uid).pw_name` / `grp.getgrgid(st_gid).gr_name`，
KeyError → None。**不得**在 Windows 路径上触发 pwd/grp import 失败（try 包裹）。

### 2. `Workspace.stat_entry(self, path: Path) -> EntryStat`（~workspace.py:460 附近）
一次 `path.stat()`（`OSError` → 全零降级 EntryStat，size=0/mtime=0/mode=0/nlink=0，
不抛出——浏览大目录时不因竞态删除崩溃）。目录 size 取 0（lf 惯例）。

### 3. `human_size(n: int) -> str` 模块级函数
`0 → "0"`；`< 1024 → f"{n}"`；否则 1024 进制一位小数 `15K / 2.6M / 183M / 1.2G /
3.4T`（单位 K/M/G/T，去尾零：`1.0K → 1K`；负数/超大按同式）。

### 4. `Workspace.list_drives(self) -> list[Entry]`
`sys.platform == "win32"` 时对 `string.ascii_uppercase` 逐字母
`Path(f"{c}:\\").exists()` 探测，命中 → `Entry(path, f"{c}:", True)`，按字母序；
非 win32 返回 `[]`。纯函数级成本，不缓存。

### 5. `Workspace.copy_entry(self, src: Path, dest_dir: Path) -> Path`
目标 = `dest_dir / src.name`；已存在 → `FileExistsError`（调用方走确认流）。
目录 → `shutil.copytree(src, target)`；文件 → `shutil.copy2`。
复用 `validate_name` 语义不做（名字来自既有条目）。

### 6. `Workspace.move_entry(self, src: Path, dest_dir: Path) -> Path`
`shutil.move(str(src), str(dest_dir / src.name))`；目标已存在 → `FileExistsError`
（先查后动，避免 shutil.move 静默覆盖目录）。**跨卷移动**：`shutil.move` 自带
copy+delete，允许（issue 非目标仅限制 y/x 语义不做特判，shutil.move 天然支持）。
上述修改全部追加在文件尾部区段，`stat_entry` 放 `path_matches` 之前；
新代码 docstring 英文、`from __future__ import annotations` 已存在不动。

## 新增测试（tests/test_workspace_filemgr.py）
前置：tmp_path 构造目录树（dir_a/file.txt、dir_b、大小 2048 的文件、隐藏文件）。

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_stat_entry_returns_size_mtime_and_posix_fields` | 对 2048 字节文件调 `stat_entry` | `size == 2048`；`mtime_ns > 0`；`owner/group` 在 win32 为 None（POSIX 断言 str 或跳过） |
| `test_stat_entry_dir_reports_zero_size` | 对目录调 | `size == 0`、`is nlink >= 2` |
| `test_stat_entry_missing_path_degrades_to_zeroes` | 对不存在路径调 | 不抛异常，`size == 0 and mtime_ns == 0` |
| `test_human_size_formats_binary_units` | 参数化 0/1023/1024/1536/2621440/188743680/1.2*1024**3 | `"0" / "1023" / "1K" / "1.5K" / "2.5M" / "180M" / "1.2G"` |
| `test_list_drives_empty_on_posix_and_sorted_on_windows` | 调 `list_drives` | win32：结果字母序且每项 `is_dir is True`；POSIX：`== []`（monkeypatch `sys.platform` 双跑） |
| `test_copy_entry_copies_file_and_dir_recursively` | copy2 后内容一致；copytree 后子树一致 | 目标存在、源保留、`FileExistsError` on 重复 |
| `test_move_entry_renames_into_dir_and_rejects_existing` | move 后源消失；再建同名 move | `FileExistsError` 且源仍在 |
| `test_copy_move_reject_escape_via_existing_target` | dest_dir 下预置同名 | 抛 `FileExistsError`（防覆盖） |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/services/workspace.py tests/test_workspace_filemgr.py
.venv\Scripts\python.exe -m pytest tests/test_workspace_filemgr.py tests/test_workspace_filter.py -q
```
（局部覆盖率口径如需 `--cov` 则加 `--cov-fail-under=0`。）

## 风险与回滚
- pwd/grp 条件导入在 pyright strict 下需显式类型（`owner: str | None`），import 放
  try 块且变量注解——如 pyright 报 stub 缺失，改用 `importlib.util.find_spec` 守卫。
- 回滚：单笔提交 revert 即可；纯追加，无既有行为改动。
