# yate 计划文档索引（.trae/documents）

本目录存放**方案与计划文档**：每个任务一篇主计划 `<task>-plan.md`；规模较大时
按波次拆进子计划目录 `<task>-plans/`（总纲 `overview.md` + 子计划
`<task>-<subtask>-plan-<a|b|c...>.md`，字母位在目录内唯一）。

**每篇文档头部都有统一的可检索状态块**：

```text
> **实施状态**：<图标> <状态> —— <核对日期与依据>
```

状态取四值：**已实施 / 部分实施 / 未实施 / 已被取代**。本索引由
`tools/_gen_index.py` 从同一份数据生成，与文档头部不会漂移。
2026-10-05 全量核对：逐篇比对文档自述与代码产物是否一致。

> **评审记录不在本目录**，见 [`.trae/reviews/`](../reviews/README.md)。

---

## 一、状态速览

- ✅ **已实施**：134 篇
- 🟡 **部分实施**：4 篇
- ❌ **未实施**：2 篇
- ↩️ **已被取代**：7 篇
- **合计**：147 篇


---

## 二、专题：未实施 / 部分实施 / 已被取代

引用这些文档中的产物路径前，请先按状态块里的依据核实文件是否存在。

### 🟡 部分实施（4 篇）

- [`keybinding-fix-wt-plans/keybinding-fix-wt-gates-matrix-plan-e.md`](keybinding-fix-wt-plans/keybinding-fix-wt-gates-matrix-plan-e.md) —— 自动化部分已实施；SP5 真机矩阵待人工（同上速览 #10）
- [`keybinding-fix-wt-plans/overview.md`](keybinding-fix-wt-plans/overview.md) —— SP1–SP5 自动化已实施；三终端真机人工矩阵未执行（`.trae/reviews/README.md` 速览 #10）
- [`win-keybinding-protocol-plan.md`](win-keybinding-protocol-plan.md) —— `keyproto/` 已落地 5 模块；`kitty.py`、`negotiate.py`、`--key-protocol`、`tools/probe_keys.py` 未落地
- [`wt-keybinding-fix-plan.md`](wt-keybinding-fix-plan.md) —— SP1–SP3 已执行；后续路线由 `keybinding-fix-wt-plans/keybinding-fix-wt-steps-plan-g.md` 承接

### ❌ 未实施（2 篇）

- [`dap-support-plan.md`](dap-support-plan.md) —— `yate/editor_dap*` 实测零文件；`extensions/python_dap.py`、`yate/docs/dap.*.md` 不存在；`config.py` 无 `debug_options`
- [`highlight-comment-flicker-plan.md`](highlight-comment-flicker-plan.md) —— 无专属产物；前置 `typing-flicker-debounce-plan.md` 已实施但本篇未做

### ↩️ 已被取代（7 篇）

- [`editor-refactoring-plans/overview.md`](editor-refactoring-plans/overview.md) —— 历史总纲，产物已并入 `app-layering-refactoring-plans/` 与 `editor-split-plans/`
- [`keybinding-fix-wt-plans/keybinding-fix-wt-key-reachability-plan-f.md`](keybinding-fix-wt-plans/keybinding-fix-wt-key-reachability-plan-f.md) —— 根因假设被探针证伪，已由同目录 `keybinding-fix-wt-steps-plan-g.md` 取代
- [`logs-impl-plan.md`](logs-impl-plan.md) —— 功能已落地但不在本文设想的 `yate/tracing.py`，实际在 `yate/logs.py`
- [`remove-type-checking-refactor.md`](remove-type-checking-refactor.md) —— 2026-09-22 起被分层重构取代；`TYPE_CHECKING` 已清零并由架构测试守卫
- [`split-app-protocol-plan.md`](split-app-protocol-plan.md) —— 计划已完成，中间产物 `yate/interfaces.py` 已随 R2 删除并由 R8 取代
- [`theme-ownership-plan.md`](theme-ownership-plan.md) —— 明示「本文件不再维护」；唯一来源为 `theme-ownership-refactoring-plans/overview.md`
- [`unify-crash-tracing-plan.md`](unify-crash-tracing-plan.md) —— 功能已实现，实现集中在单模块 `yate/logs.py`

---

## 三、全量清单

| # | 计划文档 | 状态 |
|---|---|---|
| 1 | [`app-capability-injection-plan.md`](app-capability-injection-plan.md) | ✅ 已实施 |
| 2 | [`app-layering-refactoring-plans/app-layering-refactoring-functional-tables-plan-c.md`](app-layering-refactoring-plans/app-layering-refactoring-functional-tables-plan-c.md) | ✅ 已实施 |
| 3 | [`app-layering-refactoring-plans/app-layering-refactoring-gate-docs-plan-f.md`](app-layering-refactoring-plans/app-layering-refactoring-gate-docs-plan-f.md) | ✅ 已实施 |
| 4 | [`app-layering-refactoring-plans/app-layering-refactoring-leaf-models-plan-a.md`](app-layering-refactoring-plans/app-layering-refactoring-leaf-models-plan-a.md) | ✅ 已实施 |
| 5 | [`app-layering-refactoring-plans/app-layering-refactoring-pane-model-to-session-plan-g.md`](app-layering-refactoring-plans/app-layering-refactoring-pane-model-to-session-plan-g.md) | ✅ 已实施 |
| 6 | [`app-layering-refactoring-plans/app-layering-refactoring-shell-wiring-plan-d.md`](app-layering-refactoring-plans/app-layering-refactoring-shell-wiring-plan-d.md) | ✅ 已实施 |
| 7 | [`app-layering-refactoring-plans/app-layering-refactoring-tests-tools-plan-e.md`](app-layering-refactoring-plans/app-layering-refactoring-tests-tools-plan-e.md) | ✅ 已实施 |
| 8 | [`app-layering-refactoring-plans/app-layering-refactoring-widget-selfhold-plan-b.md`](app-layering-refactoring-plans/app-layering-refactoring-widget-selfhold-plan-b.md) | ✅ 已实施 |
| 9 | [`app-layering-refactoring-plans/overview.md`](app-layering-refactoring-plans/overview.md) | ✅ 已实施 |
| 10 | [`changelog-plan.md`](changelog-plan.md) | ✅ 已实施 |
| 11 | [`clipboard-review-round2-fixes-plan.md`](clipboard-review-round2-fixes-plan.md) | ✅ 已实施 |
| 12 | [`code-coverage-and-test-expansion-plan.md`](code-coverage-and-test-expansion-plan.md) | ✅ 已实施 |
| 13 | [`code-review-fix-p1-plans/code-review-fix-p1-editor-view-rendering-plan-c.md`](code-review-fix-p1-plans/code-review-fix-p1-editor-view-rendering-plan-c.md) | ✅ 已实施 |
| 14 | [`code-review-fix-p1-plans/code-review-fix-p1-keymaps-and-completion-plan-d.md`](code-review-fix-p1-plans/code-review-fix-p1-keymaps-and-completion-plan-d.md) | ✅ 已实施 |
| 15 | [`code-review-fix-p1-plans/code-review-fix-p1-services-and-logs-plan-e.md`](code-review-fix-p1-plans/code-review-fix-p1-services-and-logs-plan-e.md) | ✅ 已实施 |
| 16 | [`code-review-fix-p1-plans/code-review-fix-p1-syntax-highlight-perf-plan-a.md`](code-review-fix-p1-plans/code-review-fix-p1-syntax-highlight-perf-plan-a.md) | ✅ 已实施 |
| 17 | [`code-review-fix-p1-plans/code-review-fix-p1-terminal-subsystem-plan-b.md`](code-review-fix-p1-plans/code-review-fix-p1-terminal-subsystem-plan-b.md) | ✅ 已实施 |
| 18 | [`code-review-fix-p1-plans/code-review-fix-p1-test-hygiene-and-document-plan-f.md`](code-review-fix-p1-plans/code-review-fix-p1-test-hygiene-and-document-plan-f.md) | ✅ 已实施 |
| 19 | [`code-review-fix-p1-plans/code-review-fix-p1-toolchain-plan-g.md`](code-review-fix-p1-plans/code-review-fix-p1-toolchain-plan-g.md) | ✅ 已实施 |
| 20 | [`code-review-fix-p1-plans/overview.md`](code-review-fix-p1-plans/overview.md) | ✅ 已实施 |
| 21 | [`code-review-fix-p2-plans/code-review-fix-p2-editor-core-plan-a.md`](code-review-fix-p2-plans/code-review-fix-p2-editor-core-plan-a.md) | ✅ 已实施 |
| 22 | [`code-review-fix-p2-plans/code-review-fix-p2-editor-dispatch-components-plan-f.md`](code-review-fix-p2-plans/code-review-fix-p2-editor-dispatch-components-plan-f.md) | ✅ 已实施 |
| 23 | [`code-review-fix-p2-plans/code-review-fix-p2-editor-syntax-plan-b.md`](code-review-fix-p2-plans/code-review-fix-p2-editor-syntax-plan-b.md) | ✅ 已实施 |
| 24 | [`code-review-fix-p2-plans/code-review-fix-p2-keymaps-registry-plan-e.md`](code-review-fix-p2-plans/code-review-fix-p2-keymaps-registry-plan-e.md) | ✅ 已实施 |
| 25 | [`code-review-fix-p2-plans/code-review-fix-p2-services-logs-plan-g.md`](code-review-fix-p2-plans/code-review-fix-p2-services-logs-plan-g.md) | ✅ 已实施 |
| 26 | [`code-review-fix-p2-plans/code-review-fix-p2-terminal-plan-c.md`](code-review-fix-p2-plans/code-review-fix-p2-terminal-plan-c.md) | ✅ 已实施 |
| 27 | [`code-review-fix-p2-plans/code-review-fix-p2-toolchain-plan-d.md`](code-review-fix-p2-plans/code-review-fix-p2-toolchain-plan-d.md) | ✅ 已实施 |
| 28 | [`code-review-fix-p2-plans/overview.md`](code-review-fix-p2-plans/overview.md) | ✅ 已实施 |
| 29 | [`code-review-fix-plans/code-review-fix-critical-plan-a.md`](code-review-fix-plans/code-review-fix-critical-plan-a.md) | ✅ 已实施 |
| 30 | [`code-review-fix-plans/code-review-fix-nice-to-have-plan-c.md`](code-review-fix-plans/code-review-fix-nice-to-have-plan-c.md) | ✅ 已实施 |
| 31 | [`code-review-fix-plans/code-review-fix-suggestions-plan-b.md`](code-review-fix-plans/code-review-fix-suggestions-plan-b.md) | ✅ 已实施 |
| 32 | [`code-review-fixes-plan.md`](code-review-fixes-plan.md) | ✅ 已实施 |
| 33 | [`completion-staleness-check-plan.md`](completion-staleness-check-plan.md) | ✅ 已实施 |
| 34 | [`crash-diagnostic-plan.md`](crash-diagnostic-plan.md) | ✅ 已实施 |
| 35 | [`dap-support-plan.md`](dap-support-plan.md) | ❌ 未实施 |
| 36 | [`diag-command-plan.md`](diag-command-plan.md) | ✅ 已实施 |
| 37 | [`diag-package-sync-plans/diag-package-sync-diagnostics-plan-a.md`](diag-package-sync-plans/diag-package-sync-diagnostics-plan-a.md) | ✅ 已实施 |
| 38 | [`diag-package-sync-plans/diag-package-sync-pack-metadata-plan-b.md`](diag-package-sync-plans/diag-package-sync-pack-metadata-plan-b.md) | ✅ 已实施 |
| 39 | [`diag-package-sync-plans/overview.md`](diag-package-sync-plans/overview.md) | ✅ 已实施 |
| 40 | [`diff-review-fixes-plan.md`](diff-review-fixes-plan.md) | ✅ 已实施 |
| 41 | [`diff-tool-plan.md`](diff-tool-plan.md) | ✅ 已实施 |
| 42 | [`diff-tool-plans/diff-tool-diff-engine-plan-a.md`](diff-tool-plans/diff-tool-diff-engine-plan-a.md) | ✅ 已实施 |
| 43 | [`diff-tool-plans/diff-tool-diffview-plan-b.md`](diff-tool-plans/diff-tool-diffview-plan-b.md) | ✅ 已实施 |
| 44 | [`diff-tool-plans/diff-tool-integration-plan-c.md`](diff-tool-plans/diff-tool-integration-plan-c.md) | ✅ 已实施 |
| 45 | [`diff-tool-plans/overview.md`](diff-tool-plans/overview.md) | ✅ 已实施 |
| 46 | [`dist-copy-plan.md`](dist-copy-plan.md) | ✅ 已实施 |
| 47 | [`doc-plans-naming-convention-plan.md`](doc-plans-naming-convention-plan.md) | ✅ 已实施 |
| 48 | [`editor-refactoring-plans/editor-refactoring-assembly-plan-a.md`](editor-refactoring-plans/editor-refactoring-assembly-plan-a.md) | ✅ 已实施 |
| 49 | [`editor-refactoring-plans/editor-refactoring-lsp-sync-plan-b.md`](editor-refactoring-plans/editor-refactoring-lsp-sync-plan-b.md) | ✅ 已实施 |
| 50 | [`editor-refactoring-plans/editor-refactoring-overlays-plan-d.md`](editor-refactoring-plans/editor-refactoring-overlays-plan-d.md) | ✅ 已实施 |
| 51 | [`editor-refactoring-plans/editor-refactoring-prompt-flows-plan-e.md`](editor-refactoring-plans/editor-refactoring-prompt-flows-plan-e.md) | ✅ 已实施 |
| 52 | [`editor-refactoring-plans/editor-refactoring-shell-plan-c.md`](editor-refactoring-plans/editor-refactoring-shell-plan-c.md) | ✅ 已实施 |
| 53 | [`editor-refactoring-plans/overview.md`](editor-refactoring-plans/overview.md) | ↩️ 已被取代 |
| 54 | [`editor-split-plans/editor-split-delegates-plan-c.md`](editor-split-plans/editor-split-delegates-plan-c.md) | ✅ 已实施 |
| 55 | [`editor-split-plans/editor-split-docs-plan-a.md`](editor-split-plans/editor-split-docs-plan-a.md) | ✅ 已实施 |
| 56 | [`editor-split-plans/editor-split-documents-plan-d.md`](editor-split-plans/editor-split-documents-plan-d.md) | ✅ 已实施 |
| 57 | [`editor-split-plans/editor-split-extension-flows-plan-f.md`](editor-split-plans/editor-split-extension-flows-plan-f.md) | ✅ 已实施 |
| 58 | [`editor-split-plans/editor-split-flows-rename-plan-b.md`](editor-split-plans/editor-split-flows-rename-plan-b.md) | ✅ 已实施 |
| 59 | [`editor-split-plans/editor-split-windows-plan-e.md`](editor-split-plans/editor-split-windows-plan-e.md) | ✅ 已实施 |
| 60 | [`editor-split-plans/overview.md`](editor-split-plans/overview.md) | ✅ 已实施 |
| 61 | [`fancy-sym-plan.md`](fancy-sym-plan.md) | ✅ 已实施 |
| 62 | [`fancy-sym-plans/fancy-sym-config-plan-c.md`](fancy-sym-plans/fancy-sym-config-plan-c.md) | ✅ 已实施 |
| 63 | [`fancy-sym-plans/fancy-sym-docs-plan-e.md`](fancy-sym-plans/fancy-sym-docs-plan-e.md) | ✅ 已实施 |
| 64 | [`fancy-sym-plans/fancy-sym-final-plan-f.md`](fancy-sym-plans/fancy-sym-final-plan-f.md) | ✅ 已实施 |
| 65 | [`fancy-sym-plans/fancy-sym-rosters-tool-plan-b.md`](fancy-sym-plans/fancy-sym-rosters-tool-plan-b.md) | ✅ 已实施 |
| 66 | [`fancy-sym-plans/fancy-sym-screen-plan-d.md`](fancy-sym-plans/fancy-sym-screen-plan-d.md) | ✅ 已实施 |
| 67 | [`fancy-sym-plans/fancy-sym-sprites-plan-a.md`](fancy-sym-plans/fancy-sym-sprites-plan-a.md) | ✅ 已实施 |
| 68 | [`fancy-sym-plans/overview.md`](fancy-sym-plans/overview.md) | ✅ 已实施 |
| 69 | [`fancy-sym-review-fixes-plan.md`](fancy-sym-review-fixes-plan.md) | ✅ 已实施 |
| 70 | [`fix-folder-deletion-lsp-notify-plan.md`](fix-folder-deletion-lsp-notify-plan.md) | ✅ 已实施 |
| 71 | [`highlight-comment-flicker-plan.md`](highlight-comment-flicker-plan.md) | ❌ 未实施 |
| 72 | [`input-assist-plan.md`](input-assist-plan.md) | ✅ 已实施 |
| 73 | [`input-assist-review-fixes-plan.md`](input-assist-review-fixes-plan.md) | ✅ 已实施 |
| 74 | [`keybinding-fix-wt-plans/keybinding-fix-wt-ctrl-slash-mapping-plan-a.md`](keybinding-fix-wt-plans/keybinding-fix-wt-ctrl-slash-mapping-plan-a.md) | ✅ 已实施 |
| 75 | [`keybinding-fix-wt-plans/keybinding-fix-wt-dispatch-guards-diag-plan-b.md`](keybinding-fix-wt-plans/keybinding-fix-wt-dispatch-guards-diag-plan-b.md) | ✅ 已实施 |
| 76 | [`keybinding-fix-wt-plans/keybinding-fix-wt-docs-backfill-plan-d.md`](keybinding-fix-wt-plans/keybinding-fix-wt-docs-backfill-plan-d.md) | ✅ 已实施 |
| 77 | [`keybinding-fix-wt-plans/keybinding-fix-wt-gates-matrix-plan-e.md`](keybinding-fix-wt-plans/keybinding-fix-wt-gates-matrix-plan-e.md) | 🟡 部分实施 |
| 78 | [`keybinding-fix-wt-plans/keybinding-fix-wt-issue-reply-plan-h.md`](keybinding-fix-wt-plans/keybinding-fix-wt-issue-reply-plan-h.md) | ✅ 已实施 |
| 79 | [`keybinding-fix-wt-plans/keybinding-fix-wt-key-reachability-plan-f.md`](keybinding-fix-wt-plans/keybinding-fix-wt-key-reachability-plan-f.md) | ↩️ 已被取代 |
| 80 | [`keybinding-fix-wt-plans/keybinding-fix-wt-manual-terminal-notes-plan-c.md`](keybinding-fix-wt-plans/keybinding-fix-wt-manual-terminal-notes-plan-c.md) | ✅ 已实施 |
| 81 | [`keybinding-fix-wt-plans/keybinding-fix-wt-steps-plan-g.md`](keybinding-fix-wt-plans/keybinding-fix-wt-steps-plan-g.md) | ✅ 已实施 |
| 82 | [`keybinding-fix-wt-plans/overview.md`](keybinding-fix-wt-plans/overview.md) | 🟡 部分实施 |
| 83 | [`logging-for-layers-plan.md`](logging-for-layers-plan.md) | ✅ 已实施 |
| 84 | [`logs-impl-plan.md`](logs-impl-plan.md) | ↩️ 已被取代 |
| 85 | [`lsp-support-plan.md`](lsp-support-plan.md) | ✅ 已实施 |
| 86 | [`overlay-theme-consistency-plan.md`](overlay-theme-consistency-plan.md) | ✅ 已实施 |
| 87 | [`pack-wiki-plan.md`](pack-wiki-plan.md) | ✅ 已实施 |
| 88 | [`pack-wiki-review-fixes-plan.md`](pack-wiki-review-fixes-plan.md) | ✅ 已实施 |
| 89 | [`path-space-handling-plan.md`](path-space-handling-plan.md) | ✅ 已实施 |
| 90 | [`pr47-review-fixes-plan.md`](pr47-review-fixes-plan.md) | ✅ 已实施 |
| 91 | [`py-style-audit-plan.md`](py-style-audit-plan.md) | ✅ 已实施 |
| 92 | [`pytest-isolation-plan.md`](pytest-isolation-plan.md) | ✅ 已实施 |
| 93 | [`python-312-upgrade-plans/overview.md`](python-312-upgrade-plans/overview.md) | ✅ 已实施 |
| 94 | [`python-312-upgrade-plans/python-312-upgrade-plan-a.md`](python-312-upgrade-plans/python-312-upgrade-plan-a.md) | ✅ 已实施 |
| 95 | [`python-312-upgrade-plans/python-312-upgrade-plan-b.md`](python-312-upgrade-plans/python-312-upgrade-plan-b.md) | ✅ 已实施 |
| 96 | [`python-312-upgrade-plans/python-312-upgrade-plan-c.md`](python-312-upgrade-plans/python-312-upgrade-plan-c.md) | ✅ 已实施 |
| 97 | [`python-312-upgrade-plans/python-312-upgrade-plan-d.md`](python-312-upgrade-plans/python-312-upgrade-plan-d.md) | ✅ 已实施 |
| 98 | [`python-312-upgrade-plans/python-312-upgrade-plan-e.md`](python-312-upgrade-plans/python-312-upgrade-plan-e.md) | ✅ 已实施 |
| 99 | [`python-code-review-fixes-plan.md`](python-code-review-fixes-plan.md) | ✅ 已实施 |
| 100 | [`readonly-option-plan.md`](readonly-option-plan.md) | ✅ 已实施 |
| 101 | [`release-tool-hardening-plan.md`](release-tool-hardening-plan.md) | ✅ 已实施 |
| 102 | [`release-tool-plan.md`](release-tool-plan.md) | ✅ 已实施 |
| 103 | [`remove-inline-default-css-plans/overview.md`](remove-inline-default-css-plans/overview.md) | ✅ 已实施 |
| 104 | [`remove-inline-default-css-plans/remove-inline-default-css-plan-a.md`](remove-inline-default-css-plans/remove-inline-default-css-plan-a.md) | ✅ 已实施 |
| 105 | [`remove-inline-default-css-plans/remove-inline-default-css-plan-b.md`](remove-inline-default-css-plans/remove-inline-default-css-plan-b.md) | ✅ 已实施 |
| 106 | [`remove-inline-default-css-plans/remove-inline-default-css-plan-c.md`](remove-inline-default-css-plans/remove-inline-default-css-plan-c.md) | ✅ 已实施 |
| 107 | [`remove-type-checking-refactor.md`](remove-type-checking-refactor.md) | ↩️ 已被取代 |
| 108 | [`review-vscode-keymap-plan.md`](review-vscode-keymap-plan.md) | ✅ 已实施 |
| 109 | [`reviews-open-issues-fixes-plan.md`](reviews-open-issues-fixes-plan.md) | ✅ 已实施 |
| 110 | [`reviews-plans-full-sweep-plan.md`](reviews-plans-full-sweep-plan.md) | ✅ 已实施 |
| 111 | [`screensaver-extension-api-plan.md`](screensaver-extension-api-plan.md) | ✅ 已实施 |
| 112 | [`screensaver-p1-p7-fix-plan.md`](screensaver-p1-p7-fix-plan.md) | ✅ 已实施 |
| 113 | [`scrollbar-tab-click-plan.md`](scrollbar-tab-click-plan.md) | ✅ 已实施 |
| 114 | [`setup-defaults-plan.md`](setup-defaults-plan.md) | ✅ 已实施 |
| 115 | [`smoke-test-improvement-plan.md`](smoke-test-improvement-plan.md) | ✅ 已实施 |
| 116 | [`split-app-protocol-plan.md`](split-app-protocol-plan.md) | ↩️ 已被取代 |
| 117 | [`split-panes-plan.md`](split-panes-plan.md) | ✅ 已实施 |
| 118 | [`syntax-langs-plan.md`](syntax-langs-plan.md) | ✅ 已实施 |
| 119 | [`syntax-langs-review-fixes-plan.md`](syntax-langs-review-fixes-plan.md) | ✅ 已实施 |
| 120 | [`system-clipboard-plan.md`](system-clipboard-plan.md) | ✅ 已实施 |
| 121 | [`tcss-split-plan.md`](tcss-split-plan.md) | ✅ 已实施 |
| 122 | [`theme-layer-refactor-plans/overview.md`](theme-layer-refactor-plans/overview.md) | ✅ 已实施 |
| 123 | [`theme-layer-refactor-plans/theme-layer-refactor-baseline-plan-a.md`](theme-layer-refactor-plans/theme-layer-refactor-baseline-plan-a.md) | ✅ 已实施 |
| 124 | [`theme-layer-refactor-plans/theme-layer-refactor-decouple-plan-b.md`](theme-layer-refactor-plans/theme-layer-refactor-decouple-plan-b.md) | ✅ 已实施 |
| 125 | [`theme-layer-refactor-plans/theme-layer-refactor-gate-commit-plan-d.md`](theme-layer-refactor-plans/theme-layer-refactor-gate-commit-plan-d.md) | ✅ 已实施 |
| 126 | [`theme-layer-refactor-plans/theme-layer-refactor-guard-docs-plan-c.md`](theme-layer-refactor-plans/theme-layer-refactor-guard-docs-plan-c.md) | ✅ 已实施 |
| 127 | [`theme-ownership-plan.md`](theme-ownership-plan.md) | ↩️ 已被取代 |
| 128 | [`theme-ownership-refactoring-plans/overview.md`](theme-ownership-refactoring-plans/overview.md) | ✅ 已实施 |
| 129 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-architecture-guards-plan-d.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-architecture-guards-plan-d.md) | ✅ 已实施 |
| 130 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-gate-docs-plan-e.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-gate-docs-plan-e.md) | ✅ 已实施 |
| 131 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-scrollbar-injection-plan-b.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-scrollbar-injection-plan-b.md) | ✅ 已实施 |
| 132 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-theme-broadcast-plan-a.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-theme-broadcast-plan-a.md) | ✅ 已实施 |
| 133 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-theme-gap-terminal-message-plan-f.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-theme-gap-terminal-message-plan-f.md) | ✅ 已实施 |
| 134 | [`theme-ownership-refactoring-plans/theme-ownership-refactoring-widget-theme-selfhold-plan-c.md`](theme-ownership-refactoring-plans/theme-ownership-refactoring-widget-theme-selfhold-plan-c.md) | ✅ 已实施 |
| 135 | [`themes-expansion-plan.md`](themes-expansion-plan.md) | ✅ 已实施 |
| 136 | [`translate-cmd-tool-plan.md`](translate-cmd-tool-plan.md) | ✅ 已实施 |
| 137 | [`typing-flicker-debounce-plan.md`](typing-flicker-debounce-plan.md) | ✅ 已实施 |
| 138 | [`ui-refine-plan.md`](ui-refine-plan.md) | ✅ 已实施 |
| 139 | [`unify-crash-tracing-plan.md`](unify-crash-tracing-plan.md) | ↩️ 已被取代 |
| 140 | [`vim-keymap-review-motion-fixes-plan.md`](vim-keymap-review-motion-fixes-plan.md) | ✅ 已实施 |
| 141 | [`vim-keymap-review-plan.md`](vim-keymap-review-plan.md) | ✅ 已实施 |
| 142 | [`wiki-translate-progress-plan.md`](wiki-translate-progress-plan.md) | ✅ 已实施 |
| 143 | [`win-keybinding-plan.md`](win-keybinding-plan.md) | ✅ 已实施 |
| 144 | [`win-keybinding-protocol-plan.md`](win-keybinding-protocol-plan.md) | 🟡 部分实施 |
| 145 | [`wq-safety-plan.md`](wq-safety-plan.md) | ✅ 已实施 |
| 146 | [`wt-keybinding-fix-plan.md`](wt-keybinding-fix-plan.md) | 🟡 部分实施 |
| 147 | [`yaterc-pyright-plan.md`](yaterc-pyright-plan.md) | ✅ 已实施 |

---

## 四、命名与引用规范（摘要）

完整规约见 `.trae/rules/doc-conventions.md`，要点：

- 主计划 `<task>-plan.md`；子计划目录 `<task>-plans/`（**只用一层**，不再嵌套
  `*-subplans/`）；子计划 `<task>-<subtask>-plan-<a|b|c...>.md`，字母位在目录内
  唯一；子计划目录总纲固定 `overview.md`（不用 `README.md`）。
- 文件名一律 ASCII 小写连字符分词；禁止日期与主题混排；禁止中英混合。
- 正文引用仓库内文件一律用**相对路径**（以本文档自身位置为基准），禁止盘符
  路径、用户目录与仓库根绝对路径；环境信息须脱敏为可移植写法。
- 单篇计划不得超过 1 MB，超出须按子计划规范拆分。

---

## 五、本轮（2026-10-05）全量 review 处置摘要

- **命名**：26 个违规文件已修正——`P1-subplans/` / `P2-subplans/` 消除嵌套并
  更名为 `code-review-fix-p1-plans/` / `code-review-fix-p2-plans/`；
  `keybinding-fix-wt/` → `keybinding-fix-wt-plans/`；
  `issue_reply_IKH1RA.md` → `keybinding-fix-wt-issue-reply-plan-h.md`；
  `fix-folder-deletion-does-not-notify-LSP-plan.md` →
  `fix-folder-deletion-lsp-notify-plan.md`。改名保持目录深度，入链已全部同步。
- **相对链接**：可修复类（目标存在但写成仓库根相对、或少写一层 `../`）已修复；
  **真正失效**的目标（`yate/app_features/*`、`yate/crash.py`、
  `.venv/.../textual/widget.py` 等已删除或本就在仓库外）按 `doc-conventions` §五
  「存量文档不做专项清扫」保留原样，并登记为待办。
- **状态标注**：147 篇全部注入统一状态块，本索引为汇总入口。
- **登记未处理项**：`keybinding-fix-wt-plans/` 内 3 个一次性脚本
  （`win32im_probe.py`、`pb6_real_input_harness.py`、`verify_matrix.ps1`）是计划
  证据附件而非文档，规范无对应形态，保留在原位。

