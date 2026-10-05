# plan_A — 组装工厂化（Wave 1）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
`Editor.__init__`（editor.py:88-207，120 行集中组装）拆为模块级工厂函数，构造函数只留
「参数接收 + 顺序调用」。review 问题 5 的直接落地。

## 改动文件（独占）
- `yate/editor.py` —— 仅此一个文件

## 实施
1. `Editor` 类体顶部补**类级注解声明**（无赋值值、无 TYPE_CHECKING）：`session` /
   `workspace` / `lsp` / `keymaps` / `actions` / `commands` / `extension_api` /
   `extension_loader` / `key_ui` / `prompt_bar` / `tabbar` / `breadcrumbs` /
   `completion_popup` / `terminal_panel` / `explorer_tree` / `status_bar` /
   `sidebar` / `sidebar_head` / `editor_col` / `panes` / `pane_host` / `completion`。
   （理由：属性改由模块级函数赋值后，pyright strict 不再从函数内赋值推断实例属性。）
2. 新增模块级私有工厂（签名一律 `ed: Editor` 显式传入，不用隐藏 self）：
   - `_build_models(ed, keymap: str | None) -> None`——session / workspace / lsp /
     keymaps / registries / extension_api / extension_loader / key_ui（原 112-143 行）。
     `on_closed=self._lsp_documents_closed`、`on_event=self._on_lsp_event` 保持现状
     （Wave B 才改接）。
   - `_build_widgets(ed) -> None`——prompt_bar / tabbar / breadcrumbs /
     completion_popup / terminal_panel / explorer_tree / status_bar / 三容器
     （原 145-174 行）。回调均为 ed 的绑定方法，构造期只存不调，安全。
   - `_build_pane_stack(ed) -> None`——panes / pane_host / completion（原 188-207 行）。
3. `__init__` 收敛为：参数与状态字段（app/config/ext_files/ext_dirs/_mounted/
   _window_pending/startup_readonly/_ext_messages）→ `_open_startup_target(ed, target)`
   （原 176-185 行目标打开 + 空缓冲种子，独立成第三个工厂）→ `_build_models` →
   `_build_widgets` → `_build_pane_stack`，共约 25 行。
4. 保持原构造顺序不变（models → widgets → target → panes；target 依赖 widgets 后的
   现状语义：`_open_target` 只用 workspace/session， explorer_visible 判定不变）。
   实施时按现有顺序逐行搬运，不重排。

## 输出 / 验收
```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.smoke_test run
```
- `__init__` ≤ 30 行；tests/ 目录零 diff；架构测试 20 用例全绿。

## 回滚
本波单独提交，`git revert` 即回基线。
