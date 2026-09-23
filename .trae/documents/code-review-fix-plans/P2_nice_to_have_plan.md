# P2 Nice-to-have 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Nice-to-have 段（2026-09-23 复核后
> 仍存在的条目）。均为锦上添花，不阻塞发布；随手清理即可，无独立排期。
> **本文档仅为计划，未实施。**

| # | 条目 | 位置 | 策略 | 测试 |
|---|---|---|---|---|
| N1 | 保存始终 LF，忽略原始/平台换行 | [document.py:50-53](../../../yate/editor_core/document.py) | 打开时记录原始 dominante EOL（crlf/lf/cr），保存按其写回；默认保持 LF。仅对已存在文件生效，新文件一律 LF | crlf 文件往返 round-trip 断言 EOL 不变 |
| N2 | config tokenizer 重叠 token | [regex_backend.py:651-677](../../../yate/editor_syntax/regex_backend.py) | 各 `finditer` 独立发射；改为按 start 排序后对重叠区间取先到者（或合并为一次交替扫描） | `"true1"` / 字符串内数字用例断言不双着色 |
| N3 | 缺符号时报错无上下文 | [ts_backend/languages.py:243-254](../../../yate/editor_syntax/ts_backend/languages.py) | `getattr(dll, symbol)` 包 try，`raise RuntimeError(f"{library_path} lacks entry point {symbol!r} ...") from e`（`_FAILED` 缓存已防重复） | monkeypatch 假 dll 缺符号，断言错误消息含路径与符号名 |
| N4 | `_to_char` 字节偏移边界缺注释 | [ts_backend/backend.py:~115](../../../yate/editor_syntax/ts_backend/backend.py) | 纯注释补充：说明 UTF-8 多字节中间偏移为何映射到字符首列 | 无（注释） |
| N5 | Outdent 按 tab_width 而非上一个 tab stop | [buffer.py:510-525](../../../yate/editor_core/buffer.py) | 空格行改算 `rrem = removed % tab_width`，`removed - (rrem or tab_width)` 对齐上一个 stop；整 Tab 剥离保留 | 3 空格缩进 + tab_width=4 → 移除 3；8 空格 → 移除 4 |
| N6 | `replace_current` 可用 `replace_range` 简化 | [search.py:102](../../../yate/editor_core/search.py) | 内部改调 `replace_range(buffer, match_span, replacement)`，删重复实现 | 现有 replace 用例全绿 |
| N7 | `_soft_reset`（ESC c）不退备用屏幕 | [emulator.py:387-397](../../../yate/editor_term/emulator.py) | 加 `self._exit_alt_screen()`（或等价状态复位），对齐 xterm RIS 部分语义 | 写入 `ESC c` 后断言 alt_screen 为 False |
| N8 | ctrl+digit 用 kitty CSI-u | [base.py:118-121](../../../yate/keymaps/base.py) | 换绑到多数终端可发的替代键（如 alt+digit），或保留 kitty 绑定同时文档标注终端要求；**实施前先在 Windows Terminal / cmd 验证** | 手动验证 + 冒烟关键路径 |
| N10 | `cycle_tab` 空操作循环 | [editor.py:476-484](../../../yate/editor.py) | 单 tab 时 no-op 且不提示（或保留提示但仅 verbose）；倾向静默 no-op | 单 tab 连按断言无消息、无异常 |
| N13 | smoke 工具自身无测试 | [tools/smoke_test/](../../../tools/smoke_test/) | 对纯函数部分（场景解析、报告渲染、`extract_svg_rows`）补 `tests/test_smoke_tool.py`；harness 端到端不测（冒烟本身即验证） | 新测试文件 |
| N14 | SVG 提取正则依赖 Textual 版本 | [harness.py:130](../../../tools/smoke_test/harness.py) | 提取失败时给明确报错并打印 SVG 头部片段（诊断版本漂移）；正则收紧为当前实测格式并在注释记录适配的 Textual 版本 | 喂旧版/新版 SVG 样例断言行为 |
| N15 | 单场景执行无整体超时 | [tools/smoke_test/](../../../tools/smoke_test/) | harness 用 `asyncio.wait_for(scenario, timeout=per_scenario)`（默认 60s，`--timeout` 可调），超时记 failed 并继续 | 人造挂起场景断言超时生效 |
| N16 | `check_commit_pushed` 仅支持 gitee | [gitee.py:61-85](../../../tools/changelog/gitee.py) | 其它 host 返回 `None` 时由调用方输出「无法核验，跳过 gate」而非当失败；github 可用 `api.github.com` 同构实现 | 单测 host 分派 |
| N17 | `strip_unreleased` 边界未测 | [render.py:89-108](../../../tools/changelog/render.py) | 补用例：仅有 Unreleased 段、Unreleased 为空、Unreleased 在末尾三种 | 新增 3 条单测 |

## 建议处理方式

- **N4 / N6 / N10 / S16**（P1 已含）属「顺手清」级，可在任何触碰对应文件的
  PR 里捎带完成；
- **N1 / N8** 涉及行为变化，实施前需在目标环境人工验证；
- 其余为纯增益，按批次随 P1 工具链改动同批处理。
