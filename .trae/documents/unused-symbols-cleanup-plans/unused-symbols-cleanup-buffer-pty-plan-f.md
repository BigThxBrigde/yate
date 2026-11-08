# wave-2 / plan-f：`type_char.language`（含 PTY 占位类改判）

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #12。
> 所属波次 `wave-2: plan_d ∥ plan_e ∥ plan_f`，文件与同波另两个子计划互不重叠。
> **执行后回填**：原 #13 / #14（PTY 占位类 `owner`）已改判 keep，见 §五。

## 一、输入

- AST 事实：`yate/editor_core/buffer.py:856` 的 `language` 在函数体内无 `Load` 引用。
- `type_char` docstring 自述「*language* is the seam ... V1 reads it not at all」；
  函数体为括号自动补全文本算法，不消费 `language`。
- 调用点清单：`language=` 关键字实参 3 处（`yate/keymaps/base.py:223`、
  `yate/keymaps/vim.py:498`、`tests/test_input_assist.py:981`）；另有 7 处仅位置
  参数调用 `type_char(ch)`，不受影响。

## 二、独占文件清单（实际落地）

- `yate/editor_core/buffer.py`
- `yate/keymaps/base.py`
- `yate/keymaps/vim.py`
- `tests/test_input_assist.py`

`yate/editor_term/pty_proc.py` 已从独占清单移除：其两处 `owner` 形参改判保留，
本子计划不改动该文件（调用点 `pty_proc.py:71` 保持传 `self`）。

## 三、具体修改（已落地）

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/editor_core/buffer.py:856` | `def type_char(self, ch: str, *, language: str = "plaintext") -> None:` | `def type_char(self, ch: str) -> None:` |
| `yate/editor_core/buffer.py:873-877` | docstring「*language* is the seam ... no keymap change needed.」 | 删除整段 |
| `yate/keymaps/base.py:223` | `...type_char(ch, language=...)` | `...type_char(ch)` |
| `yate/keymaps/vim.py:498` | `...type_char(ch, language=...)` | `...type_char(ch)` |
| `tests/test_input_assist.py:981` | `...type_char(ch, language=...)` | `...type_char(ch)` |

- `type_char` 的整个函数体（含 `locked` 守卫、选区包裹、括号配对、撤销合并）
  **一行不改**。
- 若调用点因删 `language=...` 出现未使用局部名，不要顺手删除：本子计划只改
  调用点实参（未使用局部名属另案，登记表已登记）。

## 四、测试用例与验证方案

不新增用例；既有回归即行为一致证据：

- `tests/test_editor_core.py` / `tests/test_input_assist.py`：括号自动补全、
  引号跳过、撤销单步合并、只读缓冲区守卫，覆盖 `type_char` 全部分支。
- `tests/test_keymaps*.py`（以仓库实际文件名为准）：keymap 打印键路径。

**验证方案**：局部 pytest 全绿（退出码 0）+ pyright 全仓零诊断（含 `pack/`）+
`git diff` 自查只含签名、实参与 docstring 删除。主代理复核实测：pyright
`0 errors, 0 warnings`，wave-2 六文件 pytest `350 passed / 1 skipped`。

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py tests/test_input_assist.py tests/test_terminal.py -q
git diff --check
```

## 五、wave-2 实测改判（计划事实错误，已回填）

原计划把 `yate/editor_term/pty_proc.py:754` / `:759` 两个**平台占位类**的 `owner`
判为可删，并计划把 `pty_proc.py:71` 的 `_UnixPty(self) / _ConPty(self)` 改成无参。
执行时实测发现该文件另有两个**真实平台实现类**：

- 第 248 行 `_UnixPty`（POSIX 真实实现）：`__init__(self, owner: PtyProcess)` 消费
  `owner`，`_spawn()` 用 `self._owner.env` / `.argv`；
- 第 419 行 `_ConPty`（NT 真实实现）：同样消费 `owner`；
- 第 754 / 759 行是「Platform-specific placeholder types for static analysis」，
  只在当前平台**不是**该类平台时定义，函数体只 `raise PtyProcessError(...)`。

`pty_proc.py:71` 在运行时解析到的是真实类，删占位类形参与调用点实参后 pyright
报 `reportCallIssue`（`Expected 0 positional arguments`）。按 issue §三「框架固定
签名不可删」与保守口径，**改判 keep 并整体回退 PTY 相关改动**：占位类签名恢复
`(self, owner: PtyProcess)`、调用点保持传 `self`，两行登记到
`framework-fixed-signature:platform-placeholder` 类。回退后 pyright 零诊断。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 3 处 `language=` 关键字实参漏改 → `TypeError` | 调用点清单逐处核对 + 局部 pytest + pyright | `git revert` 本波提交 |
| 插件/外部按 `language=` 调用 `type_char` | 该函数是 L0 `TextBuffer` 内部方法，未列入插件手册开放 API；跨仓调用面为 `services/extensions` 门面 14 名 | 同上 |
| 平台占位类签名与真实实现不一致 | 已整体回退，两处保持一致；pyright 全仓零诊断 | 同上 |
