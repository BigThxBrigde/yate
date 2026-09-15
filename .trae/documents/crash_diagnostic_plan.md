# 崩溃诊断集成方案：faulthandler + excepthook 落盘

> 将 `faulthandler` 与自定义 `sys.excepthook` 集成到 yate，
> 在进程异常退出（native crash / 未捕获 Python 异常）时，
> 将诊断日志写入 `~/.yate/data/` 下带时间戳的 `.err` 文件，
> 便于事后快速定位问题。

---

## 1. 背景与目标

### 1.1 现状

yate 当前**没有**任何崩溃诊断机制：

- 未引入 `faulthandler`
- 未设置 `sys.excepthook`
- 未使用 `logging` 模块

当进程因 native crash（段错误、SIGABRT 等）或未捕获 Python 异常退出时，
终端关闭后诊断信息即丢失，用户只能复述现象，无法提供回溯。

### 1.2 目标

- **native crash**：通过 `faulthandler` 将所有线程的 Python 回溯落盘
- **未捕获 Python 异常**：通过包装 `sys.excepthook` 将回溯追加到同一文件
- **文件位置**：`~/.yate/data/crash-YYYYMMDD-HHMMSS.err`
- **零侵入**：诊断失败不影响编辑器正常启动（best-effort）

---

## 2. 方案设计

### 2.1 新增模块：`yate/crash.py`

与 `paths.py`、`config.py` 同级，属启动期基础设施。

| 函数/变量 | 职责 |
|-----------|------|
| `crash_data_dir()` | 返回并创建 `~/.yate/data/` |
| `_err_file_path()` | 生成带时间戳的 `.err` 文件路径 |
| `_write_header()` | 写入进程元数据头并 flush |
| `install()` | 主入口：打开文件 → 写头 → `faulthandler.enable()` → 包装 `sys.excepthook` |

### 2.2 集成点

```python
# yate/cli.py 的 main() 最前面
from yate import crash
crash.install()
```

放在 `main()` 的第一行，确保**整个进程生命周期**（含启动期）都被覆盖。

### 2.3 文件命名

```
~/.yate/data/crash-20260913-101530.err
```

格式：`crash-YYYYMMDD-HHMMSS.err`

### 2.4 文件内容结构

```
yate 0.1.0 crash report
time: 2026-09-13T10:15:30
cwd: /home/user/project
argv: ['yate', 'main.py']
python: 3.11.5 on win32
------------------------------------------------------------

=== uncaught Python exception ===
Traceback (most recent call last):
  ...
ValueError: boom
```

- **头部**：进程元数据（版本、时间、cwd、argv、Python 版本）
- **native crash**：`faulthandler` 直接向 fd 写入所有线程回溯
- **Python 异常**：自定义 `excepthook` 追加回溯块

---

## 3. 技术要点

### 3.1 faulthandler 的 fd 特性

`faulthandler` 在致命信号触发时**绕过 Python 缓冲**直接写文件描述符。
因此：

1. 头部写入后必须**显式 `flush()`**，否则缓冲内容会丢失
2. 使用**行缓冲文本模式**（`buffering=1`），减少手动 flush 频率
3. 文件句柄需保持打开直到进程结束（模块级变量持有）

### 3.2 健壮性设计

| 风险 | 应对措施 |
|------|----------|
| 数据目录创建失败 | `try/except` 捕获，回退到 `sys.stderr`，不阻塞启动 |
| `excepthook` 自身抛异常 | 内层 `try/except` 吞掉，始终调用原始 hook |
| 重复调用 `install()` | 模块级 `_err_file` 守护，幂等 |
| 退出路径阻塞 | 不做任何退出拦截，让默认行为执行 |

### 3.3 两类崩溃的覆盖路径

```
                    +----------------------+
                    |   crash.install()    |
                    +----------+-----------+
                               |
                +--------------+--------------+
                |                             |
        faulthandler.enable()        sys.excepthook = wrapper
        (致命信号 → 写 fd)          (未捕获异常 → 追加 + 原hook)
                |                             |
                +--------------+--------------+
                               |
                    ~/.yate/data/crash-*.err
```

---

## 4. 实施步骤

### 步骤 1：创建 `yate/crash.py`

核心实现：

```python
import faulthandler
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import IO, Optional

from yate import __version__

DATA_DIRNAME = "data"
ERR_PREFIX = "crash-"
ERR_SUFFIX = ".err"

_err_file: Optional[IO[str]] = None
_original_excepthook = sys.excepthook


def crash_data_dir() -> Path:
    directory = Path.home() / ".yate" / DATA_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def install() -> None:
    global _err_file
    if _err_file is not None:
        return
    try:
        path = crash_data_dir() / f"{ERR_PREFIX}{datetime.now():%Y%m%d-%H%M%S}{ERR_SUFFIX}"
        _err_file = open(path, "w", encoding="utf-8", buffering=1)
        _err_file.write(f"yate {__version__} crash report\n")
        _err_file.write(f"time: {datetime.now().isoformat(timespec='seconds')}\n")
        _err_file.write(f"cwd: {os.getcwd()}\n")
        _err_file.write(f"argv: {sys.argv}\n")
        _err_file.write(f"python: {sys.version.split()[0]} on {sys.platform}\n")
        _err_file.write("-" * 60 + "\n")
        _err_file.flush()
        faulthandler.enable(file=_err_file, all_threads=True)
    except (OSError, ValueError):
        try:
            faulthandler.enable(file=sys.stderr, all_threads=True)
        except Exception:
            pass
        return

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            if _err_file is not None:
                _err_file.write("\n=== uncaught Python exception ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=_err_file)
                _err_file.flush()
        except Exception:
            pass
        _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook
```

### 步骤 2：修改 `yate/cli.py`

在 `main()` 开头安装诊断：

```python
def main(argv=None):
    from yate import crash
    crash.install()
    # ... 原有逻辑
```

### 步骤 3：编写测试 `tests/test_crash.py`

测试覆盖：

- `crash_data_dir()` 正确创建 `~/.yate/data/`
- `_err_file_path()` 命名格式正确
- `install()` 启用 faulthandler 并创建 `.err` 文件
- `install()` 幂等（多次调用不重复创建文件）
- 未捕获异常追加到 `.err` 文件
- 数据目录不可用时回退到 stderr 且不抛异常

---

## 5. 验证方案

### 5.1 单元测试

```powershell
python -m pytest tests/test_crash.py -v
```

### 5.2 Python 异常路径手动验证

```powershell
python -c "from yate import crash; crash.install(); raise RuntimeError('test')"
dir $HOME\.yate\data\crash-*.err
```

### 5.3 faulthandler 启用状态验证

```powershell
python -c "from yate import crash; crash.install(); import faulthandler; print(faulthandler.is_enabled())"
```

### 5.4 真实 native crash 验证说明

> ⚠️ **注意**：在 CPython 解释器环境下，`ctypes` 制造的访问违规会被 ctypes 的 SEH 保护捕获并转换为 Python 异常，无法走到 `SetUnhandledExceptionFilter` 路径。
>
> 验证真实 native crash 需要：
> - 编译小型 C 扩展/独立崩溃子进程触发真正未处理异常；或
> - 在 PyInstaller 打包后的二进制中测试
>
> 源码模式下可验证的是**回调逻辑与落盘逻辑**，编译模式下再验证真实崩溃路径。

---

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/crash.py` | 新增 | 崩溃诊断核心模块 |
| `yate/cli.py` | 修改 | `main()` 开头调用 `crash.install()` |
| `tests/test_crash.py` | 新增 | 单元测试 |
| `.trae/documents/crash_diagnostic_plan.md` | 新增 | 本文档 |

---

## 7. 后续可扩展方向

- **日志轮转**：限制 `~/.yate/data/` 下 `.err` 文件数量，避免无限堆积
- **崩溃提示**：下次启动时检测到上一次的 `.err` 文件，在状态栏提示用户
- **环境变量开关**：`YATE_NO_CRASH_LOG=1` 禁用诊断（CI/容器场景）
- **minidump**：Windows 下配合 `MiniDumpWriteDump` 生成完整 dump（需 C 扩展）
