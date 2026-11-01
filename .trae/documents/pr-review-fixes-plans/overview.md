# pr-review 修复波总纲 — feat/file-manager（2026-11-01）

**来源**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md`
（Overall: BLOCKED — 1 blocker / 1 major / 11 minor）。
**裁决**（pr-review 三档处置）：

- 本 PR 必修：**B1 + M1 + m1 + m2 + m3 + m4 + m6 + m7**（本文档三个子计划）。
- 登记后另案（can-defer，不在本波实现）：m5（预览装配去重）、m8（`alt+shift+f` 改走
  `execute_action`）、m9（`is_mounted` → `is_attached`，palette 两处同形）、
  m10（nav 重映射补 pilot 用例）、m11（目录预览记忆化，并入「中栏万级条目增量刷新」立项）。

## 子计划与文件互斥

| 子计划 | 修的条目 | 独占文件 |
|---|---|---|
| [prfix-ws.md](prfix-ws.md) | B1 | `yate/services/workspace.py`、`tests/test_workspace_filemgr.py` |
| [fix-fm.md](fix-fm.md) | M1、m3、m4、剪切回归用例 | `yate/editor_view/filemgr.py`、`yate/editor_view/filemgr_model.py`、`tests/test_filemgr.py`、`tests/test_filemgr_model.py`、`yate/docs/file-manager.en.md`、`yate/docs/file-manager.zh.md` |
| [fix-cli.md](fix-cli.md) | m1、m2、m6、m7 | `yate/commands.py`、`tests/test_cmd_cd.py`、`yate/flows/filemanager_flows.py`、`yate/cli.py`、`tests/test_app_filemgr.py`（m6 用例如实际在 `tests/test_cli.py` 等其他文件，也归本批独占）、`yate/resources/manual.en.md`、`yate/resources/manual.zh.md` |

三批文件集互不重叠，可并行执行。禁止触碰上表之外的任何文件（评审记录本身不修改）。

## 硬约束

1. pyright strict **零诊断**；完整类型注解 + docstring；禁 `Any` / `Protocol` / `TYPE_CHECKING`。
2. 代码注释、docstring、`file-manager.en.md` / `manual.en.md` 用英文；`file-manager.zh.md` /
   `manual.zh.md` 用中文。行宽 ≤100。
3. 架构边界不动：`filemgr.py` 只收 `Workspace`/`FilePreviewConfig`/回调；flows 不持 App 句柄；
   不新增 yate 内部跨层导入。
4. 「先红后绿」：凡新增回归用例，先跑一次确认**红**（抓到缺陷），再修实现转绿；把
   红证据（报错摘要）写进最终汇报。B1 用例先红演练**只跑一次**（`-k` 单选），避免在
   pytest tmp 反复留下 500 层垃圾树；**不要**主动清理 `%TEMP%` 积压垃圾（主代理处理，
   本机 safe-delete 钩子会拦截大批量删除进程）。
5. 每批自测命令见各自子计划；不许只跑新用例，至少跑该批全部关联测试文件。
