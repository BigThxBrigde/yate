# 计划 b — 声明 hover 客户端能力（wave-1，L0）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)

## 输入

- `yate/editor_lsp/client.py:591-633`（`_initialize_params`）、`:598-631`（`capabilities`）、`:224-268`（`start()` 握手仅解析 `completionProvider.triggerCharacters`）。
- 主计划 D2：客户端声明 `textDocument.hover.contentFormat`，而**不是** `hoverProvider`（那是 server 侧能力）。issue 的 `documentationFormat` 措辞通过填充现有的补全字段来满足。

## 独占文件

- `yate/editor_lsp/client.py`
- `tests/test_lsp_client_capabilities.py`（新增）

## 具体变更

1. `yate/editor_lsp/client.py:612-620`——在 `textDocument.completion` 块中，将 `"documentationFormat": []` 替换为 `"documentationFormat": ["markdown", "plaintext"]`。
2. `yate/editor_lsp/client.py:620`——在 `textDocument` 内新增一个同级键：

   ```python
   "hover": {
       "dynamicRegistration": False,
       "contentFormat": ["markdown", "plaintext"],
   },
   ```

   保持 `synchronization`、`completion`、`publishDiagnostics`、`workspace`、`window` 与 `textDocumentSync` 逐字节不变（AC6：不改变同步协议）。在 `hover` 上方添加一条 ASCII 注释，说明 `hoverProvider` 是 server 能力，有意不予声明。
3. 将格式列表一次性定义为模块级常量 `DOCUMENTATION_FORMATS: tuple[str, ...] = ("markdown", "plaintext")`，并在两处用 `list(DOCUMENTATION_FORMATS)` 转换，使两个声明不会漂移。将其放在 `ERR_METHOD_NOT_FOUND`（`client.py:44`）旁边并附带 `#:` 注释。**不要**改动 `ServerState`、`start()` 或请求分发。

## 测试（`tests/test_lsp_client_capabilities.py`）

Fixture：按 `tests/test_lsp.py:37-43`（`PY_CONFIG`）的方式构造 `LspClient`，以 `tmp_path` 为根；不启动进程。

| 测试 | Arrange / Act | 断言 |
| --- | --- | --- |
| `test_initialize_params_declares_hover_content_format` | `caps = client._initialize_params()["capabilities"]["textDocument"]` | `caps["hover"] == {"dynamicRegistration": False, "contentFormat": ["markdown", "plaintext"]}` |
| `test_initialize_params_declares_completion_documentation_format` | 同一载荷 | `caps["completion"]["completionItem"]["documentationFormat"] == ["markdown", "plaintext"]` |
| `test_initialize_params_does_not_declare_server_side_hover_provider` | 同一载荷 | `"hoverProvider" not in caps` 且 `"hoverProvider" not in payload["capabilities"]` |
| `test_initialize_params_keeps_existing_capabilities_unchanged` | 将载荷其余部分与一个字面量期望字典比较 | `textDocumentSync`、`synchronization`、`completion` 的其余键、`publishDiagnostics`、`workspace`、`window` 均等于 `client.py:598-631` 的基线值 |
| `test_documentation_formats_constant_is_shared_by_both_declarations` | 读取模块常量，调用 `_initialize_params()` | 两个列表都等于 `list(DOCUMENTATION_FORMATS)` |
| `test_initialize_params_hover_declaration_has_no_dynamic_registration` | `caps["hover"]` | `dynamicRegistration is False`（运行时无新的 server 请求）|

索引 `dict[str, Any]` 载荷时使用 `cast(dict[str, object], ...)` / `cast(list[object], ...)`，使 pyright strict 保持通过，且产品代码中无需新增 `Any` 注解。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_client_capabilities.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_real_server.py -q -n 1
```

两条命令退出码均为 0。第二条证明握手路径未改变。

## 风险与回滚

- 风险：严格的 server 拒绝未知的 `hover` 客户端字段。LSP 3.17 已将其标准化；现有握手在两端都忽略未知字段，且 `tests/test_lsp_real_server.py` 守卫真实 server 路径。
- 风险：填充 `documentationFormat` 会使 server 返回更丰富的补全文档。非目标明确禁止展示它；本计划不允许改动补全解析。
- 回滚：回退该提交；plan d 只读取客户端的 `state`，不读取能力载荷。
