# plan-c：services/extension 拆分子模块单元测试（wave-1）

## 输入

- `yate/services/extension_api.py`（336 行：`ExtensionContext` / `ExtensionAPI`）
- `yate/services/extension_bridges.py`（221 行：4 个 `*ExtensionBridge`）
- 既有覆盖参照：`tests/test_extensions.py`（22 用例，经
  `services.extensions` 门面——其 fixture 构造方式是本计划的 fixture 范本）；
  `tests/test_ts_backend.py`（SyntaxExtensionBridge 树 sitter 路径）；
  `tests/test_highlight.py:194`（register_language 清理模式先例）。

## 独占文件清单（只新建这 2 个）

- `tests/test_extension_api.py`
- `tests/test_extension_bridges.py`

缺口声明（与 test_extensions.py 不重复的部分）：bind_key 装饰器形态 /
`both` / `normal` 别名 / 位置参数（Lua 桥）、`command` 装饰器 vs
`register_command`、accessors 转发、二次 `start_scope` 警告、无 scope 时
`rollback_scope` 幂等；4 个桥类除 Syntax 桥外的直测。loader 主路径
（顺序/trust/去重/teardown 隔离）test_extensions.py 已覆盖，**不重建**。

## 一、tests/test_extension_api.py

fixture 范本：参照 `test_extensions.py` 顶部构造 `ExtensionContext`
（`EditorSession(YateConfig())` + `Workspace` + `LspManager` +
`ActionRegistry`/`CommandRegistry` + 收集型 lambda）。message 用
`messages: list[str]` 收集器断言。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_bind_key_decorator_form_registers_binding` | `callback=None` 返回装饰器 | `@api.bind_key("ctrl+shift+t", keymap="vsc")` 装饰 fn → `keymaps.get("vsc").lookup("ctrl+shift+t")` 非 None 且调用命中 fn |
| `test_bind_key_both_targets_two_keymaps` | `both` 双注册 | keymap="both" → vsc 与 vim 的 lookup 都命中同一回调 |
| `test_bind_key_normal_alias_binds_vsc_only` | `normal`→vsc 别名 | keymap="normal" → vsc 命中、vim 的同键 lookup 保持原值 |
| `test_bind_key_positional_keymap_argument_binds` | Lua 桥位置参数 | `api.bind_key("g", fn, "vim")` → vim 命中 |
| `test_command_decorator_registers_raw_args_command` | `command` 装饰器 | `@api.command("ext_cmd")` 装饰 fn(args) → `commands.get("ext_cmd")` 非 None，执行后收到参数串 `"with args"` |
| `test_register_command_default_description_applies` | 缺省描述 | `register_command("ext_cmd2", fn)` → 描述 == `"extension command"` |
| `test_register_action_default_description_applies` | 缺省描述 | `register_action("ext_act", fn)` → 描述 == `"extension action"` |
| `test_accessors_forward_to_context` | accessors 转发 | `api.buffer is ctx.session.buffer`、`api.doc is ctx.session.doc`、`api.workspace is ctx.workspace`、`api.keymaps is ctx.keymaps`、`api.app is ctx`、`api.lsp`/`api.highlight`/`api.syntax`/`api.sprites` 是 4 个桥实例 |
| `test_start_scope_second_call_drops_stale_pending_with_warning` | 陈旧 scope 防御 | start_scope → register_action("x") → 再次 start_scope → `pytest.raises` 无、`caplog` 含 `"extension scope restarted"`（logging.WARNNING 级，logger `yate.services.extension_api`），旧 undo 丢弃（后续 rollback 不回滚 x） |
| `test_rollback_scope_without_active_scope_is_noop` | 幂等 | 未 start_scope 直接 `rollback_scope()` 不抛、registrations 不变 |

回归范围：

```text
.venv\Scripts\python.exe -m pytest tests/test_extensions.py -q
```

## 二、tests/test_extension_bridges.py

fixture：
- `api` / `ctx`：同 plan-c 文件一的构造；
- `restore_langdefs`（autouse）：保存/恢复 langdefs 全局——参照
  `test_highlight.py:194` `test_register_language_tokenizes_and_resolves_by_name`
  的清理写法（执行者读该用例后同款）；
- `restore_sprites`（autouse）：`register_character` 写进程全局——fixture 在
  用例前后用 `SpriteExtensionBridge.unregister`（或 editor_sprites 的
  unregister）清掉 `test_sprite_` 前缀名，并在 teardown 中兜底。
- LSP 桥的 `LspManager` 构造：参照 `tests/test_lsp.py` / `test_app_lsp.py`
  现有 LspManager 实例化方式（执行者先读，若无独立构造先例则用
  `app.editor.lsp`——在 `new_app()`/`YateApp` 上取）。

| 用例 | 行为点 | 断言 |
|---|---|---|
| `test_lsp_bridge_register_server_maps_fields_to_config` | 参数→ServerConfig 映射 | `register_server("probe", command="tss", filetypes=["ts"], args=["-x"], language_ids={"ts":"typescript"})` → manager 配置表中该 server 的 `command/args/filetypes/language_ids` 逐字段相等；缺省字段 `args == []`、`root_markers == DEFAULT_ROOT_MARKERS` |
| `test_lsp_bridge_statuses_reports_state_names` | statuses 形态 | 注册后 `statuses()` 是 `dict[str, str]` 且含 `"probe"` 键，值为状态枚举的 `.value` 字符串 |
| `test_lsp_bridge_has_state_unknown_server_is_false` | 未知 server | `has_state("nope", "running") is False` |
| `test_highlight_bridge_register_resolves_and_pins_regex` | register→langdefs | `register(spec, "zzz")` → `lang_for("zzz") is spec`、`"zzz" in available_filetypes()`、按名解析命中；prefer_regex 钉住生效（断言形态参照 `test_highlight.py::test_register_language_tokenizes_and_resolves_by_name`：注册后对示例文本 tokenize 的结果来自 regex 后端词表） |
| `test_highlight_bridge_spec_builds_langspec` | spec 工厂 | `HighlightExtensionBridge.spec(name="x", ...)` 返回 `LangSpec` 实例且 `name == "x"` |
| `test_highlight_bridge_available_lists_builtin_filetypes` | available 透传 | `HighlightExtensionBridge.available()` 与 `available_filetypes()` 相等且含 `"python"` |
| `test_sprite_bridge_register_and_unregister_roundtrip` | 精灵注册往返 | `register("test_sprite_rt", frames2x2, {"#": "#ffffff", ".": None 之外的合法色})` → `"test_sprite_rt" in bridge.names()`；`unregister` 后不在；坏帧（1 帧）→ `ValueError`（与内置花名册同验证） |
| `test_sprite_bridge_unregister_unknown_raises_key_error` | 未知名 | `unregister("no_such_sprite")` → `pytest.raises(KeyError)` |
| `test_syntax_bridge_register_rejects_unresolvable_grammar` | 可选依赖失败面 | 依 `test_ts_backend.py` 的 ts 可用性判定：未装 → `pytest.raises(RuntimeError)`；已装 → `register_tree_sitter("nope_lang", grammar="no_such_pack", extensions=["npx"], query="(comment) @comment")` → `pytest.raises(ValueError)` 且 `available_filetypes()` 不含 `"npx"`（all-or-nothing） |

回归范围：

```text
.venv\Scripts\python.exe -m pytest tests/test_extensions.py tests/test_ts_backend.py tests/test_highlight.py -q
```

## 验收命令

```text
.venv\Scripts\python.exe -m pytest tests/test_extension_api.py tests/test_extension_bridges.py -q
.venv\Scripts\python.exe -m pyright tests/test_extension_api.py tests/test_extension_bridges.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 风险与回滚

- **全局污染**：langdefs / sprites 注册表是进程全局——两个 autouse fixture
  强制恢复；若恢复遗漏会波及其它用例（症状：`test_highlight.py` /
  `test_editor_sprites.py` 偶发失败）→ 首查 fixture。
- LSP 桥测试若 `LspManager` 无法脱离 App 构造 → 改经 `new_app()` 取
  `app.editor.lsp`（pilot 内），偏离记录于执行记录。
- 回滚 = 删除 2 个测试文件，零产品影响。

## 执行记录

（执行后回填。）
