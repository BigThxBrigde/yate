# SP3 — editor_term 终端（N7）

> 波次一 · 规模 S · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/editor_term/emulator.py`（N7）

**测试：** `tests/test_terminal_emulator.py`（仅新增）

不许动其它任何文件；范围外发现上报主代理。

## 第 0 步：现状复核

核对 P2 原文 N7 锚点：`_soft_reset`（ESC c）是否仍未退出备用屏幕。P1 波次二刚改过本文件
（S6 宽字符末列、S16 死分支），以当前代码为基准；若已修复则免实施只回填。

## 条目执行

### N7 — `_soft_reset`（ESC c）退出备用屏幕

1. **输入**：P2 原文 N7 行（加 `self._exit_alt_screen()` 或等价状态复位，对齐 xterm RIS 部分语义）。
2. **步骤**：
   - 读 `_soft_reset` 与 `_exit_alt_screen` 现实现，确认复用后状态复位集合正确
     （alt screen 退出 + 光标/滚动区等 RIS 部分复位语义，以现有方法为准，不新造状态）；
   - 若 `_exit_alt_screen` 不存在或语义过宽，则按最小改动：退出 alt screen 标志即可，上报偏离。
3. **输出**：备用屏幕中写入 `ESC c` 后 `alt_screen` 为 False，回到主屏幕。
4. **验收**：新增用例——进入 alt screen → 写 `ESC c` → 断言 alt_screen False；
   既有 emulator 用例全绿（含 S6 宽字符用例）。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/editor_term/emulator.py tests/test_terminal_emulator.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_terminal_emulator.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + 校准记录

## 校准记录

（实施时回填）
