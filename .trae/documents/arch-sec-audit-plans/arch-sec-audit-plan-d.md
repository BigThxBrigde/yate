# arch-sec-audit plan-d：`~/.yate` 路径收敛到 `yate.paths.yate_home()`（A2）+ 数据目录 0700（S5）

## 输入与依据

- 取证 1（A2）：`Path.home() / ".yate" / ...` 手工拼接散布 9 处：
  `yate/cli.py:414`（themes）、`yate/diagnostics.py:230,363`、`yate/yaterc.py:84`、
  `yate/services/trust.py:35`、`yate/services/extensions/loader.py:310`、
  `yate/services/data_store.py:31`、`yate/logs.py:190,197`。
  `yate/paths.py` 自述为"磁盘资源位置的唯一权威入口"，但其 docstring（:23-24）明确把
  可写用户数据排除在外——本计划一并修订该声明。
- 取证 2（S5）：`logs.py:188-199` 两个 mkdir 无显式权限；同文件域内 `trust.py:103-111`
  已有 0700/0600 + POSIX chmod 范式。`~/.yate/data` 存崩溃报告与 trace 日志，
  应 owner-only。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `yate/paths.py`
2. `yate/yaterc.py`
3. `yate/services/trust.py`
4. `yate/services/data_store.py`
5. `yate/services/extensions/loader.py`
6. `yate/logs.py`
7. `yate/diagnostics.py`
8. `yate/cli.py`（仅 plan-a 已改区域内的 home themes 一行）
9. `tests/test_paths.py`（若无则新建；先 `ls tests/test_paths*` 确认）

## 具体修改

### 1. `yate/paths.py`

- 新增（放在 `EXTENSIONS_DIRNAME` 附近）：

```python
#: Directory name of the per-user yate home under the OS home directory.
YATE_HOME_DIRNAME: str = ".yate"


def yate_home() -> Path:
    """The per-user writable home (``~/.yate``); owners create subdirectories.

    Single authoritative spelling of the user-level root: rc, trust store,
    user extensions, data and themes all resolve under it.  The directory
    itself is not created here.
    """
    return Path.home() / YATE_HOME_DIRNAME
```

- 修订模块 docstring :23-24 的排除句：改为"可写用户数据的**根**由本模块提供
  （`yate_home()`），各子目录语义仍归 owner 模块（config/yaterc、trust、data_store、CLI）"。
  保持英文。

### 2. 各消费点（纯机械替换，行为零变化）

| 文件 | 现状 | 改为 |
|---|---|---|
| `yaterc.py:82-84` | `user_config_path()` 返回 `Path.home()/".yate"/RC_FILENAME` | `yate_home() / RC_FILENAME` |
| `trust.py:35` | `TRUST_FILE = Path.home()/".yate"/"trusted_workspaces"` | `TRUST_FILE: Path = yate_home() / "trusted_workspaces"`（import 期求值语义不变） |
| `data_store.py:29-31` | `data_root()` 返回 `Path.home()/".yate"/DATA_DIRNAME` | `yate_home() / DATA_DIRNAME` |
| `loader.py:310` | `directories.append(Path.home()/".yate"/"extensions")` | `directories.append(yate_home() / "extensions")` |
| `logs.py:190,197` | 两个 `Path.home()/".yate"/DATA_DIRNAME/...` | `yate_home() / DATA_DIRNAME / ...`（`DATA_DIRNAME` 来源不变） |
| `diagnostics.py:230,363` | 两处拼接 | 同法替换（先读上下文确认行号在当前 HEAD 的准确位置） |
| `cli.py` | plan-a 改后的 `Path.home()/".yate"/"themes"` | `yate_home() / "themes"` |

- import 规矩：统一 `from yate.paths import yate_home`；各文件按既有 import 分组插入。
- 层级自查：paths.py 为 L0 叶子，所有消费方（L0-L4）向下引用合法；不新增任何向上边。

### 3. `yate/logs.py`（S5，同文件顺手落位）

`logs_dir()` / `crash_data_dir()` 的 mkdir 之后加：

```python
    if os.name == "posix":
        with contextlib.suppress(OSError):
            os.chmod(directory, 0o700)
```

- 范式照抄 `trust.py:103-106`（含 contextlib.suppress）；logs.py 若缺
  `contextlib`/`os` import 则补。
- 不改 Windows 行为（chmod 是 no-op）。

### 4. `tests/test_paths.py`

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_yate_home_under_os_home` | 调 `yate_home()` | 值 == `Path.home()/".yate"`；目录未被创建 |
| `test_logs_dirs_restrict_on_posix` | `skipif(os.name != "posix")`；monkeypatch `Path.home` 到 tmp 后调 `logs.crash_data_dir()` | POSIX 下 `stat().st_mode & 0o777 == 0o700`；Windows 上跳过 |

- 既有 `user_config_path()` / `data_root()` / `TRUST_FILE` 的旧用例应零改动通过
  （值语义未变）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_paths.py tests/test_logs.py tests/test_trust.py tests/test_data_store.py tests/test_yaterc.py -q
.venv\Scripts\python.exe -m pyright yate/paths.py yate/logs.py yate/cli.py yate/diagnostics.py yate/yaterc.py yate/services/trust.py yate/services/data_store.py yate/services/extensions/loader.py
git grep -n 'Path.home() / ".yate"' -- yate/
```

（测试文件名以 `ls tests/` 实际为准，对不上的用 `pytest -q -k "logs or trust or data_store or yaterc"` 兜底。）

通过判定：pytest 全部 exit 0；pyright 对所改文件零诊断；`git grep` 对 `yate/` 零命中
（tests/ 允许残留，不在收敛面）。

## 风险与回滚

- 触碰 8 个产品文件但均为机械替换；pyright strict + 定向用例 + 主代理全量门禁兜底。
- `TRUST_FILE` 仍为 import 期求值，测试通过 monkeypatch 属性隔离（沿用既有做法）。
- 回滚 = revert 本子计划提交。
