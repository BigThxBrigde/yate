# LSP 导航评审修复计划（评审后迭代）

评审记录：[../reviews/2026-11-22-lsp-navigation.md](../reviews/2026-11-22-lsp-navigation.md)。
B1 经直接探针验证予以否决（8 处冲突不变；`gd`/`gr` 未被保留）。
接受修复：B2、M1-M6，以及低成本的次要项 m3/m7/m8/m9/m13。
登记在册的后续项（此处不修）：m1、m2（由 M4 测试部分缓解）、
m4、m5、m6、m10、m11、m12。

## 修复波次 F1 — 测试、文档、注释（与 F2 并行）

独占文件：
`tools/smoke_test/scenarios/lsp_navigation.py`、`tests/test_action_table.py`、
`tests/test_vim_keymap.py`、`tests/test_architecture.py`、
`yate/keymaps/vim.py`、`yate/docs/lsp.zh.md`、`yate/docs/lsp.en.md`、
`yate/resources/manual.zh.md`、`yate/resources/manual.en.md`。

1. M1：把 `_open_call_site(pilot: object, ...)` 改为
   `pilot: Any,  # noqa: Any - naming Pilot would import textual here`
   （遵循 `scenarios/_base.py:111`）。对该文件运行 pyright。
2. M2：在 `tests/test_action_table.py` 中把 `lsp_navigation` 加入
   `_FLOW_NAMESPACES`，并把六条 `lsp_navigation.*` 条目加入 `FORWARDED_HOOKS`
   （名称与 `yate/actions.py` 一致）；在 `tests/test_vim_keymap.py:1975-1978`
   追加两行新的 `g` 前缀提示行。运行这两个测试文件。
3. B2：重写 `vim.py:280-282` 的注释，说明 `gd`/`gr` 行是被 `g` 前缀分支消费的
   帮助镜像行，而 `K` 是被 `_handle_normal` 查表使用的真正分发行。在
   `tests/test_architecture.py::test_lsp_navigation_keys_are_shared_and_identical`
   中增加运行时断言：在 vim 和 vsc 中 `<f7>` 与 `K` 都解析为
   `show_hover_docs`（双行共存）。
4. M3：把四份文档中每一处 `:lsp outline` 的提法替换为 "command
   palette: `show_outline`"（或对应的中文措辞）；本迭代不新增 `:lsp` 命令。
   核验没有 `lsp outline` 的命中。
5. m13：**仅当** `tests/test_lsp_real_server.py:184` 处也被 F2 改动时（事实如此），
   才更新那里的过期注释；否则留给 F2 处理。

验收：冒烟场景通过 pyright；涉及的三个测试文件全绿；架构守卫 47 项通过；
对 `lsp outline` 的 grep 返回 0。

## 修复波次 F2 — 产品健壮性与直接测试（与 F1 并行）

独占文件：
`yate/editor_lsp/manager.py`、`yate/editor_lsp/navigation.py`、
`tests/test_lsp_navigation.py`、`yate/flows/lsp_navigation_flows.py`、
`tests/test_lsp_navigation_flows.py`、
`yate/editor_components/lsp_chooser.py`、`tests/test_lsp_chooser.py`、
`yate/editor_components/commandline.py`、`tests/test_lsp_real_server.py`。

1. M6：为 `LspFeatureUnavailable` 增加 `reason`（默认 `"unsupported"`）；
   `manager._request` 在 client 为 None 时传入 `"no-ready-server"`；
   `_failure_text` 发出 "language server is not ready" 与 "server does not
   support X" 两种文案。为三条降级路径都补上测试。
2. M4：为 `request_document_symbols`、`request_rename`、
   `request_code_actions`、`request_signature_help` 和 `execute_command`
   补上直接的 manager 测试。覆盖 documentChanges、非 ASCII 的 UTF-16 列、
   diagnostic 往返，以及命令失败的日志。缓解评审者 m2：`_clamp_range` 在可用时
   必须使用目标 URI 的 `LspManager._open[uri].doc`；对其他 URI 则原样透传列值，
   而不是按源文档进行钳制。
3. M5：跟踪重命名打开过的文档；失败时恢复文本/光标并在消息中说明；成功时把消息改为
   `Renamed N occurrence(s) in M file(s) (unsaved; save to apply)`。补充一个包含未打开
   目标和无效第二处编辑的测试。
4. 低成本次要项：m3 用 `try/except (LspError, OSError)` 包裹 `send_cancel` 失败并
   调用 `log.debug`（新增模块 logger，R12）；m7 在 `try/finally` 中关闭选择器；
   m8 增加 `PREFIXES["lsp_rename"] = ("Rename: ", "yellow")`；
   m9 删除失效的 `NAV_TIMEOUT_MESSAGE` 分支，或映射被包装的失败
   （LspFeatureFailed 携带方法名）；m13 修复过期注释。
5. 重新测量 `editor_lsp/manager.py` 的 `splitlines()`；若发生变化，则**通过向主代理
   报告该数字**，由主代理在 F1 的 `tests/test_architecture.py` 中同步规则表和
   `SIZE_EXEMPT_LINE_COUNTS`（不构成文件重叠违规）。

验收：新增/更新的测试文件全绿；涉及的产品文件通过 pyright；此处不跑完整套件
（由主代理运行最终门禁）。

## 收尾

F1+F2 之后，主代理重新运行五道门禁，用修复后的结果更新评审记录，并分别提交
每个修复波次。不推送、不合并。
