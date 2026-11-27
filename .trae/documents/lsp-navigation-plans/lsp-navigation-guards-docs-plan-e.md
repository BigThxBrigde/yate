# 计划 e — 守卫、文档、冒烟与真实服务器 AC（波次 4）

父计划：[../lsp-navigation-plan.md](../lsp-navigation-plan.md)。

## 输入 / 输出

输入：波次 a-d 的最终代码。输出：架构守卫 + 行数同步、双语文档/手册更新、
冒烟场景、真实 pyright 双文件 AC。

## 独占文件

- `tests/test_architecture.py`
- `.trae/rules/architecture-boundaries.md`
- `yate/docs/lsp.zh.md`
- `yate/docs/lsp.en.md`
- `yate/resources/manual.zh.md`
- `yate/resources/manual.en.md`
- `tools/smoke_test/scenarios/lsp_navigation.py`（新增）
- `tools/smoke_test/scenarios/__init__.py`
- `tests/test_lsp_real_server.py`

## 具体改动

### 1. 架构守卫与计数

- 在 `test_hover_key_is_shared_and_identical`（`tests/test_architecture.py:1666`）旁
  增加 `test_lsp_navigation_keys_are_shared_and_identical`，复制其 AST + 运行时形态：
  - AST：`vsc.py` 和 `vim.py` 的 `build_bindings` 都引用每一个共享常量
    （`GOTO_DEF_KEY`、`FIND_REFS_KEY`、`GOTO_DEF_VSC_KEY`、
    `FIND_REFS_VSC_KEY`、`HOVER_POPUP_KEY`），且不含任何字面量
    `"gd"`、`"gr"`、`"<alt-g>"`、`"<alt-r>"`、`"<shift-k>"`。
  - 运行时：`VscKeymap().lookup(parse_key(GOTO_DEF_VSC_KEY)).action ==
    "goto_definition"`，引用和 hover 同理；`VimKeymap().lookup(
    parse_key(HOVER_POPUP_KEY)).action == "show_hover_docs"`；vim 帮助条目中
    `gd`/`gr` 解析为对应的动作名。
- 用 `.venv/Scripts/python.exe -c "..."` 实测 `keymaps/vim.py`、`editor.py`、
  `editor_lsp/manager.py` 的实际 `splitlines()`。把 `tests/test_architecture.py` 中的
  `SIZE_EXEMPT_LINE_COUNTS` 和 `.trae/rules/architecture-boundaries.md` §三.7 的表格
  更新为完全相同的数字；守卫计数说明保持为 47，并把新用例加入 §六 的列表。
- 核实 `UI_FROZEN_FILES` 无需新增条目：`lsp_navigation_flows.py` 必须只导入
  `editor_components.lsp_chooser` / `hover_popup` / `panes`；若导入了其他模块，
  先登记确切模块（R11）并记录。

### 2. 文档（双语，一次提交内同步）

- `yate/docs/lsp.zh.md` 的能力列表（`:10-27`）与 `lsp.en.md`（`:20-32`）：
  增加 `gd` 定义、`K` hover（保留 `<f7>`）、`:lsp outline`
  （或动作面板：`show_outline`）、`gr` 引用、重命名、代码操作、
  签名帮助的条目；说明这些都受服务器能力门控，且请求为异步并带有显式消息。
- 在两份文档中加一个简短的两文件 pyright 示例，展示 `gd`、`gr`、`K`。
- `yate/resources/manual.zh.md` §16（`:1279-1402`）与 `manual.en.md` §16
  （`:1430` 起）：增加同样的能力概要，以及 `K`、`gd`、`gr`、
  `<alt-g>`、`<alt-r>` 的按键表行；保持双语按键表各节一致。

### 3. 冒烟场景

参照 `scenarios/hover.py`（`:41-224`）增加
`tools/smoke_test/scenarios/lsp_navigation.py`：通过应用的 `set_client_factory`
注入假 LSP 客户端；两文件项目；断言：
- 在调用点按 `gd` 跳转到另一文件的定义行；
- `gr` 打开一个选择器，其 SVG 文本包含两个文件名，回车可导航；
- `K` 和 `F7` 都渲染相同的 hover 文本；
- 无服务器的场景发出警告消息，且缓冲区保持不变。
在 `scenarios/__init__.py` 中以标签 `("lsp-navigation",)` 注册。

### 4. 真实 pyright AC

扩展 `tests/test_lsp_real_server.py`（保留其 `skipif` 门控），增加一个两文件场景：
A 定义 `def greet(name: int) -> str`，B 导入并调用它。两者启动并完成 didOpen 后，断言：
- `request_definition(doc_b, call_row, call_col)` 返回一个 `LspLocation`，其解析路径为 A，
  且行/列与 `def greet` 行一致；
- `request_references` 返回至少两个覆盖两个文件的位置；
- `request_hover` 返回非空文本。
diagnostics 保留现有的 wire-recorder 方式；不要对 manager 的原始 diagnostic 键做断言。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_lsp_real_server.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4 --tag lsp-navigation
```

架构和冒烟要求以 0 退出；真实服务器测试必须通过，或由其现有环境门控显式跳过
（报告是哪一种）。

## 风险 / 回滚

风险：行数表不匹配是硬门禁 —— 在所有其他波次之后测量，绝不要猜。
风险：冒烟的按键事件可能被 vim 前缀处理吞掉；使用场景的 keymap 切换钩子测试两张 keymap。
风险：真实 pyright 可能在 runner 上不可用；保留 skipif 并如实报告。
回滚：回退本计划的提交；波次 a-d 的产品代码保持不变。

## 执行记录（2026-11-22）

主代理实测：架构 `47 passed`，退出 0；真实 pyright `2 passed`（未跳过），退出 0；
标签冒烟 `4/4 scenarios, 43/43 checks`，在下方标签注册之后退出 0。

偏离：`tools/smoke_test/harness.py::TAGS` 不含 `"lsp-navigation"`，因此计划中的
`--tag lsp-navigation` 命令以 `unknown tag(s)` 退出 1。在执行者报告该阻塞项之后，
主代理向该元组中恰好加入了这个标签（在原始独占清单之外），然后重新运行命令成功。
四个场景按名称运行时均已通过，因此没有改动任何场景断言。

偏离（R11 顺序，2026-11-23 于 pr-review 记录）：流程模块在
`tests/test_architecture.py::UI_FROZEN_FILES` 针对 `flows/lsp_navigation_flows.py`
键更新之前，就先导入了 `editor_components.commandline` / `hover_popup` /
`lsp_chooser` / `panes`（R11 要求在导入*之前*先登记）。在波次 4 收尾时，守卫键与
四模块表面均已登记并核实一致（声明集合 == 导入集合，0 缺失 / 0 多余）；
`.trae/rules/architecture-boundaries.md` 的 R11 和 §一 L3 在同一波次同步。
没有架构行为回退；这仅是顺序上的流程偏离，记录在此而非静默略过。
