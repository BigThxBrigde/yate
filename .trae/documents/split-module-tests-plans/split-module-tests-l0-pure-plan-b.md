# plan-b：L0 纯函数与配置解析单元测试（wave-1）

## 输入

- `yate/editor_term/palette.py`（47 行：`palette_color` / `ANSI_16_RGB`）
- `yate/editor_term/keys.py`（74 行：`key_to_terminal`）
- `yate/editor_lsp/parsing.py`（258 行：`__all__` 7 个 `_` 前缀纯函数）
- `yate/yaterc_options.py`（669 行：`__all__` 12 个 `_extract_*` / `_parse_*` /
  `_require_*` 纯函数）
- `tests/conftest.py`（isolated_home autouse；`make_action_context` 模式）

## 独占文件清单（只新建这 4 个）

- `tests/test_term_palette.py`
- `tests/test_term_keys.py`
- `tests/test_lsp_parsing.py`
- `tests/test_yaterc_options.py`

私有面取舍：`parsing.py` / `yaterc_options.py` 的 `_` 前缀函数全部列入
`__all__`（模块 docstring 明示 wave-a private-registry precedent，是经
`editor_lsp.manager` / `yate.yaterc` re-export 的事实包内公共 API），直接
import 测试**不算白盒**。两个文件沿用存量惯例加文件级注释与豁免：

```python
# _-prefixed names are the module's __all__ surface (wave-a private-registry
# precedent, same as tests/test_diagnostics.py).
# pyright: reportPrivateUsage=false
```

## 一、tests/test_term_palette.py

参照实现：palette.py:14-47。无 fixture。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_palette_color_base_16_reads_ansi_table` | 0-15 查表 | `palette_color(0) == ANSI_16_RGB[0]`；`palette_color(5) == ANSI_16_RGB[5]` |
| `test_palette_color_color_cube_matches_level_formula` | 676 段公式 | `palette_color(16 + 36*5 + 6*3 + 4) == (215, 175, 135)`（levels[5], levels[3], levels[4]） |
| `test_palette_color_color_cube_black_is_exact_zero` | n==0 特判 | `palette_color(16) == (0, 0, 0)` |
| `test_palette_color_grayscale_ramp_starts_at_8_step_10` | 232-255 灰度 | `palette_color(232) == (8, 8, 8)`；`palette_color(255) == (238, 238, 238)` |
| `test_palette_color_clamps_out_of_range_indices` | 越界钳制 | `palette_color(-5) == palette_color(0)`；`palette_color(999) == palette_color(255)` |

## 二、tests/test_term_keys.py

参照实现：keys.py:16-74（`_NAMED` 表 + `keyproto.legacy.modified_key_sequence`
共享编解码）。无 fixture。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_key_to_terminal_printable_with_character_returns_character` | 单字符 + character | `key_to_terminal("a", "a") == "a"` |
| `test_key_to_terminal_printable_without_character_returns_key` | 单字符无 character | `key_to_terminal("a", None) == "a"` |
| `test_key_to_terminal_combo_ignores_character_argument` | 组合键不走 character 分支 | `key_to_terminal("ctrl+a", "a") == "\x01"` |
| `test_key_to_terminal_named_keys_resolve_table` | `_NAMED` 表 | enter→`"\r"`、escape→`"\x1b"`、f5→`"\x1b[15~"`、up→`"\x1b[A"`、backspace→`"\x7f"` |
| `test_key_to_terminal_ctrl_letter_maps_control_code` | ctrl 字母 | `key_to_terminal("ctrl+c", None) == "\x03"` |
| `test_key_to_terminal_ctrl_symbol_maps_special_code` | ctrl 符号 | ctrl+space→`"\x00"`、ctrl+`[`→`"\x1b"`、ctrl+`?`→`"\x7f"` |
| `test_key_to_terminal_alt_prefixes_named_and_plain_keys` | alt 前缀 | `key_to_terminal("alt+b", None) == "\x1bb"`；`key_to_terminal("alt+up", None) == "\x1b\x1b[A"` |
| `test_key_to_terminal_ctrl_shift_letter_matches_ctrl_code` | ctrl+shift 字母 | `key_to_terminal("ctrl+shift+a", None) == "\x01"` |
| `test_key_to_terminal_modified_arrows_match_keyproto_codec` | 修饰键经 keyproto 共享 | `key_to_terminal("ctrl+left", None)` 非 None 且以 `"\x1b"` 开头（一致性目标：与 `keyproto.legacy.modified_key_sequence(frozenset({"ctrl"}), "left")` 相等，不 pin 具体字节） |
| `test_key_to_terminal_unmapped_modifier_combo_returns_none` | 未映射组合 | `key_to_terminal("meta+x", None) is None` |
| `test_key_to_terminal_unknown_named_key_returns_none` | 未知命名键 | `key_to_terminal("capslock", None) is None` |

## 三、tests/test_lsp_parsing.py

参照实现：parsing.py:43-258。Document 构造沿用 conftest 模式：
`Document(None, EditorSession(YateConfig()).make_buffer(text))`（conftest.py:121-123
同款）。共用 fixture `doc`：三行内容，第 2 行含非 BMP 字符（`"a😀b"`）验证
UTF-16 往返。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_to_utf16_ascii_line_is_passthrough` | ASCII 快路径 | `_to_utf16("abc", 2) == 2` |
| `test_to_utf16_counts_non_bmp_as_two_units` | 非 BMP 计 2 | `_to_utf16("a😀b", 2) == 4`（a=1、emoji=2） |
| `test_from_utf16_maps_units_back_to_code_points` | 逆映射 | `_from_utf16("a😀b", 4) == 2`；`_from_utf16("a😀b", 0) == 0` |
| `test_from_utf16_units_beyond_line_returns_line_length` | 超界钳到行尾 | `_from_utf16("ab", 99) == 2` |
| `test_unwrap_completion_plain_list_returns_items_no_defaults` | list 形态 | `_unwrap_completion([{"label": "x"}])` → `([{"label": "x"}], {})`；非 dict 元素被滤除 |
| `test_unwrap_completion_dict_uses_items_and_item_defaults` | dict 形态 | `{"items": [...], "itemDefaults": {...}}` → 二者透传；缺 items → `([], {})` |
| `test_unwrap_completion_garbage_returns_empty_pair` | 垃圾输入 | `_unwrap_completion(42) == ([], {})` |
| `test_range_from_insert_key_wins_over_outer_range` | insert 优先 | `{"range": {...}, "insert": {"start": {…}, "end": {…}}}` → insert 的四元组 |
| `test_range_from_malformed_returns_none` | 畸形 | 非 dict / 缺 start / 缺 end → None |
| `test_range_to_buffer_cols_converts_utf16_columns` | 服务端列→buffer 列 | doc 行 `"a😀b"`，rng `(0, 2, 0, 4)` → `(0, 1, 0, 2)`；越界行号 → 空串（列 0） |
| `test_parse_completion_item_label_becomes_insert_text` | 最小 item | `{"label": "foo"}` → `Completion(label="foo", insert_text="foo", range=prefix 四元组)`（prefix 由 row/col/prefix_start_col 决定） |
| `test_parse_completion_item_text_edit_dict_uses_new_text_and_range` | textEdit dict | newText+range（UTF-16）→ insert_text==newText 且 range 落 buffer 列 |
| `test_parse_completion_item_snippet_falls_back_to_label` | format 2 防占位符 | `insertTextFormat=2` + textEdit dict → insert_text == label（不插 `$1`） |
| `test_parse_completion_item_missing_label_returns_none` | label 缺失 | label 非 str/空 → None |

## 四、tests/test_yaterc_options.py

参照实现：yaterc_options.py:59 起。共用 fixture：`config = YateConfig()` +
`rc_dir = tmp_path`（autouse isolated_home 已隔离真实 home）。namespace 即
`dict[str, Any]`（模拟 exec 后命名空间）。执行者写用例前先读
yaterc_options.py:120-669 的各函数签名与错误消息格式（docstring 有逐函数说明）。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_extract_path_list_resolves_relative_entries_against_rc_dir` | 相对路径基于 rc_dir | rc_dir 下建 `ext/a.py`，namespace `{"extensions": ["ext/a.py"]}` → `config.extension_paths == [(rc_dir/"ext"/"a.py").resolve()]` |
| `test_extract_path_list_expands_user_home_entry` | `~` 展开 | `{"extensions": ["~/exts"]}`（isolated home 下建目录）→ 解析到 `Path.home()/"exts"` |
| `test_extract_path_list_missing_entry_appends_error_and_keeps_default` | 缺失路径报错不抛 | 不存在路径 → `config.errors` 含 `"path does not exist"` 且 `config.extension_paths` 不含它 |
| `test_extract_path_list_rejects_non_string_entry` | 非 str 条目 | `{"extensions": [1]}` → errors 含 `must be non-empty strings` |
| `test_extract_path_list_rejects_scalar_value` | 标量形态 | `{"extensions": 5}` → errors 含 `must be a path string or a list` |
| `test_extract_path_list_dedupes_resolved_entries` | 去重 | 同一文件两种写法（相对+绝对）→ target 只 1 项 |
| `test_extract_disabled_extensions_accumulates_names` | disabled_extensions | `{"disabled_extensions": ["x", "y"]}` → `config.disabled_extensions == ["x", "y"]`（执行者按 `_extract_disabled_extensions` 实际落点断言） |
| `test_extract_options_assigns_known_scalar_and_reports_unknown` | 标量表 | namespace 含一个 KNOWN_OPTIONS 内标量（如 `tab_width=8`）→ `config.tab_width == 8`；未知键 → errors 非空且 config 保留默认 |
| `test_extract_screen_saver_maps_keys_and_reports_unknown` | screen_saver dict | 合法键（如 `idle_seconds`）落 `config.screen_saver`；未知键 → errors 含键名 |
| `test_extract_file_preview_maps_keys_and_reports_unknown` | file_preview dict | 同上形态 |
| `test_extract_language_servers_builds_spec_and_reports_malformed` | declarative lsp 表 | 合法条目 → `config.language_servers` 含 `LanguageServerSpec`；坏条目 → errors 非空、其余条目仍生效 |
| `test_parse_journey_fraction_accepts_fraction_rejects_rest` | 分数解析 | 合法小数 → 原值；越界/非数 → 错误路径返回值（执行者按实现断言 None/0 与 errors） |

验收命令（4 文件逐个 + 一把全跑）：

```text
.venv\Scripts\python.exe -m pytest tests/test_term_palette.py tests/test_term_keys.py tests/test_lsp_parsing.py tests/test_yaterc_options.py -q
.venv\Scripts\python.exe -m pyright tests/test_term_palette.py tests/test_term_keys.py tests/test_lsp_parsing.py tests/test_yaterc_options.py
```

回归范围（新用例触碰的既有面）：

```text
.venv\Scripts\python.exe -m pytest tests/test_terminal_emulator.py tests/test_diagnostics.py tests/test_config.py -q
```

## 风险与回滚

- `_extract_options` 的标量键名以 `yate/config.py::KNOWN_OPTIONS` 为准（表驱动
  A8），断言写具体值前先查该表——用例保持"表内任一标量 + 未知键"两条腿，
  键名选 `tab_width`（KNOWN_OPTIONS 稳定成员）。
- parsing/yaterc_options 用例不改产品代码；回滚 = 删除对应测试文件。
- yaterc_options 测试只写 tmp_path 内文件，不触碰真实 `~/.yate`（conftest 已隔离）。

## 执行记录

2026-10-12 wave-1 执行完毕（执行者：plan-executor 子代理；复验：主代理）。

- 实际产物：4 个新测试文件共 **42 用例**（test_term_palette 5 /
  test_term_keys 11 / test_lsp_parsing 14 / test_yaterc_options 12）。
- 验收：`pytest` 4 文件 42 passed（exit 0）；`pyright` 0 诊断（exit 0）；
  `test_architecture.py` 全绿（exit 0）；回归范围
  `test_terminal_emulator + test_diagnostics + test_config` 209 passed。
  主代理复跑新文件同结果。
- 偏离（执行前 `python -c` 探针逐项实测计划断言值，发现 6 处数值/行为
  笔误，断言按实测落笔、行为点全部保留）：
  1. palette 色立方体：`palette_color(16+36*5+6*3+4)` 实测
     `(255, 175, 215)`（计划正文数值笔误，其括号注释与实现自洽）；
  2. `_to_utf16("a😀b", 2)` 实测 `== 3`（1+2，计划写 4）；
  3. `_from_utf16` 互逆对为 `("a😀b", 3) == 2`（计划写 4→2）；
  4. 越界钳制只发生在非 ASCII 行：ASCII 快路径透传返回原值
     （`_from_utf16("ab", 99) == 99`），改用 `_from_utf16("a😀b", 99) == 3`
     断言钳制；
  5. `_range_to_buffer_cols(0,2,0,4)` 实测 `→ (0,2,0,3)`（units 落在
     surrogate 中间，语义为"越过该 unit 的字符边界"）；改用边界对齐输入
     `(1,1,1,3) → (1,1,1,2)` 保留计划期望语义；
  6. `alt+up` 实测 `"\x1b[1;3A"`——实现先查 `keyproto.legacy.
     modified_key_sequence` 共享表（keys.py:47），alt+arrow 走 CSI 1;3A
     而非双 ESC 前缀。
- 行为点替换一处：`_extract_options` 实测不报未知键（只遍历
  `KNOWN_OPTIONS` 取交集，yaterc_options.py:420），"未知键 → errors" 用例
  改为"越界值 → errors"（`test_extract_options_assigns_known_scalar_and_
  rejects_bad_value`），未知键报告在 dict 形态两条用例中按原计划覆盖。
- 提交：commit `6de3954`。
