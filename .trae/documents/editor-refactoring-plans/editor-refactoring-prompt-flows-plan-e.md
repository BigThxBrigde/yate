# plan_E — 查找/替换/跳转流程外移（Wave 5，收尾）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
prompt 驱动的查找 / 实时高亮 / 替换 / 行跳转外移到 `yate/prompt_flows.py`；
收尾波含覆盖率门禁与文档回填。

## 改动文件（独占）
- 新建 `yate/prompt_flows.py`
- `yate/editor.py`
- `tests/test_architecture.py`（R11 登记）

## 输入（外移方法，editor.py 行号）
| 方法 | 行号 | 去向 |
|---|---|---|
| `find_prompt` | 959-967 | `PromptFlows.find_prompt` |
| `_live_search` / `_submit_search` | 969-977 | 同名私有 |
| `find_next` | 980-992 | `PromptFlows.find_next` |
| `replace_prompt` / `_replace_find_step` / `_do_replace` | 994-1022 | 同名 |
| `goto_prompt` / `goto_line_command` / `goto_line` | 1024-1064 | 同名 |

## 实施
1. `PromptFlows` 构造参数：`session: EditorSession`、`panes: PaneManager`、
   `prompt: PromptBar`、`message: Callable[[str, str], None]`、
   `readonly_notice: Callable[[], None]`（= Editor._readonly_notice，单一来源）。
   无 app 依赖——全部同步操作，纯会话/视图交互。
2. editor.py 薄委托（KeyUi 与 actions.py:132-135、commands 的调用面不变）：
   `find_prompt` / `find_next` / `replace_prompt` / `goto_prompt` /
   `goto_line_command`（run_command `:42` 裸数字分支 editor.py:1263 调用）/
   `goto_line`，各 2-4 行。
   `_live_search` / `_submit_search` / `_replace_find_step` / `_do_replace` 内部化。
   `page()` 不动（视图滚动，非 prompt 流程）；`_cancel_prompt` 不动（4 行，挂接点）。
3. `UI_FROZEN_FILES["prompt_flows.py"] = {"yate.editor_view",
   "yate.editor_view.commandline"}`。
4. 收尾：`python -m pytest tests/ -q --cov=yate --cov-branch --cov-report=term-missing
   --cov-fail-under=75`（memory 规则：评审含覆盖率）；README 总纲回填各波真实数字
   （editor.py 前后行数、pyright/pytest/smoke/coverage 实测、偏离记录）。

## 输出 / 验收
统一门禁全 0 + coverage ≥ 75；`/`、`?`、`n`/`N`、`:s`、Ctrl+G、`:42` 行为不变
（tests 零 diff）；smoke 5 场景绿。

## 回滚
单提交 revert。
