# SP1 — `ctrl+/` 全平台修复 + help 显示修复

> 前置：无（首个可执行子计划）
> 预估：30min　|　独占文件：`yate/editor_view/keys.py`、`yate/keymaps/base.py`、`tests/test_app_textual.py`、`tests/test_key_notation.py`

## 目标

1. `\x1f`（ctrl+/ 与 ctrl+_ 共用的 C0 字节，Textual 命名 `ctrl+underscore`）能映射回 raw `\x1f`，
   使 vsc/vim 双键位的 `toggle_keymap`（`vsc.py:102`、`vim.py:113` 的 raw 绑定）在所有 legacy 终端生效；
2. `key_name("\x1f")` 返回 `<ctrl-/>`，消除 help 面板乱码。

## 实施步骤

### 步骤 1.1　`_CTRL_PUNCT` 补条目

文件 `yate/editor_view/keys.py`，第 12-14 行（当前）：

```python
# Ctrl+punctuation raw bytes. Ctrl+/ is 0x1F (the vsc keymap's keymap
# toggle); without this entry Textual's "ctrl+/" could never reach it.
_CTRL_PUNCT = {"[": 0x1B, "\\": 0x1C, "]": 0x1D, "/": 0x1F}
```

改为：

```python
# Ctrl+punctuation raw bytes. Ctrl+/ is 0x1F (the vsc keymap's keymap
# toggle); without these entries it could never reach it -- legacy
# terminals deliver \x1f as Textual's "ctrl+underscore", kitty CSI-u
# ones as "ctrl+slash", so both spellings must map to the same byte.
_CTRL_PUNCT = {"[": 0x1B, "\\": 0x1C, "]": 0x1D, "/": 0x1F, "underscore": 0x1F}
```

### 步骤 1.2　`KEY_ALIASES` 补显示别名

文件 `yate/keymaps/base.py`，第 83-84 行（dict 尾部，`"\x1b[Z": "shift-tab",` 之后）追加一行：

```python
    "\x1f": "ctrl-/",
```

（使 `key_name("\x1f")`（L128-131）返回 `<ctrl-/>`。）

### 步骤 1.3　测试断言

- `tests/test_app_textual.py` 的 `test_ctrl_and_alt`（L70，现有 L74 `ctrl+/` 断言旁）追加：
  ```python
  assert textual_key_to_raw("ctrl+underscore") == "\x1f"
  ```
- `tests/test_key_notation.py`：任选邻近 `key_name` 断言的用例追加：
  ```python
  assert key_name("\x1f") == "<ctrl-/>"
  ```

## 测试（完成后立即执行，全绿才可提交）

```powershell
d:\Programming\yate\.venv\Scripts\python.exe -m pytest tests\test_app_textual.py tests\test_key_notation.py tests\test_keymap_set.py tests\test_vim_keymap.py -q
d:\Programming\yate\.venv\Scripts\python.exe -m pyright yate tests
```

## 验收标准

- [ ] 新增 2 条断言通过；既有 `textual_key_to_raw("ctrl+/") == "\x1f"`（L74）不回归（两个名字并存是有意设计）；
- [ ] pyright 0 诊断；
- [ ] 冒烟（可选）：`python -m yate` 中按 `ctrl+/` 在 vim/vsc 间切换成功（conhost 与 WT 行为一致）。

## 回滚

单 commit revert 即可；两张表均为纯查表项，无状态、无迁移。
