# 崩溃诊断集成方案：faulthandler + excepthook 落盘

> 将 `faulthandler` 与自定义 `sys.excepthook` 集成到 yate，
> 在进程异常退出（native crash / 未捕获 Python 异常）时，
> 将诊断日志写入 `~/.yate/data/` 下带时间戳的 `.err` 文件，
> 便于事后快速定位问题。

> **状态：已实现。** 后续重构把崩溃诊断与运行日志合并为统一模块
> `yate/logs.py`（`CrashService` + `TracingService` 两个互不引用的单例），
> 本文档已按当前代码回写；与初稿的差异见 §8。
>
> 姊妹文档：`logs_impl_plan.md`（运行日志 `YATE_TRACE`）、
> `unify_crash_tracing_plan.md`（两服务统一后的设计）。

---

## 1. 背景与目标

### 1.1 现状（实现前，历史记录）

yate 当时**没有**任何崩溃诊断机制：

- 未引入 `faulthandler`
- 未设置 `sys.excepthook`
- 未使用 `logging` 模块

当进程因 native crash（段错误、SIGABRT 等）或未捕获 Python 异常退出时，
终端关闭后诊断信息即丢失，用户只能复述现象，无法提供回溯。

### 1.2 目标与达成情况

| 目标 | 达成方式（现行代码） |
|------|----------------------|
| **native crash**：所有线程的 Python 回溯落盘 | `faulthandler.enable(file=handle, all_threads=True)`，句柄在 `install()` 时已被**急切打开**（崩溃时无法再可靠地做文件 I/O） |
| **未捕获 Python 异常**：追加到同一文件 | `sys.excepthook = CrashService._excepthook`，写 `=== uncaught Python exception ===` + 回溯块，最后**链回原 hook** |
| **文件位置** | `~/.yate/data/crash-YYYYMMDD-HHMMSS.err`（`build_err_path()`） |
| **零侵入**：诊断失败不影响启动 | 目录/句柄不可用 → 回退 `faulthandler.enable(sys.stderr)` 并直接返回；`excepthook` 内部 `try/except` 吞掉所有异常 |
| *（新增）* 健康退出不留垃圾 | `atexit` → `cleanup_on_exit()`：关闭句柄，若从未记录过异常则删除只含头部的报告 |
| *（新增）* Windows 句柄可控 | `uninstall()`：`faulthandler.disable()` + `cleanup_on_exit()`；`yate --cleanup-defaults --include-data` 先调用它，否则打开的句柄会让删除 `data/` 失败 |

---

## 2. 方案设计

### 2.1 模块归属（现行）

实现位于 **`yate/logs.py`**：`CrashService` 类 + 模块级单例 `crash`。
调用方直接取单例：`from yate.logs import crash` → `crash.install()`；
模块级纯函数按名字导入（`from yate.logs import crash, crash_data_dir` →
`crash_data_dir()`）。曾经短暂存在的 `yate/crash.py` 薄壳已在最终版删除（见 §8）。

| 初稿设计（`yate/crash.py` 模块级） | 现行 |
|------------------------------------|------|
| `crash_data_dir()` | 仍是**模块级纯函数**（`yate/logs.py`）；`yate/diagnostics.py` 与测试按名导入它 |
| `_err_file_path()` | `CrashService.build_err_path(directory, now=None)` |
| `_write_header()` | `CrashService._write_header(handle)` → 复用 `build_session_header(title=f"yate {__version__} crash report")`（与 trace 头部同一个构造函数，输出字节级一致） |
| `install()` | `CrashService.install()`（幂等，返回 `None`），经单例调用 |
| 模块级 `_err_file` / `_err_path` / `_crashed` / `_original_excepthook` | 类的实例属性，配公开只读属性 `err_file` / `err_path` / `had_crash` / `original_excepthook` |
| `_excepthook` / `_cleanup_on_exit`（闭包/私有函数） | 实例方法 `_excepthook()` / `cleanup_on_exit()`（后者公开，供 atexit 与测试调用） |
| *（新增）* | `uninstall()`、`current_path()` / `current_crash_file()`、`is_enabled()` |

调用方式只有一条规则：**对象从 `yate.logs` 取**（`from yate.logs import crash`），
**常量与纯函数按名导入**（`crash_data_dir`、`LEVEL_NAMES`、`resolve_level` …）——
它们在模块里本来就不是单例的成员（`crash.crash_data_dir()` 这种写法已不存在）。
薄壳删除后，同一个 API 只有一个地址，不存在"一会儿 `logs.xxx`、一会儿薄壳"的混淆。

### 2.2 集成点

```python
# yate/cli.py 的 main() 最前面
from yate.logs import crash, tracing

crash.install()          # 第一件事：整个进程生命周期（含启动期）都被覆盖
tracing.install()        # 运行日志 pass 1：只看环境变量
# ... 解析参数 / 加载 yaterc ...
tracing.configure(yate_trace=..., yate_trace_level=...)   # pass 2
```

放在 `main()` 的第一行，确保**整个进程生命周期**（含启动期）都被覆盖。

另一个集成点是 `--cleanup-defaults --include-data` 分支：

```python
if args.include_data:
    crash.uninstall()    # 先释放句柄，否则 Windows 上删不掉 data/
    tracing.uninstall()
```

### 2.3 文件命名

```
~/.yate/data/crash-20260913-101530.err
```

格式：`crash-YYYYMMDD-HHMMSS.err`（本地时间；同名冲突极少，靠时间戳区分）。
生成逻辑集中在 `CrashService.build_err_path()`，测试可用 `now=` 注入固定时间。

### 2.4 文件内容结构

```
yate 0.2.4 crash report
time: 2026-09-21T19:20:03
cwd: D:\Programming\yate
argv: ['-c']
python: 3.13.2 on win32
------------------------------------------------------------

=== uncaught Python exception ===
Traceback (most recent call last):
  ...
RuntimeError: smoke-boom
```

- **头部**：进程元数据（版本、时间、cwd、argv、Python 版本），由
  `build_session_header()` 生成；与 trace 日志的头部同构（同样字段、同样顺序、
  同一条 60 字符分隔线）
- **native crash**：`faulthandler` 直接向 fd 写入所有线程回溯
- **Python 异常**：自定义 `excepthook` 追加回溯块，然后交给原 hook（终端照常打印）

---

## 3. 技术要点

### 3.1 faulthandler 的 fd 特性

`faulthandler` 在致命信号触发时**绕过 Python 缓冲**直接写文件描述符。
因此：

1. 头部写入后必须**显式 `flush()`**，否则缓冲内容会丢失
2. 使用**行缓冲文本模式**（`buffering=1`），减少手动 flush 频率
3. 文件句柄需保持打开直到进程结束（由 `CrashService` 实例持有，
   崩溃发生在 `atexit` 之前，所以报告一定留在磁盘上）

### 3.2 健壮性设计

| 风险 | 现行应对措施 |
|------|--------------|
| 数据目录创建 / 打开失败 | `except (OSError, ValueError)` → 回退 `faulthandler.enable(file=sys.stderr)` → 直接 `return`（`sys.excepthook` 保持原样，不假装已安装） |
| `faulthandler.enable()` 在 stderr 上失败（无 fileno 的流） | 内层 `except Exception: pass`，`install()` 绝不抛异常 |
| `excepthook` 自身抛异常 | 内层 `try/except` 吞掉，**始终**调用原始 hook，绝不遮蔽原故障 |
| 重复调用 `install()` | `self._err_file is not None` 守护，幂等；重复 `install()` 不会创建第二个文件、也不会重复包装 hook |
| 健康退出留下空报告 | `atexit` → `cleanup_on_exit()`：flush + close，`_crashed` 为假时 `unlink(missing_ok=True)` |
| 需要删除 `data/`（Windows 句柄占用） | `uninstall()` = `faulthandler.disable()` + `cleanup_on_exit()`；幂等、best-effort |
| 真正的崩溃 | 进程在 `atexit` 之前终止 → `_crashed` / 文件保持，报告保留 |
| 布局变化导致读取脚本失效 | 头部统一由 `build_session_header()` 生成，crash 与 trace 不会各自漂移 |

### 3.3 两类崩溃的覆盖路径

```
                    +----------------------+
                    |   crash.install()    |   ← main() 第一行
                    +----------+-----------+
                               |
                      打开 crash-*.err + 写头部 + flush()
                               |
                +--------------+--------------+
                |                             |
        faulthandler.enable()        sys.excepthook = _excepthook
        (致命信号 → 写 fd)           (未捕获异常 → 追加 + 原 hook)
                |                             |
                +--------------+--------------+
                               |
                    ~/.yate/data/crash-*.err
                               |
        +----------------------+----------------------+
        |                      |                      |
   native crash           未捕获异常              正常退出
   (进程立即终止)      (_crashed = True)      (atexit → cleanup_on_exit)
   报告保留             报告保留               仅含头部 → 删除
```

### 3.4 与运行日志（tracing）的边界

`excepthook` **不再**把异常镜像进 trace 日志：早期实现里有一句
`tracing.get_logger("crash").error(...)`，它让 crash 依赖 tracing；现行设计要求
两个服务互不引用（硬约束），所以该调用已删除，`yate/logs.py` 内不存在
`crash → tracing` 的引用。

需要"崩溃也进时间线"时，协调逻辑放在调用方（`cli.py`）：`crash.had_crash` +
`tracing.is_enabled()` 都在手边，可在 cli 层补一个钩子，而不必让两个服务互相依赖。

---

## 4. 实施步骤（回写为当前实现）

### 步骤 1：`yate/logs.py` 中的 `CrashService`

```python
class CrashService:
    def __init__(self) -> None:
        self._err_file: Optional[TextIO] = None
        self._err_path: Optional[Path] = None
        self._crashed: bool = False
        self._original_excepthook: Callable[..., Any] = sys.excepthook

    def install(self) -> None:
        """Enable on-disk crash diagnostics. Idempotent and best-effort."""
        if self._err_file is not None:
            return
        try:
            path = self.build_err_path(crash_data_dir())
            handle = open(path, "w", encoding="utf-8", buffering=1)
            self._write_header(handle)
            handle.flush()
            faulthandler.enable(file=handle, all_threads=True)
        except (OSError, ValueError):
            try:
                faulthandler.enable(file=sys.stderr, all_threads=True)
            except Exception:
                pass
            return

        self._err_file = handle
        self._err_path = path
        atexit.register(self.cleanup_on_exit)
        sys.excepthook = self._excepthook

    def _excepthook(self, exc_type, exc_value, exc_tb) -> None:
        self._crashed = True
        handle = self._err_file
        if handle is not None:
            try:
                handle.write("\n=== uncaught Python exception ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
                handle.flush()
            except Exception:
                pass
        self._original_excepthook(exc_type, exc_value, exc_tb)
```

（`cleanup_on_exit()` / `uninstall()` / `build_err_path()` / 只读属性的完整实现见
`yate/logs.py`，行号约 249–407。）

单例在模块末尾创建：`crash = CrashService()`；`yate/crash.py` 把它作为
`_service` 私有别名导入，只再导出 `crash_data_dir` / `install` / `uninstall` /
`current_crash_file`。

### 步骤 2：修改 `yate/cli.py`

```python
def main(argv=None):
    from yate.logs import crash, tracing
    crash.install()          # 崩溃诊断
    tracing.install()        # 运行日志 pass 1（env only）
    # ... 原有逻辑；yaterc 加载后 tracing.configure(...)
```

### 步骤 3：测试 `tests/test_crash.py`（11 项）

覆盖清单（现行）：

- `crash_data_dir()` 正确创建 `~/.yate/data/`
- `build_err_path()` 命名格式正确 / 不传时间时使用当前时间
- `install()` 启用 faulthandler、创建带正确头部的 `.err` 文件
- `install()` 幂等（多次调用不重复创建文件、不重复包装 hook）
- `uninstall()` 释放句柄并删除"健康"报告（`--include-data` 场景）
- `excepthook` 追加回溯并**委托原 hook**（`sentinel.assert_called_once_with(...)`）
- 正常退出（`cleanup_on_exit()`）删除只含头部的报告
- 出现未捕获异常后报告被保留
- 数据目录不可用 → 回退 stderr、不抛异常、hook 不被替换
- stderr 没有 fileno（`io.StringIO`）→ 同样不抛异常

测试语义要点：

- **单例直连**：`from yate.logs import crash`，测试里的 `crash.install()` /
  `crash.build_err_path(...)` / `crash.cleanup_on_exit()` / `crash.current_crash_file()`
  都是对象上的方法调用（与生产调用点同一条路径）
- 状态属性是**只读**的，所以 fixture 直接重置底层属性
  （`crash._err_file` / `_err_path` / `_crashed`；文件顶部保留
  `# pyright: reportPrivateUsage=false`），并在末尾恢复
  `crash._original_excepthook` 与 `sys.excepthook`、复位 `faulthandler`
- 降级用例 patch 的是 **`yate.logs.crash_data_dir`**（`install()` 从 `yate.logs`
  自己的模块全局解析该函数，patch 服务对象不会生效）

---

## 5. 验证方案

### 5.1 单元测试

```powershell
python -m pytest tests/test_crash.py -q      # 11 项
python -m pytest tests/                      # 全量 612 passed
pyright                                      # strict，0 errors
```

### 5.2 Python 异常路径手动验证

真实 `~/.yate` 会被写脏，建议用沙箱 HOME：

```powershell
$home = "$PWD\.smoke-home"
$env:USERPROFILE = $home; $env:HOME = $home
python -c "from yate.logs import crash; crash.install(); raise RuntimeError('test')"
Get-ChildItem -Recurse "$home\.yate\data"            # crash-*.err 已保留
Get-Content (Get-ChildItem "$home\.yate\data\crash-*.err")[0]
Remove-Item -Recurse -Force $home
```

期望：报告含头部 + `=== uncaught Python exception ===` + `RuntimeError: test`。

### 5.3 faulthandler 启用状态验证

```powershell
python -c "from yate.logs import crash; crash.install(); import faulthandler; print(faulthandler.is_enabled())"
```

期望 `True`；随后退出时 `atexit` 会删掉这份只含头部的报告（可顺便验证清理逻辑）。

### 5.4 真实 native crash 验证说明

> ⚠️ **注意**：在 CPython 解释器环境下，`ctypes` 制造的访问违规会被 ctypes 的 SEH 保护捕获并转换为 Python 异常，无法走到 `SetUnhandledExceptionFilter` 路径。
>
> 验证真实 native crash 需要：
> - 编译小型 C 扩展/独立崩溃子进程触发真正未处理异常；或
> - 在 PyInstaller 打包后的二进制中测试
>
> 源码模式下可验证的是**回调逻辑与落盘逻辑**，编译模式下再验证真实崩溃路径。

---

## 6. 文件变更清单（现行）

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/logs.py` | 新增 | 统一日志模块：`CrashService`（本节）、`TracingService`、共享纯函数与单例 |
| `yate/crash.py`、`yate/tracing.py` | 新增后删除 | 曾作为"薄壳"再导出旧导入路径；最终版删除，调用方直连 `yate.logs`（见 §8） |
| `yate/cli.py` | 修改 | `from yate.logs import crash, tracing`；`main()` 首行 `crash.install()`；`--include-data` 分支先 `crash.uninstall()` |
| `tests/test_crash.py` | 修改 | 单例直连；patch 目标改为 `yate.logs` 的模块全局 |
| `yate/diagnostics.py` | 修改 | `from yate.logs import crash, crash_data_dir` |

---

## 7. 后续可扩展方向

- **崩溃提示**：下次启动时检测到上一次留下的 `.err` 文件，在状态栏提示用户
  （`yate.diagnostics` 已有列出报告的能力，可复用）
- **日志轮转**：限制 `~/.yate/data/` 下 `.err` / `.log` 数量，避免无限堆积
- **环境变量开关**：`YATE_NO_CRASH_LOG=1` 禁用诊断（CI/容器场景）
- **minidump**：Windows 下配合 `MiniDumpWriteDump` 生成完整 dump（需 C 扩展）
- **与 tracing 的协调钩子**：见 §3.4，在 `cli.py` 层把崩溃事件写进 trace 时间线

---

## 8. 与初稿的差异（回写记录）

1. **模块归属**：初稿把全部逻辑放在 `yate/crash.py` 的模块级函数/变量里；
   现行实现收进 `yate/logs.py::CrashService`（单例 + 实例状态 + 只读属性）。
   `yate/crash.py` 先被改成"薄壳"（再导出旧导入路径），最终版**删除**：
   调用点从 `from yate import crash` 变成 `from yate.logs import crash`，
   方法名（`install()` / `current_crash_file()`）不变，模块级函数 `crash_data_dir()`
   改为按名导入。
2. **函数改名**：`_err_file_path()` → `build_err_path()`；
   `_cleanup_on_exit()` → `cleanup_on_exit()`（公开，供 atexit/测试）。
3. **新增行为**：`atexit` 清理（健康退出删除只含头部的报告）、`uninstall()`
   （Windows 上先释放句柄再删 `data/`）、`is_enabled()`、`current_path()` 与别名
   `current_crash_file()`。初稿的"不做任何退出拦截"仍然成立——注册的只是
   `atexit` 清理，不拦截任何退出路径。
4. **头部来源**：初稿手写五行头部；现由共享的 `build_session_header()` 生成
   （crash 与 trace 同构），**输出字节完全一致**（已实测比对）。
5. **删除 crash → tracing 镜像**：初稿之后的实现曾在 `excepthook` 里调用
   `tracing.get_logger("crash").error(...)`；统一重构时删除，两服务互不引用
   （见 §3.4）。
6. **测试适配**：`tests/test_crash.py` 改为面向单例与公开名，降级用例 patch
   `yate.logs.crash_data_dir`。
