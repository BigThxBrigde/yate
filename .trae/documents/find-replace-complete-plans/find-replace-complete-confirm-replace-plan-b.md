# plan-b：逐个确认替换（wave-2）

> 总纲见 [overview.md](overview.md)。波次：wave-2（与 plan-c 并行，文件
> 不重叠；无对 plan-a 的数据依赖——只消费 search.py 既有
> `replace_current` / `replace_all` / `next`）。

## 一、输入

- 总纲 D1/D2/D2b、F1/F4/F5/F6/F7；
- [prompt_flows.py](../../yate/flows/prompt_flows.py)（145 行）：
  `_do_replace`（L94-103）现状是两步 prompt 后直接 `replace_all`；
- [commandline.py](../../yate/editor_view/commandline.py)：`PREFIXES`
  （L36-50）、`CommandInput.on_key`（L153-188）、`PromptBar.activate`
  （L267-305）、`_show_message`（L317-326，会隐藏 input——进度展示只能
  走 `input.placeholder`）。

## 二、独占改动文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor_view/commandline.py` | 修改（`PREFIXES` +1 行；`activate` 加 `on_key` 参数；`CommandInput.on_key` 加钩子；清理点 +1 行，增量 ≤30 行） |
| `yate/flows/prompt_flows.py` | 修改（`_do_replace` 改造 + 确认循环私有方法，增量 ≤120 行） |
| `tests/test_app_find.py` | 追加 pilot 用例（测试文件；本波独占，与 plan-c 的 `test_app_find_replace.py` 不重叠） |

## 三、具体修改

### 3.1 `yate/editor_view/commandline.py`

1. `PREFIXES`（L36-50）追加一行：

```python
"replace_confirm": ("Replace:", "accent2"),
```

2. `PromptBar.__init__`（L199-225）回调字段区追加：

```python
#: Single-key confirm hook (confirm-style prompts); receives the raw
#: event.key, returns True when the key was consumed.
self._on_key: Callable[[str], bool] | None = None
```

3. `activate`（L267-305）签名追加关键字参数
   `on_key: Callable[[str], bool] | None = None`，函数体在
   `self._on_changed = on_changed` 旁加 `self._on_key = on_key`。
   docstring 补一句：*"on_key* (confirm prompts) intercepts every key
   before the Input sees it; returning True consumes the key."*

4. `CommandInput.on_key`（L153-188）**方法体最前面**插入钩子（先于
   escape/ctrl+c 分支，使 confirm 态能拦截 escape）：

```python
hook = self.bar._on_key
if hook is not None and hook(event.key):
    event.stop()
    event.prevent_default()
    return
```

   未传 `on_key`（既有全部 prompt 模式）时钩子为 None，行为零变化（R10：
   消费才 stop，不无条件拦截）。

5. 清理点：`_show_message`（L317-326）与 `cancel`（L344-349）中与
   `self._on_submit = None` 并列处加 `self._on_key = None`（消息/退出
   即卸钩子，防悬挂回调）。

### 3.2 `yate/flows/prompt_flows.py`

1. `_do_replace`（L94-103）改造为确认循环启动（read_only guard 与
   0 匹配 warn 语义保留）：

```python
def _do_replace(self, find: str, replacement: str) -> None:
    if self.session.buffer.read_only:
        self._readonly_notice()
        return
    matches = self.session.search.update(find, self.session.buffer)
    if not matches:
        self._message(f"no matches for {find!r}", "warn")
        return
    self._replacement = replacement
    self._confirm_total = len(matches)
    self._confirm_done = 0
    self.prompt.activate(
        "replace_confirm",
        placeholder="",
        on_key=self._confirm_step,
    )
    self._advance()
```

   新增私有状态字段（`__init__` 或类属性声明）：
   `self._replacement: str = ""`、`self._confirm_total: int = 0`、
   `self._confirm_done: int = 0`。

2. 新增私有方法（语义归 flow，组件不知 y/n/a/q 含义）：

```python
def _confirm_step(self, key: str) -> bool:
    """One keypress of the per-match confirm loop; True = consumed."""
    if key == "y":
        if self.session.search.replace_current(
            self.session.buffer, self._replacement
        ):
            self._confirm_done += 1
        self._finish_or_advance()
        return True
    if key == "n":
        self._confirm_done += 1  # skip the match _advance selected
        self._finish_or_advance()
        return True
    if key == "a":
        count = self.session.search.replace_all(
            self.session.buffer, self._replacement
        )
        self._end_confirm(
            f"replaced {count} occurrence(s) of "
            f"{self.session.search.query!r}"
        )
        return True
    if key in ("q", "escape", "ctrl+c"):
        self._end_confirm("replace cancelled")
        return True
    if key in ("enter",) or (len(key) == 1 and key.isprintable()):
        return True  # swallow stray keys; the Input stays empty
    return False  # up/down/history etc. fall through

def _advance(self) -> None:
    """Select the next unconfirmed match and show loop progress."""
    match = self.session.search.next(self.session.buffer, forward=True)
    if match is None:
        self._end_confirm("no further matches")
        return
    self.prompt.input.placeholder = (
        f"[{self._confirm_done + 1}/{self._confirm_total}] replace "
        f"{self.session.search.query!r} with {self._replacement!r}? "
        "(y)es (n)o (a)ll (q)uit"
    )

def _finish_or_advance(self) -> None:
    """Stop after the fixed total, else move to the next match."""
    if self._confirm_done >= self._confirm_total:
        self._end_confirm(
            f"replaced {self._confirm_done} occurrence(s) of "
            f"{self.session.search.query!r}"
        )
        return
    self._advance()

def _end_confirm(self, text: str) -> None:
    """Leave the confirm loop; write() hides the prompt and restores focus."""
    self._confirm_total = 0
    self._confirm_done = 0
    self._replacement = ""
    self._message(text, "ok" if "replaced" in text else "info")
```

**终止性论证**（总纲 D2 / R2，写入实现 docstring）：

- 每步 y/n 使 `done += 1`，`total` 进入循环后不变 → `_finish_or_advance`
  在 `total` 步内必命中 `done >= total`（**先判后走**）；
- y 替换后 `replace_current` 内部 `update()` 重算、`index = -1`，光标停
  在替换文本末尾；替换文本内部（含跨界拼出的）自匹配 start 恒
  `< cursor`，`_nearest_index` 的 forward 分支只选 `>= (row, col)`，故
  `_advance` 的 `next` 永不选中替换文本内部匹配（plan-a 的
  `test_engine_next_skips_text_inside_replaced_match` 锚定）；
  matches 耗尽时 `next` 返回 None → `_end_confirm` 兜底退出。

注意：进度经 `prompt.input.placeholder` 展示（F7：`write()` 会隐藏
input，循环中不可用）；终止时 `_end_confirm` 才走 `_message`（其内部
`prompt.write(...)` 自动回 idle 并恢复焦点，复用既有路径）。

### 3.3 `n` 分支的游标语义说明

`_advance` 已用 `search.next(forward=True)` 选中待确认匹配（cursor/
anchor 由 engine 设置）；`n` 仅计数后再次 `_advance`——`next` 的后续
调用走 `(index + 1) % len`，自然跳过刚展示的匹配（F4）。

## 四、输出

- F4 两步输入后进入 `[i/N]` 确认循环，y/n/a/q/esc 全路径可用；
- 既有 prompt 模式（find/goto/shell/…）零行为变化（钩子默认 None）。

## 五、测试用例（pilot，追加 `tests/test_app_find.py`；范式 F23）

| 用例 | 前置与操作 | 断言 |
|---|---|---|
| `test_f4_confirm_loop_replace_yes_consumes_matches` | tmp_path 文档 `"cat cat cat"`；`press f4 → "cat" → enter → "dog" → enter → y → y → y` | `buffer.get_text() == "dog dog dog"`；`prompt_bar.active_mode is None`；`message_text` 含 `replaced 3` |
| `test_f4_confirm_loop_skip_keeps_match` | `"cat cat"`；全输入后 `n → q` | buffer 不变（`"cat cat"`）；无 replaced 消息 |
| `test_f4_confirm_loop_all_replaces_everything` | `"cat cat cat"`；`y` 一次后 `a` | buffer `"dog dog dog"`；消息含 replaced |
| `test_f4_confirm_loop_quits_early` | `"cat cat cat"`；`y → q` | 仅第 1 处被替换；prompt 回 idle |
| `test_f4_confirm_loop_escape_cancels` | 同上但 `escape` | 与 q 等价（钩子拦截 escape 走 `_end_confirm`） |
| `test_f4_confirm_loop_read_only_refuses` | read-only 文档（`:set readonly` 路径） | 两步输入后 buffer 不变、`readonly_notice` 文案出现、未进 confirm |
| `test_f4_confirm_loop_regex_backreference_replaces` | `"a@x"`；find `(\w+)@x`、repl `\1`、`y` | buffer `"a"`（regex 对单匹配 sub 的既有语义保持） |
| `test_confirm_mode_swallows_other_printable_keys` | 进入 confirm 后 `press "z"` | `prompt_bar.input.value == ""` 且 buffer 不变（R10 不漏键） |
| `test_f4_no_matches_reports_warn_and_skips_loop` | 无匹配文本；全输入 | `message_text` 含 `no matches`；`active_mode is None`（未进 confirm） |
| `test_f4_confirm_loop_replacement_self_match_terminates` | `"xfoo"`；find `foo`、repl `foofoo`、`y → y`（自匹配场景） | 循环在 `total` 步内终止（pilot 挂起即失败）；buffer 符合逐步语义 |

## 六、验收命令（该波结束应全绿）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_find.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/
```

通过判定：三条退出码 0；`tests/ -q` 全量回归无新红（既有 prompt 测试零变化）。

## 七、风险与回滚

- R2 死循环：D2 先判后走 + plan-a engine 测试 + 自匹配终止用例三重防线；
- R8 键序竞态：钩子在 `on_key` 最前，消费即 `stop + prevent_default`，
  Input 不产生 `Changed`；
- 回滚：单提交 revert 即还原为直接 `replace_all`；commandline.py 的
  钩子为纯增量（默认 None），回滚 prompt_flows.py 后即使残留也无行为影响。
