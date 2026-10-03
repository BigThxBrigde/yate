# wiki 翻译进度改动评审（PR !50）

- **日期**：2026-10-03
- **对象**：`feat/wiki-translate-progress`（worktree `../yate-wiki-translate-progress`），
  提交 `2ac8453` → `6a03d6b`；PR：<https://gitee.com/jermaine/yate/pulls/50>
- **评审人**：code-review-expert 子代理（主代理复核并重跑全部命令）
- **对照基准**：[`.trae/documents/wiki-translate-progress-plan.md`](../documents/wiki-translate-progress-plan.md)
  （唯一规范来源）、`architecture-boundaries.md`、`python-coding-style.md`

## 评审范围

`tools/pack/wiki.py`（预扫描 `needs_translation` + rich Progress 进度条）、
`tools/pack/cli.py`（KeyboardInterrupt → exit 130）、`tests/test_pack_wiki.py`
（4 个新用例）、`README.md` / `README.zh.md`（双语说明）。

## 实测门禁（评审时点，退出码均 0）

| 命令 | 结果 |
|---|---|
| `pytest tests/test_pack_wiki.py -q` | 30 passed |
| `pyright yate/ tests/ tools/` | 0 errors |
| `pytest tests/ -q` | 全绿（约 1579 passed / 7 skipped） |

## 发现与处置

| # | 严重度 | 位置 | 问题 | 处置 |
|---|---|---|---|---|
| 1 | major | `tools/pack/wiki.py` `needs_translation` | `--translate-all` 下 recorded-fresh 页预告 "nothing to translate" 但主循环实际翻译，且 `pending=0` 导致进度条不启动（实测探针：2 页 wiki 第二轮多出 2 次翻译调用） | 已修复（`19f44f0`）：adopted/fresh 均返回 `translate_all`；矩阵测试补该格 |
| 2 | major | `tools/pack/wiki.py` 进度描述/预告/失败行 | 页名直入 rich markup：`[edit]` 被吞字；平衡方括号（Windows 文件名合法）触发 `MarkupError` 打崩整个 run 且绕过干净退出 | 已修复（`19f44f0`）：预告/失败行 `markup=False`，进度描述 `rich.markup.escape` |
| 3 | minor | `tools/pack/wiki.py` 失败行 | `[k/len(pages)]` 与进度条 `total=pending` 双分母并存，易误读 | 已修复（`19f44f0`）：统一 `[attempted/pending]` |
| 4 | minor | `tools/pack/wiki.py` 汇总行 | 方案目标"结束后报告结果与耗时"未兑现（非 TTY 下 `TimeElapsedColumn` 不可见） | 已修复（`19f44f0`）：汇总行追加 `in N.Ns` |
| 5 | minor | `tests/test_pack_wiki.py` 预告数断言 | 硬编码 `8 page(s)` 与夹具强耦合 | 已修复（`19f44f0`）：按 `needs_translation` 现算期望值 |
| 6 | nice-to-have | `tools/pack/wiki.py` | 92 字符 genexp 超出 80 字符分行建议（合规 ≤100）；`pending==0` 时 `add_task` 语义噪音 | 未采纳（均无行为影响，注释声明） |

## 核对结论

- **无 blocker / CRITICAL**；两个 major 均已在合入前修复并补测试；
- Ctrl+C 路径核对干净：`cli.main` 单层捕获 → stderr 一行提示 + exit 130，
  `wiki.run` 的 `try/finally` 保证 `Progress.stop()`；单测断言无 "Traceback"；
- stdout 无污染：预告/失败行/进度条全部走 `Console(file=sys.stderr)`，
  stdout 只剩最终汇总；
- pyright strict 零诊断、无 `TYPE_CHECKING`、无新 Protocol、散文式 docstring 合规；
  rich 经 `textual>=8.0` 传递提供（先例 `tools/smoke_test/report.py`）；
- 收尾门禁复核：全量 `pytest tests/ -q` 全绿；首輪
  `test_manual_search_step_lands_on_exact_rendered_row` timing 偶发失败，
  重跑通过（不触及 `tools/pack`，与本次改动无关）。

## 后续

- 交互式 Ctrl+C 冒烟未执行（自动化会话无法发送 SIGINT），中断路径由
  `test_keyboard_interrupt_maps_to_exit_130` 覆盖；真实翻译时的 TTY 进度条
  形态待人工目验一次。
