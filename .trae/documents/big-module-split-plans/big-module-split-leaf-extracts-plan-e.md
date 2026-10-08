# 波次 e：叶子包提取 words + palette + keys（issue IKK5F7）

## 目标 1：`editor_core/buffer.py`（888）→ `words.py`

- 新增 `yate/editor_core/words.py`（~85 行）：迁出 `_WORD_CHARS`（38）、
  `_is_word`、`next_word_start`、`prev_word_start`、`word_end`、`word_span`
  （46–109）；只依赖 `re`，零 yate 内依赖（L0 叶子保持）。
  独立消费面：`textobjects.py`（5 处）、`keymaps/vim.py`、
  `flows/mouse_flows.py`、`tests/test_editor_core.py` 直接引用这些自由函数。
- `buffer.py`（~822 行，仍 >800 → 维持 A11 单一职责豁免并更新行数）：
  头部新增
  `from yate.editor_core.words import next_word_start, prev_word_start, word_end`
  ——`buffer.py` 内实测有 4 个词函数调用点（`delete_back`→`prev_word_start`
  （:578）、`delete_forward`→`word_end`（:598）、`move_left`→
  `prev_word_start`（:609）、`move_right`→`next_word_start`（:625）），
  非死代码；`word_span` 仅外部消费、缓冲主体不调用。
  **`MAX_UNDO_STEPS`（40–43）属 undo 职责，留在 buffer.py**。
- import 更新（干净做法，不留 re-export）：`editor_core/textobjects.py`、
  `yate/keymaps/vim.py`、`yate/flows/mouse_flows.py`、
  `tests/test_editor_core.py` 改从 `yate.editor_core.words` 导入。

判定依据：`word_span` 与缓冲主体零耦合（不触碰 `_Snapshot`/`_Edit`/
`TextBuffer`），词函数为无状态纯函数、消费面在 textobjects/vim/
mouse_flows（buffer 内仅 4 个运动/删除方法调用），构成 A11 职责块，必须拆。

## 目标 2：`editor_term/emulator.py`（861）→ `palette.py` + `keys.py`

- 新增 `yate/editor_term/palette.py`（~50 行）：`type RGB`（28）、`_ANSI_16`
  （41–47）、`_hex_rgb`（50–52）、`ANSI_16_RGB`（55–56）、`palette_color`
  （59–74）；零项目内依赖。
- 新增 `yate/editor_term/keys.py`（~80 行）：`_NAMED`（105–118）、共享表
  注释（120–123）、`key_to_terminal`（126–168）；依赖
  `yate.keyproto.legacy`（与原方向一致，无环）。
- `emulator.py`（~775 行）：保留 `Cell`、`_char_width`、状态常量、
  `ResponseFn`、`MAX_SCROLLBACK`、`TerminalEmulator` 全类；头部改
  `from .palette import ANSI_16_RGB, RGB, palette_color` 与
  `from .keys import key_to_terminal`。
- `editor_term/__init__.py`：`key_to_terminal` 再导出改自 `.keys`（行数不变）。
- 测试同步：`tests/test_terminal_emulator.py` 的 `ANSI_16_RGB`、
  `palette_color` 改从 `yate.editor_term.palette` import。

判定依据：调色板与按键映射是与 VT 状态机无关的独立职责（输入映射 vs 输出
解析是 docstring 声明的两个对向职责）；类主体（185–861）20+ 方法共享同一组
可变状态，维持 A11 状态机单体豁免。

## 架构守卫

全部为 L0 叶包内部切分，不新增 UI 依赖。

## 规则侧同步

- 行数守卫豁免集合（`tests/test_architecture.py`）移除
  `editor_term/emulator.py`；`editor_core/buffer.py` 保留豁免，
  行数更新为拆分后实测值；
- `.trae/rules/architecture-boundaries.md` §三.7 豁免名单同步：移除
  `editor_term/emulator.py` 条目、更新 `editor_core/buffer.py` 登记行数。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_core/ yate/editor_term/
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py tests/test_terminal_emulator.py tests/test_terminal.py tests/test_vim_keymap.py tests/test_app_mouse.py -q
```

`tests/test_app_mouse.py` 覆盖 `flows/mouse_flows.py` 的 import 更新
（双击选区走 `word_span`，`mouse_flows.py:18` 的导入源改为
`yate.editor_core.words`）。

## 预估

`words.py` ~85；`buffer.py` ~822（豁免）；`palette.py` ~50；`keys.py` ~80；
`emulator.py` ~775。
