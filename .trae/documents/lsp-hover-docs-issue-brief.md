# IKTPC2 issue brief (LSP hover API docs)

Source: <https://gitee.com/jermaine/yate/issues/IKTPC2>
Title: `FEAT: LSP 启动后支持统一快捷键 / 鼠标悬停查看 API 文档，无文档时静默不显示`
Created: 2026-11-08 09:36 by Jermaine007; label `enhancement`; status 待办的; comments 0.
Attachment: external reference image (signature + docstring floating card), not in repo.

> This brief is step 1 (领会) material only: transcribed requirements and observed
> environment facts. It contains no task analysis and no design. The planner in
> step 2 owns analysis.

## 1. Requirement original text

LSP 启动后，希望：

1. 光标停在某个 API（函数 / 类 / 方法 / 变量等符号）上时，按快捷键即可查看该 API 的文档；
2. 鼠标悬停在该 API 上时，也能查看同一份文档；
3. **vsc 和 vim 两套 keymap 使用统一的快捷键**，不因模式不同给不同键；
4. **如果该 API 没有文档（结果为空），则什么都不显示。**

期望效果：符号附近弹出一张悬浮卡片，上部是格式化后的函数签名
（如 `def _capture(cmd: list[str], *, timeout: float) -> str:`），下部是 docstring 正文，
类似 VSCode 的 hover 卡片。

## 2. Current-state evidence transcribed from the issue

| 现状 | 证据 |
| --- | --- |
| LSP 客户端目前只提供自动补全与诊断 | `yate/docs/lsp.zh.md:5-8,10-17`、`yate/resources/manual.zh.md:1183-1200` |
| 未发送 `textDocument/hover`；`initialize` 未声明 `hoverProvider`，`completion.documentationFormat` 为空数组 | `yate/editor_lsp/manager.py:541,586,632-639`、`yate/editor_lsp/client.py:598-625` |
| 补全项解析只取 `label` / `insertText` / `detail`，不取文档字段 | `yate/editor_lsp/parsing.py:146-190` |
| 没有 hover / tooltip 浮层，也没有「查看文档 / 签名帮助」的 action 或 `:` 命令；唯一的轻量浮层是补全弹窗 | `yate/editor_components/completion.py:78,114-159`、`yate/actions.py:54-236`、`yate/commands.py:522-533` |
| 鼠标事件管线已就绪（`support_mouse` 默认开启、`MouseMove` 已转发），但非拖拽的 `MouseMove` 未被消费，可作为悬停触发接入点 | `yate/config.py:163-168`、`yate/editor_components/view.py:281-303`、`yate/editor_dispatch.py:181`、`yate/flows/mouse_flows.py:43-58,96-106` |
| 两套 keymap 各自维护内置绑定表；扩展侧已有 `keymap="both"` 的一次绑定语义 | `yate/keymaps/vsc.py:78-121`、`yate/keymaps/vim.py:165-227`、`yate/docs/extensions.zh.md:27` |
| 已占用：`Ctrl+Space`（手动补全）、`<f1>` help、`<f2>` shell_prompt、`<f9>` which-key、`<ctrl-shift-k>` 删除行；`<ctrl-k>` 当前空闲。vim 裸字母 `k` 是移动键，vsc 又无模态，故裸 `K` 不能同时用于两套 | `yate/editor_dispatch.py:64-81`、`yate/keymaps/vsc.py:47,116,119,121`、`yate/keymaps/vim.py:151` |
| 「空结果静默」已有先例：补全弹窗无条目时直接关闭；反例是 `:diagnostics` 无诊断时仍输出一条提示，本需求要的是前者行为 | `yate/editor_components/completion.py:130-132`、`yate/flows/lsp_sync.py:117-119` |
| 已有全屏 Markdown 渲染，但没有浮层内的 Markdown 渲染 | `yate/editor_components/manual.py:348` |

结论（issue 原文）：这是新增能力，不是修复；文档目前也只声明补全与诊断，需补 hover 章节。

## 3. Goals (What)

1. **发起 `textDocument/hover`**：客户端 `initialize` 声明 `hoverProvider` 并声明支持的
   `documentationFormat`；光标位置按 LSP（UTF-16）位置编码换算。只在该 buffer 已有就绪
   LSP server 时发起请求，不因 hover 反向启动 server、不触发额外的 `didOpen`、
   不改变现有的全文同步行为。
2. **统一快捷键（硬性）**：新增一个「显示光标处 API 文档」的 action，**vsc 与 vim 两套
   keymap 使用完全相同的默认键位**，不得各配一套、不得因模式不同给不同键。
   默认建议 `<ctrl-k>`（`K` = keyword / 查看文档，两套当前均空闲）：键位字符串在
   单一位置定义，两套 keymap 共同引用；用户改键沿用扩展 `bind_key(..., keymap="both")`
   的一次绑定语义，单独覆盖某一套仅属用户显式选择。键位必须避开 `Ctrl+Space`、
   `<f1>` / `<f2>` / `<f9>`、`<ctrl-shift-k>` 与 vim 裸字母 motion 键；**不采用**
   `Ctrl+K Ctrl+I` 之类两序列键弦（终端中 `Ctrl+I` 与 `Tab` 同码，且现有键位记法
   只支持单键 / 单修饰组合，见 `yate/keymaps/keys.py:19-22`）。若实现阶段发现
   `<ctrl-k>` 与终端 / 驱动冲突，两套必须同步换成同一个新值，并同步手册与键位速查表。
3. **鼠标悬停触发**：`support_mouse` 开启时，非拖拽 `MouseMove` 命中符号后经短防抖
   发起同一请求；鼠标移开、光标移动、任意编辑键或 `Esc` 后卡片消失。
   `support_mouse` 关闭时该路径整体禁用，且不消费未处理的鼠标/按键事件。
   鼠标路径同样不区分 keymap。
4. **悬浮卡片渲染**：渲染 LSP `Hover.contents`——`MarkupContent` 的 markdown / plaintext、
   `MarkedString` 及其数组都要支持，可显示签名、类型说明、docstring 等；
   卡片在光标/符号附近定位，空间不足时翻转，不抢焦点、不遮挡编辑操作，
   样式取主题令牌并随主题切换自持着色，可滚动时遵循项目既有滚动条规范。
5. **空结果静默（硬性）**：hover 返回 `null`、无 `contents`、内容为空或全空白、空数组，
   以及 LSP 未启动 / 未就绪 / 当前语言无 server / 请求失败 / 超时等任何无文档情形，
   一律**不显示任何东西**：不弹空卡片、不显示「无文档 / No documentation」占位文案、
   不在消息栏或状态栏输出提示、不闪一下再消失。UI 层面零反馈
   （tracing 调试日志不受此限）。
6. **与既有功能共存**：不改变自动补全、诊断、补全弹窗与现有键位行为；
   hover 卡片不吞掉未处理的按键；请求结果绑定发出时的文件与位置，
   切 buffer、关闭文件、光标移走后的过期结果直接丢弃，不残留旧卡片。

## 4. Reproduction steps and observed behavior (issue text)

1. 按 `yate/docs/lsp.zh.md` 配置并让 Python 语言服务器就绪（状态栏显示服务器名）。
2. 打开一个含带 docstring 的函数（如 `_capture`）的 `.py` 文件，把光标移到函数名上。
3. 按预期快捷键，或把鼠标停在函数名上。
4. 用 `<ctrl+/>` 切换到另一套 keymap，再按同一个快捷键。
5. 实际：没有任何文档显示——当前没有 hover 请求、没有对应的 action / 键位、
   也没有鼠标悬停处理，功能不存在。

## 5. Expected behavior (issue text)

- 有文档时：出现悬浮卡片，显示签名与 docstring（参考附件截图）；快捷键与鼠标悬停
  两条路径显示同一份内容，且无论当前是 vsc 还是 vim keymap，触发的是同一个键。
- 无文档时（包括把光标移到没有 docstring 的局部变量、LSP 返回空、server 未启动等）：
  屏幕保持原样，无任何卡片、提示或状态变化。

## 6. Acceptance criteria (AC1-AC8, verbatim)

- **AC1** 请求契约：光标位置正确换算后发送 `textDocument/hover`；`initialize` 声明
  `hoverProvider` 与 `documentationFormat`；有单元用例覆盖请求参数与位置编码。
- **AC2** 统一快捷键：vsc / vim 两套 keymap 的 hover action 绑定键位字符串**相等且
  出自同一常量**（增加单元/守卫用例，防止后续只改一侧造成漂移）；两套 keymap 下按
  同一个键都能触发；用 `<ctrl+/>` 切换 keymap 后同一键仍生效；与 `Ctrl+Space` /
  `<f1>` / `<f2>` / `<f9>` / `<ctrl-shift-k>` 等既有绑定无冲突；扩展侧 `keymap="both"`
  改键一次对两套同时生效。
- **AC3** 鼠标悬停：`support_mouse` 开 → 非拖拽 `MouseMove` 经防抖触发并可按约定条件关闭；
  `support_mouse` 关 → 完全不触发、不改变既有鼠标行为。
- **AC4** 渲染：`MarkupContent`（markdown / plaintext）、`MarkedString`、字符串数组、
  混合数组均有解析用例；卡片定位/翻转、主题令牌着色、可滚动时的滚动条接线
  （R13 / R15）有回归用例或冒烟用例。
- **AC5** 空结果静默：对 `null` / `{}` / 空字符串 / 全空白 / 空数组 / 失败 / 超时 /
  未启动 / 无 server 逐项断言「零 UI 输出」（无卡片、无消息栏文本、无状态栏变化），
  并覆盖「先有卡片后请求返回空」时卡片被清除的场景。
- **AC6** 隔离性：hover 不启动 server、不触发 `didOpen` / `didChange`，不影响补全与诊断；
  切换 buffer / 光标移动后过期响应不显示；卡片不吞键、不抢焦点。
- **AC7** 文档双语同步：`yate/docs/lsp.en.md` / `lsp.zh.md` 与 `yate/resources/manual.en.md` /
  `manual.zh.md` 同时补上 hover 能力、**同一个默认快捷键**、
  鼠标悬停与「无文档不显示」的行为说明；键位速查表里 vsc / vim 两节写同一个键值；
  如适用，同步 `FEATURES.en.md` / `FEATURES.zh.md`。
- **AC8** 门禁：pyright strict 零诊断、`pytest tests/ -q -n auto` 全绿、
  架构守卫用例全绿、覆盖率门禁 `--cov-fail-under=75`、冒烟全绿；
  新增 hover 解析、统一键位一致性、空结果静默、快捷键与鼠标悬停的自动化用例。

## 7. Non-goals (verbatim)

- 不实现 `textDocument/signatureHelp`（输入参数时自动弹签名）、definition / references /
  rename 等其它 LSP 能力。
- 不改动补全弹窗，也不把补全项的 `documentation` / `detail` 扩展成文档浮层。
- **不为 vsc / vim 各配一套默认键位或另设「专用键」**，也不引入两序列键弦。
- 不在无文档时做源码侧兜底（不猜测签名、不从 buffer 抓取 docstring 顶替），
  也绝不显示任何占位提示。
- 不引入新依赖，不改变 LSP 全文同步协议与现有 server 启动策略。

## 8. Implementation hints (non-binding, from issue)

- L0：`yate/editor_lsp/client.py` 已有通用 `request` 通道；`yate/editor_lsp/manager.py`
  增加 hover 请求封装，`yate/editor_lsp/parsing.py` 增加 `Hover.contents` 归一化。
- L1 / L3 键位：把默认键位定义在一个共享常量处，`yate/keymaps/vsc.py` 与
  `yate/keymaps/vim.py` 都引用它；`yate/actions.py` 注册 action，
  扩展改键沿用 `keymap="both"` 语义。
- L2：参照 `yate/editor_components/completion.py` 的轻量浮层与 `styles.offset` 定位范式
  新增 hover 卡片；Markdown 渲染可复用 `yate/editor_components/manual.py` 的经验，
  但需支持小尺寸浮层。
- L3：`yate/flows/mouse_flows.py` 的非拖拽 `MouseMove` 分支接入悬停防抖；
  复用 `CompletionFlows` / `LspSync` 的请求与结果过期处理范式。
- 遵守既有架构边界：依赖严格向下、组件主题自持与滚动条接线、不新增 `Protocol` /
  `TYPE_CHECKING` / `Any`、日志统一走 tracing。

## 9. Environment facts recorded in step 1 (领会)

- Local `master` HEAD `8cadbc3` equals `origin/master` at task start (2026-11-09).
- New worktree: `yate-lsp-hover-docs`; new branch: `feature/feat-lsp-hover-docs`,
  parent `master`, per `task-orchestration.md` §二.1 and the semantic-naming rule.
- Worktree has its own `.venv` (not shared with the main checkout).
- Rules loaded: all 8 mandatory files under `.trae/rules/`; agent scripts under
  `.trae/agents/`; document conventions under `.trae/rules/doc-conventions.md`.
- Unattended mode: approvals/questions are waived by the user for this session;
  step 3 (批准) is treated as approved, per the workspace rule loader §一.5.
