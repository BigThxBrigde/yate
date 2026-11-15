# IKUOAM issue material (2026-11-12 re-run)

Source: <https://gitee.com/jermaine/yate/issues/IKUOAM>
Fetched: 2026-11-12, unattended session. Issue state on Gitee: 待办的 (open),
0 comments, label `feature`, created 2026-11-11 19:51. The body ends with a
reference to #IKUCKM (the roadmap issue whose P0 first item is macro record
and replay); no new requirements were added in comments.

Title: FEAT - 宏录制与回放（VIM/VSC 统一同一套按键与命令）

## 背景

编辑器缺少宏能力，重复性编辑（批量改行、重复粘贴结构）只能靠多光标或手动重复。
需要支持「录制一段按键序列 → 回放 N 次」的经典宏语义，且 **vim 与 vsc 两套键位
必须使用同一套按键与命令**，避免两套表各自漂移。

## 功能需求

1. **录制**
   - 开始录制：指定单字符寄存器名（`a-z0-9`）；开始后进入录制态，状态栏出现
     录制指示（如 `rec @a`，复用 statusbar 模式 chip 旁的刷新通道）。
   - 停止录制：再次触发录制开关即停止，序列存入对应寄存器（同名覆盖）。
2. **回放**
   - 回放指定寄存器的按键序列，支持 count 前缀语义（回放 N 次，N 缺省 1）。
   - 支持「重复上次回放」。
   - 回放期间再次触发回放必须被拒绝或排队，禁止无限递归（防护上限）。
3. **录制内容**：原始键弦序列（raw key chords），回放时经当前活跃 keymap
   重新派发——录制什么就重放什么，不做高层操作抽象。
4. **寄存器存储**：会话级（内存），跨标签共享；不持久化、不落盘。

## 统一键位（硬性要求）

- vim / vsc 两套 keymap 的宏按键 **必须是同一套键弦、同一组动作**：
  键弦常量定义在 `yate/keymaps/keys.py`（对齐 `HOVER_DOC_KEY = "<f7>"` 先例），
  `vim.py` 与 `vsc.py` 的 `build_bindings()` 均只引用常量、禁止字面量。
- `:` 命令提供等价入口（录制/停止/回放/重复），两套 keymap 下行为一致。
- 需新增键位漂移守卫用例（对齐 `test_hover_key_is_shared_and_identical`）：
  AST 断言两侧 `build_bindings()` 引用共享常量且无宏键字面量；运行时断言
  两套表同一 raw 键解析到同一动作名。
- 键弦选择约束：不得与既有占用冲突（`<f7>` hover、`<f9>` which-key 等），
  避免部分终端吞键的组合键；具体键弦在方案文档定稿。

## 架构落点（对齐架构边界规则）

- 宏寄存器状态归 **L1 `session.py`**（EditorSession 持有，模型状态不进组件层）。
- 录制挂点：按键派发链路（`editor_dispatch.py` 的 `event_to_raw → handle_key`
  一侧）统一捕获 raw 键弦；回放复用同一派发路径，遵守 R10（一次按键只派发一次）。
- 动作注册走 `actions.py::populate()`（R7：外壳装载内置表）；不新增 Protocol。
- 录制指示归 **L2 statusbar 自持**（R13：注入纯数据/回调，不直改样式）。
- which-key 面板如有前缀提示面，需同步登记新键位提示。

## 验收标准

- AC1 录制→停止→回放：回放后缓冲区状态与手动执行同序列按键一致。
- AC2 count 回放：指定 N 次后精确执行 N 次；重复上次回放语义正确。
- AC3 vim 与 vsc 两套表：同一键弦、同一动作名，且键弦来自 `keys.py` 共享常量
  （守卫用例通过，含负向演练：任一侧硬编码字面量会被拦截）。
- AC4 回放中触发回放（直接或间接自递归）被拒绝且有用户可见提示，无死循环。
- AC5 录制态有状态栏指示；停止后指示消失；空寄存器回放给出 warn 提示。
- AC6 寄存器覆盖写入正确（同名再录制覆盖旧内容）；未录制寄存器不干扰。
- AC7 `:` 命令入口与按键入口行为一致；非法寄存器名 / 语法错误有明确报错。
- AC8 `python -m pyright yate/ tests/ tools/` 零诊断；
  `python -m pytest tests/ -q -n auto` 全绿，含新增架构守卫。

## 暂不做（v1 范围外）

- 寄存器持久化（跨会话保存宏）。
- 回放合并为单步 undo（v1 跟随自然 undo 粒度，是否原子化在方案阶段评估）。
- 宏编辑 / 查看 / 寄存器列表 UI。
- 跨寄存器嵌套录制（录制中调用其它寄存器回放）。

## 备注

- 实施需按闭环流程先出方案文档（`.trae/documents/macro-record-plan.md`，
  大任务拆子计划），批准后执行。
- 双语手册（`yate/docs/manual.en.md` / `manual.zh.md`）与键位文档需同步更新
  （doc-conventions §三：双语同时新增、同时更新）。

## 只读情报（本轮【领会】整理，不含方案结论）

- 本地 `master` HEAD `be6b4a54`，与 `origin/master` 同步（0/0）；本轮新建
  worktree `yate-macro-record-replay-unified` / 分支
  `feature/feat-macro-record-replay-unified`，parent 为该 `master`。
- 本机另有一个**未合流、未推送**的分支 `feature/feat-macro-record-replay`
  （worktree `yate-macro-record-replay`，14 提交，末笔 `c80daf58`），其产物为
  同一 issue 的上一轮实现：主计划 `macro-record-replay-plan.md`、素材
  `macro-record-replay-issue.md`、进度 `macro-record-replay-progress.md`、
  子计划目录 `macro-record-replay-plans/`（总纲 `overview.md` + a..e）。
  该分支未出现在 `origin/master` 中，故本轮 `master` 基线上没有宏能力。
- 上一轮进度记录登记的两条 MINOR（登记不修）：`:macro-play`/count 无上限
  同步阻塞；录制序列无界。登记的两条教训：键位比较必须过 `parse_key` 取 raw；
  冒烟场景 `unknown_command_and_action` 借 `<f10>`（`<f6>` 已被宏占用）。
- 上一轮收尾门禁数字（时点事实，本轮须独立复跑）：pyright 0 /
  pytest 3621 passed·10 skipped / 架构 38 / 覆盖率 92.98% /
  冒烟 123/123·1493 checks / changelog 0 / diffcheck 双 0。
- 主工作区（主仓根）存在两处**本轮不触碰**的未提交改动：
  `yate/resources/changelog.en.md` 与 `changelog.zh.md`（生成器刷新产物）。
- 用户指令（2026-11-12）：无人值守、无须过问；严格按纪律闭环；唯一例外是
  全程使用 Hy4 模型，若 Hy4 限流则切换 GLM-5.3-Flash。
