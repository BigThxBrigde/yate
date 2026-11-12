# 宏录制与回放 进度记录（issue IKUOAM，2026-11-11）

> 【历史产物 · 方案已排除】本组文档记录 2026-11-11 第一轮宏录制回放方案
> （`<f6>` 单前缀 chord：`r` 录制 / `p` 回放 / `@` 重复），其实现**未并入**现行代码。
> 现行实现是 2026-11-12 第二轮方案（`<f10>` / `<f11>` / `<f12>` 三单键，
> 见 `macro-record-replay-unified-progress.md`），键位、API 与命令契约以产品源码为准。
> 本文出现的 `MACRO_PREFIX_KEY`、`pre_dispatch`、`macro_awaiting`、`<f6>` 等符号
> 在现行代码中不存在，**不得**作为开发或施工依据。
> 2026-11-12 合并 `replay` 分支时仅为保留历史轨迹收录本组文档，代码未采纳。

> worktree `D:/Programming/yate-macro-record-replay`，分支
> `feature/feat-macro-record-replay`（parent master `18e96d2a`）。
> 规则 8 份必读已全文加载；无人值守按通过处理；子代理模型按记忆口径
> 11-11..15 统一 Hy4（本机 task 工具无模型参数，frontmatter 生效）。

## 步骤状态

| 步骤 | 状态 | 产物 / 提交 |
| --- | --- | --- |
| 【领会】 | 完成 | issue 素材落盘 `macro-record-replay-issue.md`；worktree+venv 建立（提交 `1c2b9dc6` docs(plan) 素材笔） |
| 【方案】 | 完成 | 主计划 + 总纲 + 5 子计划（提交 `5fa98d1e` docs(plan) 计划笔）；plan-architect-designer 未派发（前轮两模型失败在案，主代理兜底已登记总纲 §六） |
| 【批准】 | 完成 | 无人值守按通过处理（主计划 §11） |
| wave-1 a/b/c | 完成 | 主代理亲改 9 个产品文件；提交 `c37896ca`（a：session+flows）、`31c5b4a8`（b：keys/base/vim/vsc）、`a2a4980b`（c：dispatch/compose/editor + editor.py 豁免） |
| wave-2 d | 完成 | 主代理亲改 5 产品文件 + 测试 helper 同步；提交 `54a71d8a`；方案键弦裁决回填 `6f297c0f` |
| wave-3 测试 | 完成 | 两名 plan-executor 落盘 4 个测试文件（t1：flows+key_binding；t2：commands+app）；主代理独立复核：29 用例全绿、pyright 0、e2e `-n 1` 8 连 0（一次 flake 系与全量并发争抢，串行复核通过）、全量 pytest 过（ASCII 守卫揪出 `§` 一处已修） |
| wave-4 审核+收尾 | 完成 | 详见下方「评审与门禁记录」 |

## wave-4 评审与门禁记录（2026-11-11）

- **评审者判死登记**：spawn `code-review-expert`（bypassPermissions）后
  68 分钟未交付报告（先例约 30 分钟）。可观察产物显示其完成了大量验证
  （覆盖率口径 93.06%、全量 3621 passed、**冒烟 exit 1**）——主代理按
  其冒烟产物自查出 `unknown_command_and_action` 场景借用 `<f6>` 作无绑定
  干净键的前提被宏功能打破（4 断言失效），改借 `<f10>`（同形态 xterm
  序列、两表空闲）修复，冒烟恢复 123/123（`1be94e9`）。评审判死后主代理
  按剧本自查替代并如实登记「子代理零交付」。
- **主代理自查结论**（替代评审，APPROVE 口径）：依赖方向合规
  （macro_flows L3 → session L1 / keys L0，无 editor_components 导入）；
  R10 单点拦截；AC4 回放递归双防护有测试锁定；pyright strict 0；注释
  ASCII；提交按范围 11 笔。**MINOR 登记（v1 设计裁定，不修）**：
  ① `:macro-play`/count 前缀无上限，极大 count 会同步阻塞事件循环
  （同步回放是 issue 允许的 v1 裁定，与 vim 语义一致，用户显式输入）；
  ② 录制序列无大小上限（会话内自然有界）。
- **手册与站外文档**：应用内手册 5.3 节双语（en/zh manual）、站外
  `macros.{en,zh}.md` + README 索引双语（`5f802d2`）；issue 素材尾随
  空白剥离（`3915832`）。
- **收尾七项门禁（主代理亲跑，exit 0 全绿）**：

| 门禁 | 结果 |
| --- | --- |
| pyright yate/ tests/ tools/ pack/ | 0 errors |
| pytest tests/ -q -n auto | 3621 passed / 10 skipped（覆盖率口径内含） |
| pytest tests/test_architecture.py -q | 38 passed |
| pytest --cov=yate --cov-branch -n auto（≥75） | 92.98% |
| tools.smoke_test run --jobs 4 | 123/123 场景 / 1493 checks |
| tools.changelog check | exit 0（unreleased lag 为生成器存量状态） |
| git diff --check master...HEAD + git diff --check | 双 0 |

## wave-3 产品缺陷发现与修复（e2e 揪出，已修）

- **raw 比较缺陷**：`macro_flows.pre_dispatch` 原用键位记法
  `MACRO_PREFIX_KEY`（`"<f6>"`）与 raw 派发串比较，而 `_handle_raw_key`
  传入的是 `parse_key` 规范化 raw（`\x1b[17~`）——控制键永不匹配，e2e
  录制停止断言失败暴露。修复：模块级 `_PREFIX_RAW = parse_key(...)`，
  `pre_dispatch`/`is_control_key` 全部改 raw 比较；单元测试同步喂 raw
  形态（测试与实现此前共用同一错误假设自洽绿——教训：键位比较必须过
  `parse_key`，记法只用于绑定与文档）。

## 关键裁决（偏离总纲 §六）

1. **键弦**：`q`/`@` 可打印前缀 → `<f6>` 单前缀 chord（`r` record /
   `p` play / `@` repeat last），常量 `MACRO_PREFIX_KEY`。理由：vsc 无模式
   编辑器可打印字符是文本输入（存量守卫 `test_colon_is_inserted_literally`
   锁定）；issue 授权方案定稿；AC3 两表同键弦同动作仍满足。
2. **editor.py 豁免**：802 行登记 `SIZE_EXEMPT_FILES`（拆分后恰 800 + 2），
   守卫集合与 `.trae/rules/architecture-boundaries.md` 两处同步。

## 验收实测（主代理独立复核）

- wave-1：pyright 0；架构 + test_vim_keymap + test_editor_core +
  test_app_panes 全绿（190 passed / 1 skip 既有）。
- wave-2：pyright 0；test_whichkey_flows + 架构 56 passed；全量
  `pytest tests/ -q -n auto` exit 0；`tools.changelog check` exit 0。
- wave-3 待两名执行者交付后：4 新测试文件 + pyright + 4×`-n 1` 时序复核 +
  全量。

## 会话范围裁定（其余 open issue）

- IKTRDV：并行会话已在 pack-dist-zip worktree 完成收尾并关闭 issue；本
  会话 wave-1/2 提交被其登记为并发事实，不再介入（防双写）。
- IKU55P：已实现待显式合并，无代码工作。
- IKJLFW（DAP）/ IKQ509（音乐）：大型功能，留待后续会话单线推进。
- IKUCKM：条目随功能逐条闭环（宏 = IKUOAM 本任务）。
