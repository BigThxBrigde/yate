# wave-2 / plan-f：`type_char.language` 与 PTY 占位类 `owner`

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #12-14。
> 所属波次 `wave-2: plan_d ∥ plan_e ∥ plan_f`，文件与同波另两个子计划互不重叠。

## 输入

- AST 事实：`yate/editor_core/buffer.py:856` 的 `language` 与
  `yate/editor_term/pty_proc.py:754` / `:759` 的 `owner` 在函数体内均无 `Load` 引用。
- `type_char` docstring 自述「*language* is the seam ... V1 reads it not at all」；
  函数体为括号自动补全文本算法，不消费 `language`。
- `_UnixPty` / `_ConPty` 是「Platform-specific placeholder types for static
  analysis」，函数体只 `raise PtyProcessError(...)`。
- 调用点清单：
  - `language=` 关键字实参 3 处：`yate/keymaps/base.py:223`、
    `yate/keymaps/vim.py:498`、`tests/test_input_assist.py:981`；
    另有 7 处仅位置参数调用 `type_char(ch)`，不受影响。
  - `owner` 位置实参 1 处：`yate/editor_term/pty_proc.py:71`
    `self._impl = _UnixPty(self) if os.name == "posix" else _ConPty(self)`。

## 独占文件清单（只改这些文件）

- `yate/editor_core/buffer.py`
- `yate/keymaps/base.py`
- `yate/keymaps/vim.py`
- `tests/test_input_assist.py`
- `yate/editor_term/pty_proc.py`

## 具体修改

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/editor_core/buffer.py:856` | `def type_char(self, ch: str, *, language: str = "plaintext") -> None:` | `def type_char(self, ch: str) -> None:` |
| `yate/editor_core/buffer.py:873-877` | docstring「*language* is the seam ... no keymap change needed.」 | 删除整段 |
| `yate/keymaps/base.py:223` | `...type_char(ch, language=...)` | `...type_char(ch)` |
| `yate/keymaps/vim.py:498` | `...type_char(ch, language=...)` | `...type_char(ch)` |
| `tests/test_input_assist.py:981` | `...type_char(ch, language=...)` | `...type_char(ch)` |
| `yate/editor_term/pty_proc.py:754` | `def __init__(self, owner: PtyProcess) -> None:` | `def __init__(self) -> None:` |
| `yate/editor_term/pty_proc.py:759` | `def __init__(self, owner: PtyProcess) -> None:` | `def __init__(self) -> None:` |
| `yate/editor_term/pty_proc.py:71` | `_UnixPty(self) if ... else _ConPty(self)` | `_UnixPty() if ... else _ConPty()` |

- `type_char` 的整个函数体（含 `locked` 守卫、选区包裹、括号配对、撤销合并）
  **一行不改**；`PtyProcess` 类本身与 `PtyProcessError` 一行不改。
- 两个占位类签名同步保持一致（同为无参），pyright 在两平台分支下都成立。
- `pty_proc.py` 中 `PtyProcess` 类型仍被其它注解使用，**不得**删除相关导入。
- 若 `keymaps/base.py` / `keymaps/vim.py` 因删 `language=...` 出现未使用局部名，
  不要顺手删除：本子计划只改调用点实参。

## 测试用例与验证方案

不新增用例；既有回归即行为一致证据：

- `tests/test_editor_core.py` / `tests/test_input_assist.py`：括号自动补全、
  引号跳过、撤销单步合并、只读缓冲区守卫，覆盖 `type_char` 全部分支。
- `tests/test_keymaps*.py`（以仓库实际文件名为准）：keymap 打印键路径。
- `tests/test_terminal.py`：PTY 平台占位类与终端 resize 路径。

**验证方案**：局部 pytest 全绿（退出码 0）+ pyright 全仓零诊断（含 `pack/`）+
`git diff` 自查只含签名、实参与 docstring 删除。

## 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py tests/test_input_assist.py tests/test_terminal.py -q --cov-fail-under=0
git diff --check
```

## 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 3 处 `language=` 关键字实参漏改 → `TypeError` | 调用点清单逐处核对 + 局部 pytest + pyright | `git revert` 本波提交 |
| 插件/外部按 `language=` 调用 `type_char` | 该函数是 L0 `TextBuffer` 内部方法，未列入插件手册开放 API；跨仓调用面为 `services/extensions` 门面 14 名 | 同上 |
| 平台占位类签名与真实实现不一致 | 两个分支同时改、调用点同时改；pyright 全仓零诊断 | 同上 |
