# multi-cursor plan-b：vim/vsc 键位接入多光标（L0 keymaps）

> wave-2。依赖：plan-a（buffer 多光标 API 已合入）。总纲见 `overview.md`。
> 输入：总纲 §四.1/§四.5/§四.6（键链路、ALT+C 可用性、状态机接入点）、
> §五状态机图。

## 一、输入

- `yate/keymaps/base.py`：`handle_key`（:327-332）、`handle_unbound`
  （:334-347，modeless 打印字符唯一汇聚点）、`parse_key`（:95-146）。
- `yate/keymaps/vim.py`（1117 行，豁免名单内）：`handle_key` 路由
  （:194-222）、`_handle_insert`（:255-287）、`_handle_normal`
  （:419-640）、`_clear_pending`（:239-244）、绑定表（:116-189）。
- `yate/keymaps/vsc.py`：绑定表（:36-118），`<esc>`→`clear_selection`
  （:79）。
- plan-a 的 buffer API：`add_cursor_at` / `add_cursor_below` /
  `clear_extra_cursors` / `has_extra_cursors` / `insert_at_points` /
  `delete_at_points` / `delete_forward_at_points` / `extra_cursors`。

## 二、独占文件清单

只改以下文件，不要动其它任何文件：

| 文件 | 改动 |
|---|---|
| `yate/keymaps/base.py` | `handle_unbound` 多点分支 |
| `yate/keymaps/vim.py` | ALT+C、ESC 清点、INSERT 多点分支、清点规则 |
| `yate/keymaps/vsc.py` | `<alt-c>` 绑定 |
| `tests/test_vim_keymap.py` | 多光标 vim 用例组 |
| `tests/test_vsc_keymap.py` | `<alt-c>` / 多点 unbound 用例 |
| `tests/test_key_notation.py` | `<alt-c>` 解析钉子 |

## 三、具体修改

### 3.1 base.py — `handle_unbound` 多点分支（:334-347）

打印字符分支前插多点卫语句：

```python
if ctx.buffer.has_extra_cursors() and len(key) == 1 and key.isprintable():
    ctx.buffer.insert_at_points(key)
    return True
```

- 位置在 `type_char` 分支之前；未激活多光标时行为逐字节不变（现有多点
  零回归）。
- `"\x1bc"`（ALT+C）长度 2 不会误入该分支；vsc 的 ALT+C 走绑定表（§3.3）。

### 3.2 vim.py

1. **绑定表**（`build_bindings` :116-189，EDT 段）加 help 条目（只进
   帮助/`_index`，不参与 `_handle_normal` 分支；`category="general"`
   默认值不会被 `_extension_binding`（:224-237，仅 category≠"general"）
   误触发）：

   ```python
   KeyBinding(parse_key("<alt-c>"), "add cursor below",
       "Add a cursor on the next row (multi-cursor)", EDT),
   ```

2. **`_handle_normal`（:419-640）新增分支**——放在 ESC 分支（:423-425）
   之后、pending_register（:432）之前：

   ```python
   if key == "\x1bc":  # ALT+C: add a cursor below the bottom-most point
       buf.clear_selection()
       buf.add_cursor_below()
       return True
   ```

   （`add_cursor_below` 返回值在末行是 False 的 no-op 已由 plan-a 保证；
   静默即可，不打消息——保持 NORMAL 的安静风格。）

3. **ESC 分支扩展**（:423-425）：

   ```python
   if key == "\x1b":
       self._clear_pending()
       buf.clear_extra_cursors()
       return True
   ```

4. **清点规则**（总纲 §二非目标）：NORMAL 下除 motion（:496-499）、
   ALT+C（新增分支）、插入入口（:565-593）、ESC 外，任何命令先把附加点
   清掉再执行。实现：在 `x`（:517）、`p`/`P`（:524/:530）、`u`（:536）、
   ctrl-r（:540）、`J`（:544）、四个翻页键（:548-563）、operator 分支
   `d/y/c`（:489-494）、`v`/`V`（:595-606）、`o`/`O`（:583-592）、
   `> / <`（:501-511）、`/ ? : n N`（:608-627）各分支入口统一调用
   `buf.clear_extra_cursors()`。**不要**在 `_handle_normal` 开头一刀切
   ——motion 与插入入口必须保点。为避免 13 处重复，加私有 helper：

   ```python
   def _exit_multi(self, buf: TextBuffer) -> None:
       """Leave multi-cursor mode before a single-cursor NORMAL command."""
       buf.clear_extra_cursors()
   ```

5. **`_handle_insert`（:255-287）多点分支**：
   - ESC（:257-261）：在 `self.mode = VimMode.NORMAL` 前加
     `ctx.buffer.clear_extra_cursors()`（INSERT 的 ESC 同时清点）。
   - `\r`（:262-264）：多点时改走 `ctx.buffer.insert_at_points("\n")`
     （无逐行缩进——已知限制）；单点时保持 `ui.execute_action("newline")`
     不变。
   - `\x7f`（:268-270）：多点时 `ctx.buffer.delete_at_points()`；
     单点时保持 action。
   - 打印字符（:283-286）：多点时 `ctx.buffer.insert_at_points(key)`；
     单点时保持 `type_char`（配对语义不丢）。
   - `\t`（:265-267）、`\x1b[3~`、ctrl-w、ctrl-u、`_ARROW`（:280-282）：
     保持单点原语义，但入口处清点（方向键移动主光标属"原操作"，其余
     编辑命令退出多光标——见清点规则）。
   - 多点判断统一用 `ctx.buffer.has_extra_cursors()` 卫语句，分支内部
     不再嵌套 if。

6. **`drop_visual`（:396-404）**：补
   `buf.clear_extra_cursors()`？——**不加**：drop_visual 无 buffer 参数
   且多光标与 visual 互斥（`v`/`V` 分支已按清点规则先清点），鼠标点击
   进 `_handle_normal` 前的 `drop_visual` 不清点（普通鼠标点击的清点由
   plan-c 的 mouse_flows 负责，vim 模式不接鼠标多光标）。**此处不改**，
   仅在 docstring 注明多光标清点归 mouse_flows（vsc）与 ESC 分支。

### 3.3 vsc.py — `<alt-c>` 绑定（绑定表 SEL 段 :78 附近）

```python
_k("<alt-c>", "add_cursor_below", "Add a cursor on the next row (multi-cursor)", SEL),
```

- `parse_key("<alt-c>")` = `"\x1bc"`（`base.py:128-129` alt 分支），与
  总纲 §四.5 的可达性结论一致；action `add_cursor_below` 由 plan-c 注册
  （`yate/actions.py`）。**本子计划合入后、plan-c 合入前存在一个键指向
  未注册 action 的窗口**——`Keymap.dispatch`（`base.py:308-325`）会把
  unknown action 报 `unknown action: add_cursor_below` 并消费按键。
  处理：本子计划与 plan-c 同在 wave-2，收尾验收在两计划都合入后跑；
  任务书注明此顺序依赖。
- `<esc>` → `clear_selection`（:79）的多点清点由 plan-c 在 action 实现
  （`clear_selection` action 加 `clear_extra_cursors()`），vsc 表不动。

## 四、测试用例

### tests/test_key_notation.py（1 例）

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_parse_alt_c_produces_esc_prefixed_byte` | — | `parse_key("<alt-c>")` | 返回 `"\x1bc"`（与 `event_to_raw("alt+c")` 的产物一致，链路对齐） |

### tests/test_vim_keymap.py（新增用例组）

fixture：既有 vim keymap 测试的 `make_keymap`/`ctx` 构造（沿用文件内
现状）；buffer 文本 `"alpha beta\ngamma delta\nepsilon zeta"`。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_alt_c_adds_cursor_below_in_normal_mode` | NORMAL，光标 (0,2) | `handle_key(ctx, "\x1bc")` | `buf.extra_cursors == [(1, 2)]`；`vim.mode` 仍 NORMAL |
| `test_alt_c_twice_adds_second_cursor_below_last` | 已按一次 ALT+C | 再按一次 | `buf.extra_cursors == [(1, 2), (2, 2)]` |
| `test_esc_clears_extra_cursors_in_normal_mode` | 两个附加点 | `handle_key(ctx, "\x1b")` | `buf.extra_cursors == []`；pending 状态清空 |
| `test_motion_keeps_extra_cursors_and_moves_primary_only` | 附加点 [(1,2)] | `handle_key(ctx, "l")` | `cursor == (0, 3)`；`extra_cursors == [(1, 2)]`（点不动、模式保活） |
| `test_insert_entry_keeps_multi_cursor_active` | 附加点 [(1,2)] | `handle_key(ctx, "i")` | `vim.mode == VimMode.INSERT`；`extra_cursors == [(1, 2)]` |
| `test_insert_printable_inserts_at_all_points` | 附加点 [(1,2)]，已 `i` 进 INSERT | `handle_key(ctx, "X")` | `lines[0][:3] == "alX"`（光标 (0,2) 后插 X → "alXpha beta"）；`lines[1][:4] == "gamX"`；一次 undo 复原 |
| `test_insert_backspace_deletes_at_all_points` | 同上进 INSERT | `handle_key(ctx, "\x7f")` | 主点 (0,2) 删 'l'、(1,2) 删 'm'；一次 undo 复原 |
| `test_insert_enter_inserts_newline_at_all_points` | 三点进 INSERT | `handle_key(ctx, "\r")` | `line_count == 6`；一次 undo 复原 |
| `test_insert_esc_clears_cursors_and_returns_normal` | 多点 INSERT | `handle_key(ctx, "\x1b")` | `vim.mode == VimMode.NORMAL`；`extra_cursors == []`；`cursor` 前移一格（原 ESC 语义 :259 保留） |
| `test_operator_exits_multi_cursor_before_running` | 附加点 [(1,2)] | `handle_key(ctx, "d")` 再 `"d"` | `dd` 执行后 `extra_cursors == []`（先清点再删行） |
| `test_visual_entry_exits_multi_cursor` | 附加点 [(1,2)] | `handle_key(ctx, "v")` | `vim.mode == VimMode.VISUAL`；`extra_cursors == []`；anchor=cursor（原语义） |
| `test_alt_c_in_insert_mode_is_swallowed` | INSERT 模式 | `handle_key(ctx, "\x1bc")` | 不加点、不插字；仍 INSERT（`_handle_insert` 尾部 `return True` 原语义） |

### tests/test_vsc_keymap.py（2 例）

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_alt_c_binding_resolves_add_cursor_below` | vsc keymap | `keymap.lookup(parse_key("<alt-c>"))` | binding 存在且 `binding.action == "add_cursor_below"`、category 为 SEL |
| `test_handle_unbound_printable_multi_cursor_inserts_at_points` | `ActionContext` + buffer 双点（不依赖 actions 注册） | `keymap.handle_key(ctx, "X")` | 两点各插 X；单点时走 `type_char`（对照断言：无附加点时配对括号补全仍生效——`handle_key(ctx, "(")` 后 `lines[0]` 含 `"()"`） |

### 验证命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_vsc_keymap.py tests/test_key_notation.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pyright yate/keymaps/ tests/test_vim_keymap.py tests/test_vsc_keymap.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| 清点规则漏分支（某个 NORMAL 命令在多点下产生未定义行为） | §3.2.4 列全 13 个命令入口逐一调用 `_exit_multi`；用例覆盖 operator/visual 两条代表路径 |
| `_handle_insert` 分支重排破坏单点回归（auto-indent、bracket、skip） | 多点分支全部以 `has_extra_cursors()` 卫语句前置，单点路径字节不变；`tests/test_vim_keymap.py` 既有 ~200 例回归 |
| `<alt-c>` 先于 plan-c 合入导致 unknown action 窗口 | wave-2 收尾统一验收（plan-c 合入后跑全量）；任务书注明合入顺序 |
| vim.py 膨胀 | 预估 +~70 行 → ~1190 行，豁免名单内；plan-e 回填 |
| 回滚 | 独立 commit `feat(vim): multi-cursor entry via ALT+C`（vsc 绑定行并入同 commit 或 `feat(keymaps)`，按 `git-commit-message.md`）；`git revert` 净回 |

## 六、验收标准

1. §四 全部新用例通过；三个测试文件 `-q` 退出码 0；
2. `pytest tests/ -q` 全绿（vim/vsc 既有回归无破坏）；
3. pyright `yate/keymaps/` 零诊断；
4. `tests/test_architecture.py` 28 passed（R4：keymaps 未新增
   editor_view 导入）。
