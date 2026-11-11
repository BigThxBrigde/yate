# 子计划 b：键弦常量与双表绑定（wave-1，主代理亲改）

> 唯一规范来源：本文件 + `../overview.md` §2.2/§2.3 +
> `../macro-record-replay-plan.md` §4。

## 1. 输入

- `keys.py:57-60`（`HOVER_DOC_KEY` 单常量先例）；`vim.py:146-236` /
  `vsc.py:26-128`（build_bindings）；`vim.py:92-95`（RESERVED_KEYS）；
  `vim.py:776-782`（NORMAL count 累加）、`:1256-1266`（`_take_count`）；
  `base.py:196-201`（handle_key 契约）。
- 守卫模板：`tests/test_hover_key_binding.py:28-105` 全套 +
  `tests/test_architecture.py:1611-1646`（hover 守卫）。

## 2. 独占文件

`yate/keymaps/keys.py`、`yate/keymaps/base.py`、`yate/keymaps/vim.py`、
`yate/keymaps/vsc.py`、新建 `tests/test_macro_key_binding.py`。

## 3. 开工前置探针（冲突扫描，记录进报告）

确认 `q` / `@` 在两表现有绑定与 vim RESERVED_KEYS / motions 中零占用：
`.venv\Scripts\python.exe -c` 探针遍历 `VimKeymap().build_bindings()` /
`VscKeymap().build_bindings()` 打印 raw=="q"/"@" 冲突项；若被占用，
停下回填总纲 §六换键（issue 允许方案定稿），不得静默覆盖。

## 4. 具体修改

1. `keys.py`：按总纲 §2.2 加两常量（`#:` 注释）。
2. `base.py`：`Keymap.take_pending_count()` 默认返回 1（总纲 §2.3）。
3. `vim.py`：`build_bindings()` 内以 `parse_key(MACRO_RECORD_KEY)` /
   `parse_key(MACRO_PLAY_KEY)` 各加一条 `KeyBinding`，动作名
   `macro_record_prefix` / `macro_play_prefix`（category 与描述对齐邻近
   条目风格）；覆写 `take_pending_count()`（读 `count_str` → 清零）。
4. `vsc.py`：`_k(MACRO_RECORD_KEY, "macro_record_prefix", …)` /
   `_k(MACRO_PLAY_KEY, "macro_play_prefix", …)` 两行。
5. 两表**禁止**出现 `"q"` / `"@"` 字面量（守卫断言）。

## 5. 守卫用例（复刻 hover 全套，对齐 `tests/test_hover_key_binding.py`）

| 用例 | 断言 |
| --- | --- |
| `test_macro_keys_are_shared_constants` | 常量值与形态；两表 AST：`build_bindings` 体内引用 `MACRO_RECORD_KEY`/`MACRO_PLAY_KEY` Name 且无 `"q"`/`"@"` 字面量（AC3） |
| `test_macro_keys_resolve_identically_in_both_keymaps` | 运行时：两表 `lookup(parse_key(常量))` 同动作名（record/play prefix） |
| `test_macro_keys_are_not_reserved_or_conflicting` | 冲突扫描干净（对齐 hover 用例 :45-67 形态） |
| `test_vim_take_pending_count_consumes_and_clears` | `3@a` 形态：count_str="3" → take 返回 3 且清零；缺省 → 1 |

## 6. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_key_binding.py tests/test_vim_keymap.py tests/test_editor_core.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 7. 风险与回滚

vim.py 1528 行（SIZE_EXEMPT 登记）仅加 4-6 行；两表绑定行可单独 revert；
若 q/@ 冲突，换键只动 `keys.py` 常量 + 本文件 §3 探针重跑。
