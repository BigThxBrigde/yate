# 子计划 fix-navtest — m10 中栏 `nav()` 重映射补 pilot 用例

**Worktree 根**：`D:\Programming\yate-file-manager`（分支 `feat/file-manager`）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 m10（先读全文）。
**时序**：本批必须在 fix-preview 批落盘之后执行（用例跑在其改动后的
`filemgr.py` 上）。

## 独占文件

- `tests/test_filemgr.py`

## 修改点

补一条（或一组）pilot 回归用例，覆盖 `_FileListView.action_nav` 六路分派中
当前零覆盖的 `left` / `right` / `home` / `end` / `pageup` / `pagedown`
（评审实测缺失行 `109-121`，行号为评审时点，按内容定位）：

- `right`：光标停在**目录**条目上时进入该目录（不要停 在文件上按 right，
  那会触发 R3 打开语义）；
- `left`：从子目录返回父目录，光标落在原目录项上（lf 语义）；
- `home` / `end`：光标到首行 / 末行；
- `pageup` / `pagedown`：先读 `_FileListView.action_nav`（`yate/editor_view/filemgr.py`
  95-121 附近，按内容定位）与 `yate/editor_view/filemgr_keys.py` 的
  `LIST_BINDINGS`，确认重映射到的屏幕动作与语义后**按实际行为断言**，
  不得凭猜测写期望值。

写用例前先读 `tests/test_filemgr.py` 既有 pilot 构造方式（fixture、
`conftest.wait_until` 轮询、临时目录布局、Windows-only 用例的构造先例），
完全沿用既有风格；零真实 `sleep`。断言用的临时目录自建，不在真实盘根上操作。

## 自测

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/        # 0 诊断
.venv\Scripts\python.exe -m pytest tests/test_filemgr.py -q -n auto
```

全绿按退出码判定。

## 执行纪律

- 只改 `tests/test_filemgr.py`；产品源码零改动（m10 就是补覆盖）。
- 完成后**不提交**，汇报：新增用例名与断言要点、自测命令与退出码。

## 执行偏离记录（先红后绿，2026-11-01 主代理裁决）

新用例落盘后首跑**红**，且红因是**真实产品缺陷**而非用例错误：

- 红证据（主代理亲跑 `pytest tests/test_filemgr.py -q -n auto`）：按 `end` 触发
  绑定 `nav(bottom)` → `ActionError: unable to parse 'bottom' in action
  'nav(bottom)'`——Textual 8.2.8 的动作解析器拒绝裸单词参数，六条重映射绑定
  （left/right/home/end/pageup/pagedown）在真实应用中同样派发失败。
- 补充实证（fix-navtest 批独立复核，与主代理结论一致）：解析失败根源是
  Textual 以 `ast.literal_eval` 解析 action 参数（`.venv` 内
  `textual/actions.py:46`），探针 `parse("nav(bottom)")` 必抛、
  `parse("nav('bottom')")` 正常；端到端探针显示列表聚焦态按六键会置位
  `app._exception` 且应用停摆——生产严重度高于 m10 原判的「零覆盖」，
  实为六键派发全坏（疑似崩应用，同 B1 的 `App._handle_exception` 路径）。
- 修复（**主代理亲自执行**，偏离本计划「产品源码零改动」条款；子代理不得改
  产品源码，缺陷由主代理裁决处置）：`yate/editor_view/filemgr_keys.py`
  `LIST_BINDINGS` 六条绑定的 `nav(...)` 参数全部加引号（`nav('bottom')` 等），
  并在表头注释记录该解析约束。修复文件归本批名下。
- 绿证据：修复后 pyright 0 诊断；`pytest tests/test_filemgr.py -q -n auto`
  26 项全过（含新用例），退出码 0。
