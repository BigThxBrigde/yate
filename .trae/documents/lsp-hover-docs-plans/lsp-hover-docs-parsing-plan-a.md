# 计划 a — 规范化 `Hover.contents`（wave-1，L0）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)

## 输入

- `yate/editor_lsp/parsing.py:1-50`（模块风格、`__all__`、`_to_utf16`）、`:67-135`（`_unwrap_completion` / `_range_from` 的防御性形状风格）、`:200-230`（`_parse_diagnostics` 的"从不抛错"策略）。
- Issue 简报 §3.4 / AC4 / AC5：`MarkupContent` markdown + plaintext、`MarkedString`、字符串数组、混合数组、`null`、`{}`、空字符串、纯空白、空数组都必须规范化为**显示字符串**或 `""`。

## 独占文件

- `yate/editor_lsp/parsing.py`
- `tests/test_lsp_hover_parsing.py`（新增）

## 具体变更

1. `yate/editor_lsp/parsing.py:32`——用 `parse_hover_contents` 扩展 `__all__`；保持模块的"纯粹、全函数、防御性"契约。
2. 在 `_from_utf16`（`parsing.py:64`）之后添加：

   ```python
   def parse_hover_contents(raw: object) -> str:
       """Normalize an LSP Hover payload into Markdown text ("" when empty)."""
   ```

   数据流：解包 `{"contents": ...}`（为兼容 server 也接受裸 `contents` 载荷）→ `_hover_part(value)` → 用 `"\n\n"` 拼接非空部分 → 仅当 `text.strip()` 非空时返回 `text`，否则返回 `""`。
3. `_hover_part(value: object) -> str`（模块私有，散文式 docstring）：
   - `str` → 字符串本身（不做围栏包裹）。
   - `dict` → `cast(dict[str, object], value)`；若它有字符串类型的 `value` 字段：
     - `language` 是非空字符串（LSP `MarkedString`）→ ```` ```{language}\n{value}\n``` ````，使签名渲染为围栏代码块（与参考截图一致）；
     - 否则（`MarkupContent`，`kind` 为 markdown/plaintext/unknown）→ `value`。
     - 缺失/非字符串的 `value` → `""`。
   - `list` → 递归规范化每个元素，丢弃空部分，用 `"\n\n"` 拼接。
   - 其他任何类型（`None`、`int`、`bool`、意外对象）→ `""`。
   - 防止无限递归：允许嵌套 list，但每层只向 `list` 递归；不追踪 dict 自引用（dict 的 `value` 只作为字符串使用）。
4. 不记录面向用户的提示；对丢弃的畸形形状可选择性地用 `log.debug`，且必须使用惰性 `%` 格式化。不用 `Any`，不用 `TYPE_CHECKING`；`cast` 来自已有的 `typing` 导入。

## 测试（`tests/test_lsp_hover_parsing.py`）

所有用例都是对纯函数的 arrange/act/assert；无 App，无 LSP server。

| 测试 | Arrange / Act | 断言 |
| --- | --- | --- |
| `test_parse_hover_contents_with_none_returns_empty_string` | `parse_hover_contents(None)` | `== ""` |
| `test_parse_hover_contents_with_empty_dict_returns_empty_string` | `parse_hover_contents({})` | `== ""` |
| `test_parse_hover_contents_with_missing_contents_returns_empty_string` | `{"range": {...}}` | `== ""` |
| `test_parse_hover_contents_with_markup_markdown_returns_value` | `{"contents": {"kind": "markdown", "value": "**f()** docs"}}` | `== "**f()** docs"` |
| `test_parse_hover_contents_with_markup_plaintext_returns_value` | `{"kind": "plaintext", "value": "plain docs"}`（裸载荷）| `== "plain docs"` |
| `test_parse_hover_contents_with_whitespace_only_returns_empty_string` | `"  \n\t "` 与 `{"contents": {"kind":"markdown","value":" \n "}}`（参数化）| 两者都 `== ""` |
| `test_parse_hover_contents_with_bare_string_returns_text` | `{"contents": "hover text"}` | `== "hover text"` |
| `test_parse_hover_contents_with_marked_string_wraps_language_in_fence` | `{"language": "python", "value": "def f(x: int) -> str:"}` | 以 `` ```python `` 开头且包含该签名 |
| `test_parse_hover_contents_with_string_array_joins_nonempty_parts` | `["sig", "", "docs"]` | `== "sig\n\ndocs"` |
| `test_parse_hover_contents_with_mixed_array_preserves_order` | `[{"language":"python","value":"def f():"}, {"kind":"markdown","value":"docs"}, "tail"]` | 先是围栏签名，然后 `docs`，最后 `tail` |
| `test_parse_hover_contents_with_empty_array_returns_empty_string` | `[]`、`["", "  "]`（参数化）| `== ""` |
| `test_parse_hover_contents_with_malformed_shapes_returns_empty_string` | `{"contents": 42}`、`{"value": 7}`、`{"contents": [None, True, {"value": None}]}`、`object()` | 每一个都 `== ""` |
| `test_parse_hover_contents_is_total_for_hostile_input` | 遍历畸形样本集 | 不抛异常（在循环里包裹每次调用；断言所有结果都是 `str`）|

负向路径意图：每个 AC5 空形状都必须在此处收敛为 `""`，在任何 UI 代码看到它之前。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover_parsing.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp_parsing.py tests/test_lsp.py -q -n 1
```

两条命令退出码都必须为 0。主代理的 wave-1 门禁还会运行完整 pyright 与架构测试套件。

## 风险与回滚

- 风险：server 已经在 `MarkedString` 内放入了围栏代码块。包裹仅在 `language` 存在时应用；双重围栏只是外观问题，且由混合数组测试覆盖。
- 风险：`cast(dict[str, object], ...)` 会放宽 pyright 推断。让所有读取都在 `isinstance(..., str)` 守卫之后，以保持 strict 模式干净。
- 回滚：回退这一笔提交；`parse_hover_contents` 仅由 plan d 消费，而 plan d 在 wave 1 中尚未执行。
