# 无名称缓冲区 LSP 接入子计划 a — `:enew` 必须拒绝参数（wave-1）

主计划：[`../enew-args-lsp-attach-plan.md`](../enew-args-lsp-attach-plan.md) · 波次表：
[`overview.md`](overview.md)。从 `../yate-enew-args-lsp-attach` worktree 根目录运行。

## 1. 输入

- issue 记录 [`../enew-args-lsp-attach-issue-notes.md`](../enew-args-lsp-attach-issue-notes.md) §1 问题 1、§3 预期行为。
- 主计划 §2 事实 F1/F2/F3/F17、§3 决策 A、§6 风险表。
- 规则：`.trae/rules/python-coding-style.md`、`.trae/rules/architecture-boundaries.md`
  §五 检查清单（R5/R7：`commands.py` 是 L3 内置表），
  `.trae/rules/misc-rules.md` §四（英文注释/docstring）。

## 2. 独占文件

- `yate/commands.py`（写）
- `tests/test_cmd_enew.py`（新建文件）

所有其它文件只读。不改动 `yate/resources/**`、`tests/test_architecture.py`、
`tools/**`、`.trae/**`。

## 3. 具体改动

### 3.1 `yate/commands.py:344-345` — `_enew`

当前：

```python
def _enew(args: str) -> None:
    editor.document_flows.new_buffer()
```

替换为（措辞必须完全一致，测试会对其逐字断言）：

```python
def _enew(args: str) -> None:
    if args.strip():
        editor.message(
            "usage: :enew takes no arguments; use :e FILE to open/create a "
            "named buffer or :saveas FILE to name this buffer",
            kind="warn",
        )
        return
    editor.document_flows.new_buffer()
```

理由：`editor.message(..., kind="warn")` 是命令表的用法错误
通道（F2）；不抛异常、不新建缓冲区、不改变状态。**不要**在这里调用
`_strip_quotes` —— 带引号的 `"test.py"` 仍然是参数，必须被
拒绝。关键字/导入/类型改动：无；`args` 保持 `str`，返回值保持
`None`。

### 3.2 `yate/commands.py:383` — 注册描述

当前：

```python
reg("enew", _enew, "open a new empty buffer")
```

替换为：

```python
reg("enew", _enew, "open a new empty buffer (no arguments)")
```

不添加 `arg_completer`：零参数命令没有可补全的内容。不要新增命令或别名。

### 3.3 `tests/test_cmd_enew.py` — 新建无头测试模块

沿用 `tests/test_cmd_cd.py:61-115` 的无头模式：一个带有
`document_flows` 和 `message(text, kind)` 的桩编辑器、一个真实的
`CommandRegistry`，以及 `register_commands(registry, cast(Any, editor))`。使用
`from __future__ import annotations`、完整类型标注、英文的模块/类/函数
docstring、绝对导入、不用相对导入、不用 `TYPE_CHECKING`、不用裸 `except`。

fixture 结构（实现细节，名称可调整但行为固定）：

- `_RecordingFlows.new_buffer()` 向 `self.new_buffer_calls` 追加一个标记；
- `_EnrewEditor.message(text: str, kind: str = "info")` 向 `notes`
  追加 `(text, kind)`；
- `_fixture()` 返回 `"enew"` 的注册项以及两个记录器。

精确的测试用例（`test_<behavior>_<condition>_<expected>`）：

| # | 测试名称 | 安排/执行 | 断言（具体值） |
|---|---|---|---|
| 1 | `test_enew_without_arguments_creates_one_unnamed_buffer` | 全新 fixture；`entry.fn("")` | `new_buffer_calls == 1`；`notes == []` |
| 2 | `test_enew_with_whitespace_only_arguments_creates_one_unnamed_buffer` | 全新 fixture；`entry.fn("   \t ")` | `new_buffer_calls == 1`；`notes == []` |
| 3 | `test_enew_with_filename_warns_and_creates_no_buffer` | 全新 fixture；`entry.fn("test.py")` | `new_buffer_calls == 0`；`notes == [("usage: :enew takes no arguments; use :e FILE to open/create a named buffer or :saveas FILE to name this buffer", "warn")]` |
| 4 | `test_enew_with_quoted_filename_warns_and_creates_no_buffer` | 全新 fixture；`entry.fn('"test.py"')` | `new_buffer_calls == 0`；与 #3 相同的单条警告记录 |
| 5 | `test_enew_registration_description_states_no_arguments` | 全新 fixture；`entry.description` | `"no arguments" in entry.description` 且 `"open a new empty buffer" in entry.description` |

负向演练（守卫语义所必需）：在改动产品代码之前，先用当前的 `_enew` 临时运行
用例 #3 并确认其失败（`new_buffer_calls == 1`、`notes == []`）；然后应用改动并确认转绿。
将两次结果记录到 §6。

## 4. 产出

- 不再静默丢弃 `:enew` 参数；零参数 `:enew` 的行为不变。
- 5 个无头测试固定守卫行为、精确的告警文本以及注册描述。
- 无新增导入边，未改变架构守卫面。

## 5. 验收命令（可复制粘贴，从 worktree 根目录执行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cmd_enew.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py tests/test_set_options.py tests/test_action_table.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/commands.py').read_text(encoding='utf-8').splitlines()))"
```

通过标准：所有 pytest/pyright 命令退出码为 0；pyright 报告 0 错误；
架构测试套件仍为 37 通过；`yate/commands.py` 保持低于 800 行
（§三.7）。如果 `-n auto` 报告失败，用 `-n 1` 重跑该测试，并在宣布成功前修复
真实的时序假设。

## 6. 执行记录（填入实测数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| 负向演练（改动前的用例 #3） | 如预期失败：`new_buffer_calls == 1`、`notes == []`（旧 `_enew` 忽略了参数） | 1（负向演练） |
| `pytest tests/test_cmd_enew.py -q` | 5 通过 | 0 |
| `pytest ... -n auto`（cmd_cd / set_options / action_table 回归） | 全部通过；主代理独立的 wave-1 复跑：143 通过 | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 通过 | 0 |
| `yate/commands.py` 行数 | 617 | 0 |

偏差：无。wave-3 随后追加了一个多参数回归用例
（`test_enew_with_multiple_arguments_warns_and_creates_no_buffer`），作为评审
第 1 轮的次要项；两个文件都保持在子计划 a 的独占清单内，最终第 7 步门禁记录为 3422 通过。

## 7. 风险与回滚

- 风险：外部键位映射/扩展调用 `:enew something` 时，现在看到的是警告而不是新缓冲区。缓解措施：随产品发布的绑定中没有这样的调用
  （F16/F17）；该警告是非破坏性的，并指向 `:e FILE` /
  `:saveas FILE`。
- 风险：精确字符串断言使测试与措辞耦合。接受：该措辞是本次修复对用户可见的契约；有意修改措辞时必须同时更新代码和 §3.3 中的表格。
- 回滚：`git revert` 本波次的提交即可恢复 `yate/commands.py` 并删除 `tests/test_cmd_enew.py`；没有其它子计划依赖这个新文件。
