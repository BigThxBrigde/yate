# plan-b — 键弦常量 + 两套 keymap + vim 分派前消费 + AC4 守卫（wave-1）

父文档：[overview.md](overview.md)。输入：F1/F2/F3/F4；设计决策 D1。
本计划不依赖 plan-a（运行时等价断言只比较两套表内的动作名字符串，不执行动作）。

## 目标与非目标

- 目标：三个键弦常量进 `yate/keymaps/keys.py`（L0）；vsc/vim 两套
  `build_bindings()` 只引用常量新增三行绑定；vim 在模式分派前消费 alt-* raw 键
  （三态一致 + 清半途 chord）；落地 `test_jumplist_keys_are_shared_and_identical`
  守卫（AST + 运行时，对齐 hover/macro 守卫形态）。
- 非目标：动作注册（plan-c 在 actions.py 接线）；任何流程/组件代码。

## 独占文件清单

- `yate/keymaps/keys.py`
- `yate/keymaps/vsc.py`
- `yate/keymaps/vim.py`
- `tests/test_architecture.py`
- `tests/test_marks_keys.py`（新建）

## 具体修改（定位到行号）

### 1. `yate/keymaps/keys.py`：共享常量（插在 `MACRO_CONTROL_KEYS` 块 L173-176 之后）

```python
#: Shared jump-list / marks keys for both built-in keymaps (issue IKUOCI).
#: alt+arrow reaches the keymap as modified-CSI bytes -- keyproto.key_codec
#: maps Textual's "alt+left"/"alt+right" event names to exactly these
#: sequences (vsc move_line_up precedent) -- so the constants hold the raw
#: CSI form; parse_key would produce the meta-prefix form ("\x1b\x1b[D")
#: which no terminal sends.  key_name() renders both via KEY_ALIASES as
#: "<alt-left>" / "<alt-right>" in help and which-key surfaces.
JUMPLIST_BACK_KEY: str = "\x1b[1;3D"
JUMPLIST_FORWARD_KEY: str = "\x1b[1;3C"
#: Marks overlay key (alt+m); parse_key's meta-prefix form IS the bytes a
#: terminal sends for alt plus a letter (MACRO_CONTROL_KEYS precedent).
MARKS_OVERLAY_KEY: str = parse_key("<alt-m>")
```

要点：`MARKS_OVERLAY_KEY` 必须在 `parse_key`（L108）定义之后做模块级求值
（L173 先例）；注释全 ASCII。禁止把 `<alt-left>` 等记法字符串当绑定键
（parse_key 会产出错误字节，F1）。

### 2. `yate/keymaps/vsc.py`：表行 + 导入

- L13 的 macro 常量导入扩展为
  `from yate.keymaps.keys import (JUMPLIST_BACK_KEY, JUMPLIST_FORWARD_KEY,
  MARKS_OVERLAY_KEY, MACRO_PLAY_KEY, ...)`（保持既有排序习惯）。
- `build_bindings`（L42-132）末尾、`]`（L132）之前追加三行（`_raw` 为既有
  helper L27-32；category 用 `NAV`，与 move_line_up/down 同组，which-key 自动
  分组展示，F13）：

```python
    _raw(JUMPLIST_BACK_KEY, "jump_back", "Jump back in jump history", "NAV"),
    _raw(JUMPLIST_FORWARD_KEY, "jump_forward", "Jump forward in jump history", "NAV"),
    _raw(MARKS_OVERLAY_KEY, "marks_overlay", "Open the marks overview", "NAV"),
```

`_raw` 生成的 `key_label` 经 `key_name()` 反查 KEY_ALIASES 显示 `<alt-left>`/
`<alt-right>`/`<alt-m>`（F2），which-key 与 f1 帮助自动出现（AC7 的自动面）。

### 3. `yate/keymaps/vim.py`：表行 + 分派前消费

- L41 的 keys 导入追加三个常量。
- `build_bindings`（L147-243）表尾（L242 之后）追加同样三行（vim 侧
  `KeyBinding` 直构形态，category 同样 `NAV`，动作名与 vsc 完全一致）。
- 模块级（`_FUNCTION_KEYS` L82 附近）新增：

```python
_NAVIGATION_KEYS: frozenset[str] = frozenset(
    {JUMPLIST_BACK_KEY, JUMPLIST_FORWARD_KEY, MARKS_OVERLAY_KEY}
)
```

- `handle_key`（L248-276）：在 `_FUNCTION_KEYS` 分支（L262-271）之后、模式
  分派（L272+）之前插入分支，形态对齐 F-keys 先例：

```python
        if key in _NAVIGATION_KEYS:
            self._clear_pending()
            binding = self.lookup(key)
            if binding is not None:
                self.dispatch(binding, ctx)
                return True
```

alt-* 是 raw 键，须在三态（NORMAL/INSERT/VISUAL）分派前消费（issue 硬性
要求），`_clear_pending()` 丢弃半途 operator（如先按 `d` 再按 alt-left）。

### 4. `tests/test_architecture.py`：AC4 守卫（插在
`test_macro_keys_are_shared_and_identical` L1653-1706 之后）

`test_jumplist_keys_are_shared_and_identical`，对齐 macro 守卫三段形态：

1. **AST 段**：读 `yate/keymaps/vsc.py` 与 `yate/keymaps/vim.py` 源码取
   `build_bindings` 函数体 AST；断言两侧 `Name` 节点都引用
   `{JUMPLIST_BACK_KEY, JUMPLIST_FORWARD_KEY, MARKS_OVERLAY_KEY}` 全集；
   断言两侧函数体内**无**这些字符串字面量：`<alt-left>`、`<alt-right>`、
   `<alt-m>`、`\x1b[1;3D`、`\x1b[1;3C`、`\x1bm`（记法与 raw 双形态都禁——
   防止"绕过常量直接写 raw 字节"漂移）。
2. **运行时段**：分别构造 `build_keymap_set("vsc")`/`build_keymap_set("vim")`
   （或直接 `build_bindings()`），断言三个常量 raw 键在两套表中解析到
   **同一动作名**：`jump_back` / `jump_forward` / `marks_overlay`，且
   `key_label` 渲染为 `<alt-left>`/`<alt-right>`/`<alt-m>`。
3. 断言 keys.py 模块级确有这三个常量（AST，防手滑删常量）。

### 5. `tests/test_marks_keys.py`（新建）

fixture：`ActionContext` 用 stub `EditorSession` + stub `KeyUi`
（`execute_action` 记录动作名并返回 True，形态对齐既有 keymap 测试）。

| 用例 | 前置/操作/断言 |
|---|---|
| `test_vim_alt_keys_consumed_in_all_three_modes` | 分别把 `VimKeymap.mode` 置 NORMAL/INSERT/VISUAL → `handle_key(ctx, JUMPLIST_BACK_KEY)` 等三个键 → 返回 True 且 ui 记录到对应动作名（9 组断言，三态行为一致） |
| `test_vim_alt_key_clears_pending_chord` | 先 `handle_key(ctx, "d")`（armed operator）→ `handle_key(ctx, JUMPLIST_BACK_KEY)` → 返回 True、动作已派发、`pending` 为空（不残留 op） |
| `test_vim_unrelated_keys_unaffected` | 分派前消费分支只吃三个键：`handle_key(ctx, "x")` 在 NORMAL 下仍走原路径（ui 记录动作名来自表，而不是误入新分支） |
| `test_vsc_and_vim_resolve_same_actions_for_same_raw_keys` | 两套 `build_bindings()` 对三个 raw 常量各得同一动作名（与架构守卫运行时段互补，作为独立可跑的键位回归） |
| `test_key_labels_render_alt_notation` | 三行绑定的 `key_label` 分别为 `<alt-left>` / `<alt-right>` / `<alt-m>`（帮助/which-key 显示一致性，AC7 前提） |

## 验证方案与验收命令

- 验证目标：AC4（两套表同键弦同动作 + 常量来源 keys.py，含负向演练——执行时
  手工把一侧常量改回字面量确认守卫失败后还原，仓库惯例）；三态一致
  （issue"vim 侧 alt-* 为 raw 键，须在模式分派前消费"）。
- 负向演练记录要求：守卫用例需经历"单侧改字面量 → 失败 → 还原 → 通过"一次，
  在子计划验收记录中留痕。

```powershell
.venv\Scripts\python.exe -m pytest tests/test_marks_keys.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps/ tests/test_marks_keys.py tests/test_architecture.py
```

- 通过判定：三条命令退出码 0；`test_architecture.py` 用例数 41 → 42。

## 风险与回滚

- 风险1：`\x1bm` 与 Esc 序列歧义（用户连按 Esc+m 被合并为 alt+m）→ Textual
  输入解析的既有行为，与其它两字节 alt 绑定同性质，可接受；如实测异常，
  回退方案是换 `<alt-.>` 级别未占用键（keys.py 常量单点改）。
- 风险2：vim `_index` 冲突：alt 键从未登记（issue 已核对全仓未绑定），且表行
  与分派前消费分支都走 `lookup`，双路径一致；`test_marks_keys.py` 注册断言兜底。
- 风险3：which-key/hover 面板展示漂移 → 数据驱动（F13），`key_label` 用例
  锁定显示形态。
- 回滚：`git checkout -- yate/keymaps/keys.py yate/keymaps/vsc.py
  yate/keymaps/vim.py tests/test_architecture.py` + 删除
  `tests/test_marks_keys.py`；不触碰其它文件。
