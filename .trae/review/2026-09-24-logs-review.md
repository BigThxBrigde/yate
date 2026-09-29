# yate Code Review — 复审补充（logs.py）— 2026-09-24

## 复审补充（logs.py）— 2026-09-24

> 来源：外部审查工具报告的 2 个改进项，均指向 `yate/logs.py`；主代理现场读码
> 核实成立，登记于此，**均未修**。

- [x] **`warn()` 在 `sys.stderr` 为 `None` 时退化为写 stdout，与 docstring 承诺不符（Low，可维护性）** —
  [`logs.py:85-87`](../../yate/logs.py#L85-L87)
  `pythonw` 等 GUI 环境下 `sys.stderr` 为 `None`，而 `print(..., file=None)` 按 Python 语义回退到
  `sys.stdout`：警告文本会打进 TUI 屏幕，docstring 的「Print ``yate: <message>`` to stderr」名不副实。
  **修复**：`if sys.stderr is not None:` 再 `print(...)`——stderr 不可用时静默丢弃，与
  「Never raises」承诺一致。
  *✅ 已修复（2026-09-25，P2 波次二 SP7）：`warn()` 入口 `if sys.stderr is None: return`，docstring 补 pythonw 行为；守卫 `test_warn_silently_drops_output_when_stderr_is_none`（monkeypatch stderr=None，断言不抛且 stdout/stderr 均空）。*

- [x] **崩溃报告 / trace 日志文件名仅秒级精度，同秒并发启动互相覆盖或交织（Low，功能性）** —
  [`logs.py:396-401`](../../yate/logs.py#L396-L401)、[`logs.py:522-523`](../../yate/logs.py#L522-L523)
  `build_err_path` 生成 `crash-YYYYMMDD-HHMMSS.err`，且 [`logs.py:319`](../../yate/logs.py#L319) 以
  `"w"` 模式打开：同一秒内先后启动两个进程，后者截断前者的头部，两进程随后向同一文件交叉写入，
  崩溃报告互毁（faulthandler 的 fd 也指向被截断的文件）。trace 日志
  （[`logs.py:523`](../../yate/logs.py#L523)）同为秒级命名，但 `mode="a"`
  （[`logs.py:221`](../../yate/logs.py#L221)）只交织不覆盖——同秒两进程的会话 header 会混入同一文件。
  *存量问题，非新引入；多 yate 实例共享同一数据目录，场景真实但触发概率低。*
  **修复**：文件名追加 pid（`crash-YYYYMMDD-HHMMSS-<pid>.err`）或改微秒精度时间戳；trace 同理。
  *✅ 已修复（2026-09-24）— [logs.py](../../yate/logs.py) `build_err_path` 与 trace 文件名均追加 pid 后缀（`crash-YYYYMMDD-HHMMSS-<pid>.err`；trace 同理）；守卫：monkeypatch `os.getpid`（111/222）同秒两次 `build_err_path` 断言路径不同；副作用记录：test_crash.py 两处既有断言（文件名字面量与正则）固化的正是被修复的碰撞缺陷本身，已同步改为含 pid 的等价断言。*
