# plan-a：editor_view 拆分子模块单元测试（wave-1）

## 输入

- `yate/editor_view/cells.py`（133 行，`__all__` 全公开纯函数）
- `yate/editor_view/welcome.py`（128 行，`welcome_rows` / `render_welcome_row`）
- `yate/editor_view/theme_files.py`（102 行，`load_theme_file` / `load_theme_paths`）
- `yate/editor_view/highlighting.py`（416 行，`HighlightProbe` / `HighlightMixin`）
- `tests/conftest.py`（isolated_home autouse）

## 独占文件清单（只新建这 4 个，不动其它任何文件）

- `tests/test_cells.py`
- `tests/test_welcome.py`
- `tests/test_theme_files.py`
- `tests/test_highlighting.py`

统一头部：模块 docstring（英文）、`from __future__ import annotations`、
绝对导入（`from yate.editor_view.cells import ...`）。测试注释全英文
（misc-rules §四）。

## 一、tests/test_cells.py

参照实现：cells.py:31-133。无 fixture 需要（纯函数 + lru_cache 只读）。

| 用例 | 行为点 | 断言（arrange/act→expect） |
|---|---|---|
| `test_cell_width_combining_mark_is_zero` | combining mark 占 0 cell | `cell_width("́") == 0`（U+0301） |
| `test_cell_width_wide_cjk_is_two` | East-Asian W/F 占 2 | `cell_width("中") == 2` |
| `test_cell_width_tab_counts_one` | `\t` 在宽度口径计 1 | `cell_width("\t") == 1` |
| `test_cell_width_ascii_is_one` | 常规字符 1 | `cell_width("a") == 1` |
| `test_cell_len_mixed_string_counts_display_cells` | 混排求和 | `cell_len("a中b") == 4`；`cell_len("a\tb") == 3` |
| `test_truncate_to_cells_stops_before_overflowing_wide_char` | 宽字符放不下即截断 | `truncate_to_cells("a中", 2) == "a"` |
| `test_truncate_to_cells_zero_limit_returns_empty` | `max_cells<=0` 边界 | `truncate_to_cells("abc", 0) == ""` |
| `test_char_to_cell_expands_tab_to_next_stop` | tab 推到下一 stop | `char_to_cell("\tx", 1) == 4`（默认 tab_width=4） |
| `test_cell_to_char_maps_back_from_cell_column` | cell→char 逆映射 | `cell_to_char("ab中cd", 4) == 2`；`cell_to_char("ab", 99) == 2`（超出→行尾） |
| `test_cell_offsets_matches_char_to_cell_prefix` | 前缀表一致性 | 对 `"a\t中b"`：每个 `offsets[i] == char_to_cell(line, i)`，`len(offsets) == len(line)+1` |
| `test_expand_char_doubles_wide_glyph_into_two_cells` | 宽字符展开占 2 cell | `cells: list[str] = []; expand_char("中", cells, 4)` → `cells == ["中", ""]` |
| `test_expand_char_attaches_combining_mark_to_previous_cell` | 0 宽附着前格 | 先 `expand_char("a", ...)` 再 `expand_char("́", ...)` → `cells == ["á"]`（组合后单格） |
| `test_expand_char_tab_advances_to_next_stop` | tab 展开补空格 | `cells=["ab"]; expand_char("\t", cells, 4)` → `cells == ["a","b"," "," "]` |

验收命令：

```text
.venv\Scripts\python.exe -m pytest tests/test_cells.py -q
.venv\Scripts\python.exe -m pyright tests/test_cells.py
```

## 二、tests/test_welcome.py

参照实现：welcome.py:39-128。fixture：`t = theme.active()`（只读，不改全局）；
`cache: dict[tuple[str, bool], list[_WelcomeRow]] = {}` 由用例自建。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_welcome_rows_cache_hits_same_object_for_same_key` | 缓存命中返回同一对象 | 同 key 二次调用 `welcome_rows(t, False, cache) is` 首次返回值，且 `len(cache) == 1` |
| `test_welcome_rows_rebuilds_when_cache_key_changes` | key 变化重建 | `(t.name, False)` 与 `(t.name, True)` 各占一缓存项，两个 list 不是同一对象 |
| `test_welcome_rows_vim_hint_present_only_in_vim_mode` | `:` 提示仅在 vim_keys | vim_keys=True 时某 row 含 `("  " + ":".ljust(15), ...)` 片段文本 `":"`；False 时任何 row 文本不含 `":  "` 前缀提示（以 `":" == hint kbd` 精确判定） |
| `test_welcome_rows_banner_rows_are_centered_flags_true` | banner 6 行居中标记 | rows[1..6] 每行恰 1 个 tuple 且 `tuple[3] is True`、文本宽度一致（ljust 后等于 banner_w） |
| `test_render_welcome_row_strip_width_equals_view_width` | Strip 补齐到 view_w | `render_welcome_row(0, view_w=80, gutter_w=4, t, False, cache)` 的 `Strip` 段总 cell 宽 == 80（`strip.cell_length`） |
| `test_render_welcome_row_pads_gutter_prefix` | gutter 空白前缀 | 第 0 行（空 row）返回 Strip 的首段文本 == `" " * 4` |

验收命令：

```text
.venv\Scripts\python.exe -m pytest tests/test_welcome.py -q
.venv\Scripts\python.exe -m pyright tests/test_welcome.py
```

## 三、tests/test_theme_files.py

参照实现：theme_files.py:38-101。**全局污染控制**：`register_theme` 写进程全局
`themes.THEMES`（themes.py:384，dict），autouse fixture：

```python
@pytest.fixture(autouse=True)
def restore_themes(monkeypatch: pytest.MonkeyPatch) -> None:
    from yate.editor_view import themes as themes_mod
    monkeypatch.setattr(themes_mod, "THEMES", dict(themes_mod.THEMES))
```

（`_loaded_theme_files` 进程缓存用 monkeypatch.setattr 换空 set。）

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_load_theme_file_registers_theme_from_user_py` | 用户 py 注册主题 | 写 tmp 文件 `register_theme(Theme(name="rt_probe", ...))`（字段抄 `yate/resources/theme_examples/ayu_theme.example` 的构造形态）→ `load_theme_file(path) is None` 且 `"rt_probe" in themes.THEMES` |
| `test_load_theme_file_broken_file_returns_error_string` | 坏文件不抛 | `SyntaxError("x =")` 文件 → 返回串以 `"SyntaxError"` 开头 |
| `test_load_theme_file_second_load_is_noop` | resolved 路径幂等 | 成功 load 后再次 `load_theme_file` 返回 None；把文件改成会抛错的版本再 load 仍返回 None（走 `_loaded_theme_files` 短路） |
| `test_load_theme_paths_directory_skips_underscore_files` | `_` 前缀跳过 | 目录放 `_bad.py`（抛错）+ `good.py` → errors 为空、good 已注册 |
| `test_load_theme_paths_missing_path_is_silent` | 缺失路径静默 | `load_theme_paths([tmp/"nope"], errors)` → errors == [] |
| `test_load_theme_paths_collects_errors_with_path_prefix` | 错误带路径前缀 | 目录含坏文件 → `errors == [f"{path}: SyntaxError: ..."]` 形态（前缀断言） |

验收命令：

```text
.venv\Scripts\python.exe -m pytest tests/test_theme_files.py -q
.venv\Scripts\python.exe -m pyright tests/test_theme_files.py
```

## 四、tests/test_highlighting.py

参照实现：highlighting.py:31-361。**host 设计**：`HighlightMixin` 声明的协作面是
`doc` / `is_mounted` / `refresh` / `set_timer` / `run_worker`（highlighting.py:96-139
前 5 个是 host 需提供的协议位，其中 refresh/set_timer/run_worker 由 Textual
widget 自带）。执行者先读 highlighting.py:49-140 确认 `_tokenize_with_states`
对 host 的属性依赖（如 filetype/spec 来源），host 用最小组合类：

```python
class _HostWidget(HighlightMixin, Static):
    def __init__(self, document: Document, **kwargs: Any) -> None: ...
    @property
    def doc(self) -> Document: ...
```

挂载在 `app.run_test()` pilot 内（Textual 上下文，set_timer/worker 可用）。
**风险与降级**：若 mixin 依赖 EditorView 专有属性无法轻量宿主，则把该文件
降级为经 `EditorView` 构造的集成用例（沿用 `test_app_render.py` 的 app 装配
模式）——不改产品代码，偏离记录于本文档"执行记录"节。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_tokens_for_tokenizes_rows_with_active_spec` | 公开 tokens_for 产出 token | host doc 内容 `x = "hi"` → `tokens_for(0)` 非空且含字符串 kind 的 token（kind 以 `Token`/SYNTAX_KINDS 常量判定） |
| `test_tokens_for_second_call_returns_cached_list` | 缓存命中 | 二次 `tokens_for(0) is` 首次返回对象 |
| `test_tokens_for_after_buffer_edit_rebuilds_row` | 编辑后失效重建 | 修改 doc buffer 该行文本后（触发 `_rebuild_tokens_on_edit` 路径）`tokens_for(0)` 返回**新** list 且反映新文本 |
| `test_tokens_for_row_beyond_document_returns_empty` | 越界行 | `tokens_for(999) == []` |
| `test_highlight_probe_reports_state_consistent_with_doc` | probe 公开面 | `highlight_probe()` 返回 `HighlightProbe`，其行数字段 == doc 行数（字段名执行者按 HighlightProbe dataclass 定义落定） |
| `test_tokens_for_empty_document_returns_empty` | 空 doc 边界 | doc 0 行 → `tokens_for(0) == []` |

验收命令：

```text
.venv\Scripts\python.exe -m pytest tests/test_highlighting.py -q
.venv\Scripts\python.exe -m pyright tests/test_highlighting.py
```

## 风险与回滚

- highlighting host 不可轻量化 → 降级为 EditorView 集成用例（上文）；
  回滚 = 删除 `tests/test_highlighting.py`。
- welcome.py 依赖 `yate.__version__`（import 副作用）→ 已由 conftest 隔离，
  无用户目录触碰。
- 全部为新建测试文件，回滚零产品影响。

## 执行记录

（执行后回填：实际用例数、pytest/pyright 退出码、偏离与依据。）
