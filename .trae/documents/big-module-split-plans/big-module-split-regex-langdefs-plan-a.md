# 波次 a：regex_langdefs 抽取 + 行数守卫（issue IKK5F7）

## 目标

1. `yate/editor_syntax/regex_backend.py`（1225 行）拆为：
   - 新增 `yate/editor_syntax/regex_langdefs.py`（~780 行）：`LangSpec`
     dataclass、全部 `_*_KEYWORDS/_TYPES/...` 词表、`_spec` 构造器、
     `_LANGUAGES` / `_NAME_TO_KEY` 注册表、`register_language`、全部内置
     `register_language(...)` 登记（含 `_css_family`）、`lang_for` /
     `resolve_filetype` / `language_name` / `available_filetypes` /
     `format_filetype_candidates`。
   - `regex_backend.py` 瘦身（~490 行）：regex 构建（`_NUMBER_RE` …
     `_code_line_pattern`）+ tokenizer 引擎（`_S_*` 状态、`_emit`、
     `_tokenize_code_line`、`_classify_ident`、`_tokenize_markdown_line`、
     `_tokenize_config_line`、`tokenize_document*`、`tokenize_line`）。
2. 规则侧：`tests/test_architecture.py` 新增
   `test_source_files_within_size_threshold`（遍历 `yate/**.py`，>800 行且不在
   豁免集合即 fail；豁免集合见下方，附 A11 注释）；`.trae/rules/
   architecture-boundaries.md` §三.7 行数校准 + regex_backend 移出名单 +
   新增 `editor_view/theme.py`、`yaterc.py` 豁免登记；§六用例对照表 26→27 条。

## import 方向（无环）

`regex_backend.py → regex_langdefs.py`（单向）；`regex_langdefs.py` 只依赖
stdlib（`dataclasses`）。公开 API 兼容：`regex_backend` 再导出
`LangSpec, available_filetypes, format_filetype_candidates, lang_for,
language_name, register_language, resolve_filetype`（加 `__all__` 供 pyright
识别 re-export 使用），因此 `editor_syntax/__init__.py`、
`ts_backend/languages.py`、`services/extensions.py` 零改动。

## 同步改动

- `tests/test_ts_backend.py`、`tests/test_extension_examples.py`：
  `regex_backend._LANGUAGES` / `_NAME_TO_KEY` 改指 `regex_langdefs`。
- 注释校准：make 登记处注释引用的 `_IDENT_RE`（迁后驻留 regex_backend）改写
  为"tokenizer 的标识符模式"表述。
- 守卫豁免集合（a 波全量，b–f 逐波收缩）：
  `keymaps/vim.py`、`editor.py`、`editor_view/editor.py`、
  `editor_view/diffview.py`、`editor_core/buffer.py`、
  `editor_term/emulator.py`、`editor_lsp/manager.py`、`editor_view/theme.py`、
  `yaterc.py`。

## 验收命令（worktree 内）

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_syntax/
.venv\Scripts\python.exe -m pytest tests/test_syntax_engine.py tests/test_ts_backend.py tests/test_highlight.py tests/test_extension_examples.py tests/test_architecture.py -q
.venv\Scripts\python.exe -c "import yate.editor_syntax as s; print(len(s.available_filetypes()))"
```

## 预估

`regex_langdefs.py` ~780 行；`regex_backend.py` ~490 行。
风险：循环导入（单向已排除）、测试 patch 面已列。
