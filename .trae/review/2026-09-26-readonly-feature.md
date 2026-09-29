# yate Code Review — readonly feature 评审（两轮）— 2026-09-26

## readonly feature 评审（两轮）— 2026-09-26

> **范围**：`issues/readonly-opt-impl` 分支的只读模式特性（`cfd9d12..dd47be0`，含合入
> master 的 `c3fcd6f`）。两轮评审：**本地自查**（PR 前主代理 + 2 个验证子代理交叉复核，
> 修复提交 `8b6b1b4`/`d960a08`）与 **Gitee PR #24 评审**（1 阻断 + 8 改进，修复提交
> `1f82fae`/`dd47be0`）。逐条处理依据与实测门禁详见
> [readonly_option_plan.md §5](../documents/readonly_option_plan.md)。
> **门禁（实测 2026-09-26）**：pyright 全仓 0 诊断；pytest 1239 passed / 7 skipped；
> 架构守护测试 13 passed。
>
> **Gitee PR #24 AI 队友审查登记**（[原始评论](https://gitee.com/jermaine/yate/pulls/24#note_51374919_conversation_190960220)，
> 审查时间 2026-09-26 19:30）：结论 ⛔ **1 阻断 + 8 改进，请修改后再合并**；风险等级
> **medium**。四维度判定：功能性与逻辑 ❌ 未通过；安全性 ⚠️ 待优化；性能 ✅ 通过；
> 可维护性 ⚠️ 待优化。潜在影响（原文摘要）：阻断项使 `--readonly` 在会话内打开新文档即
> 失效，用户可能在自认为只读的会话中误改内容；`Document.save()` 缺 L0 护栏可被扩展经
> `api.doc.save()` 绕过只读写盘。下方 PR 节条目已与该评论原文逐条比对（9/9 对应，无
> 遗漏、无新增），全部修复于 `1f82fae`/`dd47be0`；改进2 与本地自查重复已去重。

### 本地自查（提交 8b6b1b4、d960a08）

- [x] **状态栏 `name_budget` 漏减 `lock_cells`（Minor，行为）** —
  [`statusbar.py:119`](../../yate/editor_view/statusbar.py#L119)
  只读 + 长文件名截断时右侧块溢出 2 列被裁。
  *✅ 已修复（2026-09-26，`8b6b1b4`）— 预算补减 `lock_cells`；守卫：100 字符文件名 pilot
  断言右块仍贴边（`test_readonly_statusbar_lock_keeps_right_block_visible`）。*

- [x] **vim `i/I/a/A` 只读仍进 INSERT，与 `o/O` 入口拒绝不一致（Minor，行为）** —
  [`vim.py:374-393`](../../yate/keymaps/vim.py#L374-L393)
  进入插入模式后逐键告警；`o/O` 则在入口被拒且抛错前已移光标（单键残影）。
  *✅ 已修复（2026-09-26，`8b6b1b4`）— `_handle_normal` 的 insert entry 分支入口预检抛
  `BufferReadOnlyError`（vim E21 对齐），不再移动光标；守卫：6 键单测
  `test_insert_entry_refused_on_read_only_buffer`（断言停留 NORMAL 且内容不变）。*

- [x] **`set_readonly` docstring 写 "Toggle"，实为按显式值设置；manual en/zh 同病（Low）** —
  [`editor.py:1112`](../../yate/editor.py#L1112)
  *✅ 已修复（2026-09-26，`d960a08`）— docstring 与 manual en/zh 三处统一改 "Set/设置"。*

- [x] **`_open_readonly` docstring 声称 unnamed/welcome no-op 情形（该路径不可达，Low）** —
  [`editor.py:364`](../../yate/editor.py#L364)
  两个调用点传入的恒为带路径 Document 或 None，所述情形不存在且具误导。
  *✅ 已修复（2026-09-26，`8b6b1b4`）— docstring 改写为实际情形；方法随后随下方 PR 阻断1
  重构删除，条目仅存档。*

- [x] **`execute_action` 未记录"动作因只读被拒返回 True"契约（Low，R10 相关）** —
  [`editor.py:663`](../../yate/editor.py#L663)
  docstring 只写 "False when it is unknown"，而返回值决定键是否 fall-through。
  *✅ 已修复（2026-09-26，`8b6b1b4`）— docstring 补充 refusal→True（请求已消费并提示）语义。*

- [x] **扩展文档缺 `doc.save()` 直调绕过只读的注记（Low）** —
  [`extensions.en.md`](../../yate/docs/extensions.en.md) / `extensions.zh.md`
  *✅ 已修复（2026-09-26，`d960a08` 注记）— 随下方 PR 改进6 收紧为 L0 护栏语义。*

### Gitee PR #24 评审（提交 1f82fae、dd47be0）

- [x] **（阻断）`--readonly` 仅作用启动文件参数，会话内后续打开不继承（Major）** —
  [`editor.py`](../../yate/editor.py) `_open_target` 仅在启动路径应用标志，
  `:e`/分屏/资源管理器等后续打开不受限。
  *✅ 已修复（2026-09-26，`1f82fae`）— 标志下沉 `_open_document` / `_open_document_async`
  （所有打开路径汇聚点）：新开文档一律继承；经 `session.is_open` 复用检测——重开已解锁
  文档不重锁；`_open_readonly` 删除；manual en/zh 改会话语义。守卫：
  `test_readonly_session_applies_to_later_opens`（含复用不重锁序列）。*

- [x] **保存拒绝文案误导用户解锁覆盖源文件，且缺正规另存出口（Major）** —
  [`editor.py:510-538`](../../yate/editor.py#L510-L538)
  文案只说拒绝，缺引导；`:saveas` 此前不存在。
  *✅ 已修复（2026-09-26，`1f82fae`）— 文案改引导 `:saveas`；新增 `:saveas` 命令 +
  `Editor.save_as`（vim `:sav` 语义：提交时先解锁再写、写失败回滚标志）；manual en/zh
  补 `:saveas` 行与命令速查。守卫：`test_readonly_saveas_writes_elsewhere_and_unlocks`
  （源文件不动、缓冲解锁、后续 `:w` 写新路径）。附带发现：首版命令描述含 `t-h-e-m-e`
  模糊子序列，使命令面板输入 "theme" 多匹配一条、既有 `filtered_count == 1` 断言失败，
  描述已改写规避。*

- [x] **`Document.save()` 可被扩展直调绕过只读（Major）** —
  [`document.py`](../../yate/editor_core/document.py)
  评审建议仅"文档注明"；实读确认后收紧。
  *✅ 已修复（2026-09-26，`1f82fae`）— L0 护栏：只读时抛 `BufferReadOnlyError`（扩展
  `api.doc.save()` 无法再绕过）；扩展文档注记改为"先解标志再持久化（`:saveas` 即如此）"。
  守卫：`test_save_refused_on_read_only_document`。*

- [x] **`execute_action` 捕获只读异常后未刷新 UI（Minor）** —
  [`editor.py:677-679`](../../yate/editor.py#L677-L679)
  *✅ 已修复（2026-09-26，`1f82fae`）— 补 `refresh_ui()`（被拒动作可能在抛错前移动光标/
  改变锚点）。*

- [x] **`accept_completion` 与按键路径处理不对称（Minor）** —
  [`editor.py:1282`](../../yate/editor.py#L1282)
  *✅ 已修复（2026-09-26，`1f82fae`）— 补 `refresh_ui()`；popup 在写缓冲前已关闭，
  异常时无状态残留（复核属实）。*

- [x] **readonly 与 show_hidden 布尔解析约定分裂（Minor）** —
  [`commands.py:125`](../../yate/commands.py#L125)
  *✅ 已修复（2026-09-26，`1f82fae`）— 抽模块级 `_TRUTHY`/`_FALSY` + `_parse_bool` 两分支
  共用；show_hidden 非法值由静默按 False 改为警告。*

- [x] **`icons.py` 注释字形丢失（Low）** —
  [`icons.py`](../../yate/editor_view/icons.py)
  PLUG/LOCK 注释只剩 `#  (说明)`——评审工具不渲染 Nerd Font 字形所致。
  *✅ 已修复（2026-09-26，`1f82fae`）— 脚本恢复 `# <字形> (说明)` 约定（repr 验证码位）。*

- [x] **测试硬编码 `"\uf023"` 且状态栏文本拼接重复（Low）** —
  [`test_app_textual.py`](../../tests/test_app_textual.py)
  *✅ 已修复（2026-09-26，`dd47be0`）— 断言改引 `icons.LOCK`；新增 `_status_strip` helper
  去重。（评审改进2「`name_budget` 漏减」与本地自查同一条，评审基于旧 HEAD，已去重。）*

### 排查后排除的项（记录以防重提）

- **护栏先于 no-op 早退**：空 undo 栈按 `u`、空寄存器 `p`、末行 `J` 等本应静默 no-op 的
  键也会触发只读警告。2/2 验证者一致判定为**合理设计**——入口统一拦截保证无部分写入，
  与 vim E21 行为一致，无状态损坏，不列缺陷。
