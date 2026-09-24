# SP2 — 终端子系统健壮性（S6 + S10 + S16 + S32 + S43）

> 来源：[P1 批次二（S6/S10）](../P1_suggestions_plan.md)、[批次三（S16）](../P1_suggestions_plan.md)、
> [批次四（S43）](../P1_suggestions_plan.md)、[批次六（S32）](../P1_suggestions_plan.md)。
> 统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S6 | [emulator.py:426-430](../../../../yate/editor_term/emulator.py) | 宽字符在最后一列被丢弃（仅置 autowrap） | M |
| S10 | [pty_proc.py:557-566](../../../../yate/editor_term/pty_proc.py) | `_exit_code` 三态模糊（STILL_ACTIVE 与 API 失败同为 None） | M |
| S16 | [terminal.py:280](../../../../yate/editor_view/terminal.py) | 死条件分支 `cell.char if cell.char != " " else " "` | S |
| S32 | [terminal.py:104-121](../../../../yate/editor_view/terminal.py) | PTY spawn 失败后面板永久空白无法复活 | M |
| S43 | [pty_proc.py:78](../../../../yate/editor_term/pty_proc.py) | `except BaseException:` 缺理由注释（同文件其它宽捕获均有） | S |

## 独占文件清单（只许改这些）

- `yate/editor_term/emulator.py`
- `yate/editor_term/pty_proc.py`
- `yate/editor_view/terminal.py`
- `tests/test_terminal_emulator.py`、`tests/test_pty_proc.py`、`tests/test_terminal.py`（新增用例）

## 实施步骤

1. **第 0 步 复核**：五条锚点逐一确认（重点：S32 的 `self.proc = proc` 是否仍在
   `await proc.start()` 之前）。
2. **S6**：宽字符 `col == width - 1` 时先执行换行、再在新行 col 0 完整放置，与既有
   autowrap 延迟换行机制语义对齐（P1 策略：先换行后放置）。行中间宽字符行为不变。
3. **S10**：新增内部 `_exit_code_or_failed()` 区分 `running / failed / code` 三态；
   公开 `exit_code` 签名不变；调用点（状态栏轮询）按需采用新方法。
4. **S16**：分支简化为 `cell.char`，删除恒等条件。
5. **S32**：spawn 失败分支复位 `proc=None`、`dead=True`，让面板回到可重生状态。
6. **S43**：补一行理由注释（re-raise 不吞异常，纯合规）。
7. **守卫测试**：S6 宽字符行末 → 下一行首列出现、行中间不变；S10 三态各一条
   （活进程 / 退出 / 句柄无效，平台不适用的显式 skip）；S32 monkeypatch spawn 抛错 →
   dead 态且重生路径可达；S16 现有终端渲染用例全绿。
8. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright yate/editor_term/emulator.py yate/editor_term/pty_proc.py yate/editor_view/terminal.py tests/test_terminal_emulator.py tests/test_pty_proc.py tests/test_terminal.py
   .venv\Scripts\python.exe -m pytest tests/test_terminal_emulator.py tests/test_pty_proc.py tests/test_terminal.py -q
   ```

## 注意

- S10 的 Windows 路径（`STILL_ACTIVE`）在 POSIX CI 上不可测：按文件既有平台 skip 惯例。
- S6 涉及终端语义，改动前先在报告中写明与现有 autowrap 的交互顺序（先写后换）。
