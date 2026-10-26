# perf-audit-fixes-terminal-plan-b（成员 A2：P9）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P9。

## 一、目标

**P9（major）**：集成终端的 VT 解析跑在 UI 事件循环上——读线程每输出块（最大 64KB）
经 `call_soon_threadsafe` 投递，`_on_output`（editor_view/terminal.py:195-205）同步调
`emulator.feed(data)`（emulator.py:201-211，逐字符 `_consume → _ground → _print →
_char_width`，每打印字符 2 次 `unicodedata` 调用 + 每字符一个 8 字段 Cell 分配），
无预算上限。批量输出时主循环被解析占满，UI 卡顿。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_term/emulator.py`（仅当实现需要暴露批量接口时才动；预期主要在组件侧）
- `yate/editor_view/terminal.py`

关联测试（可改/可新增用例）：
- `tests/test_terminal_emulator.py`、`tests/test_terminal.py`、
  `tests/test_pty_proc.py`、`tests/test_app_terminal.py`

## 三、实施要点

1. `TerminalPanel._on_output`（terminal.py:195-205）改为：chunk 追加到实例级
   `bytearray` 缓冲，然后 `self.call_after_refresh(self._drain_output)`（去重：
   已有 pending drain 则不再排）；`_drain_output` 每帧把缓冲整体 `feed` 给
   模拟器并清空。
2. 缓冲上限：如 1 MiB——超限时 `_on_output` 立即同步 drain（防输出速率高于帧率
   导致无限膨胀）；上限常量模块级命名。
3. `feed` 后的 `self._grid_seq += 1; self.refresh()` 语义不变（仍在 drain 内）。
4. emulator.py 不改解析算法本身（ASCII 批量快路径为非目标）；若 feed 接口无需
   变化则该文件零改动。
5. 多实例/关闭时序：面板移除时若有 pending drain，需防 `call_after_refresh`
   回调在 unmount 后触达已卸载组件（Textual 通常安全，仍需在 drain 开头判活）。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_terminal_emulator.py tests/test_terminal.py tests/test_pty_proc.py tests/test_app_terminal.py -q
```

补用例：连续多块输出合帧后最终内容正确（多 chunk 拼接后解析结果与逐块一致）；
缓冲超限路径不丢字节。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

合帧引入单帧解析延迟（正常输出体量下不可感）；上限兜底防膨胀。
回滚：本成员产物单独提交，可独立 revert。
