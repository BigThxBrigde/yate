# SP5 — 全量门禁 + 真机验证矩阵 + 收尾

> **实施状态**：🟡 部分实施 —— 2026-10-05 全量核对：自动化部分已实施；SP5 真机矩阵待人工（同上速览 #10）。
> ⚠️ 本计划**仅部分落地**，未完成部分见正文，引用产物前请先确认其存在。
> 预估：40min　|　独占文件：无产品代码（只跑门禁、记录结果）

## 目标

合并前最后一道关：全量自动化门禁 + 真实终端手动矩阵 + 架构守护确认。

## 门禁（全部必须通过）

```powershell
.venv\Scripts\python.exe -m pyright yate tests tools
$env:PYTHONDONTWRITEBYTECODE='1'; .venv\Scripts\python.exe -m pytest tests\ -q
.venv\Scripts\python.exe -m pytest tests\test_architecture.py -q   # 13 passed
                                                                                        # 2026-09-28 核对：现 20 passed
```

- pyright：**0 诊断**（合并硬门槛）；
- pytest：全绿；偶发失败先重跑确认（并发 pilot 干扰史），不许直接改断言；
- 架构守护：13 用例通过（R2/R3/R6/命名守卫等未被触碰）。**（2026-09-28 核对：实测 20 个用例——
  此后 R12/R13、日志惰性格式、T1/T2 治理等守卫陆续加入。）**

## 冒烟（Textual pilot harness）

用 `textual-pilot-smoke` 技能或 `tools/smoke_test` 跑键位相关场景：
keymap 切换（`ctrl+/`）、quick open（`ctrl+p`）、explorer/editor 焦点切换（`ctrl+shift+e`/`ctrl+1`）。

## 真机验证矩阵（手动，逐项勾选）

> **助手脚本**：[verify_matrix.ps1](verify_matrix.ps1) —— 在**被测终端**里运行
> `powershell -ExecutionPolicy Bypass -File .trae\documents\keybinding-fix-wt\verify_matrix.ps1`：
> 阶段一自动逐键捕获控制台上报的字符码/修饰键（根因取证：ctrl+1 应看到 `0x31 + Control`），
> 阶段二按下方矩阵逐项启动 yate 引导作答，结果写入同目录 `matrix_results.md`，回填本文件后可删除脚本。
> 注意：脚本为 UTF-8 with BOM（PowerShell 5.1 兼容），编辑后需保留 BOM。

在**真实终端**运行 yate（pilot 测不到终端字节层，此矩阵不可省略）。
vim / vsc 两键位各过一遍（`ctrl+/` 切换键位本身即 SP1 的验证）：

**状态：⏳ 待验证**（2026-09-26）——自动化门禁已全绿（见收尾清单），仅剩本表；
用 [verify_matrix.ps1](verify_matrix.ps1) 执行，每终端跑完后把 `matrix_results.md` 的结论按下表回填
（☐ 待验 / ✅ 符合预期 / ❌ 不符，❌ 必须附现象描述）：

| 键 | 期望 | WT | conhost | VS Code 终端 |
|---|---|---|---|---|
| `ctrl+/`（键位切换） | 两键位间来回切换 | ☐ | ☐ | ☐ |
| `ctrl+p`（文件面板） | 面板打开（vim/vsc 双键位） | ☐ | ☐ | ☐ |
| `ctrl+q` / `ctrl+w` | 退出 / 关标签（回归） | ☐ | ☐ | ☐ |
| `ctrl+shift+e` / `ctrl+1` | 焦点 explorer / editor（`ctrl+1` 见下行） | ☐ | ☐ | ☐ |
| `ctrl+1`（WT/conhost） | **预期失效**（已文档化）；验证替代路径 `alt+shift+p` 可达 | ☐ | ☐ | n/a |

阶段一取证参考（脚本自动打印，人工核对）：`ctrl+p/q/w` → `0x10/0x11/0x17`；`ctrl+/` → `0x1F`；
`ctrl+1` 在 WT/conhost/VS Code → `0x31 + Control`（修饰丢失证据，与根因分析一致即通过）。

## 收尾清单

- [x] 门禁三项全绿（2026-09-26 实测：全量 pytest **1228 passed, 7 skipped** / pyright 全仓 **0 诊断** / 架构守护 **13 passed**；冒烟 **88/88 场景 · 917/917 checks · exit 0**，见 keybinding-fix-wt-plans/overview.md 状态表）；
  **2026-09-28 复核：全量收集 1354、exit 0；pyright 0 诊断；架构守护 20 passed；冒烟 89/89 场景 · 932/932 checks · exit 0。**
- [ ] 真机矩阵勾完，与期望一致（`ctrl+1` 在 WT/conhost 的失效属预期）——**待验证**，用 [verify_matrix.ps1](verify_matrix.ps1) 在 WT / conhost / VS Code 终端各跑一遍，产出 `matrix_results.md` 后回填下表；
- [x] commit 历史整洁（每 SP 一个 commit，`git log --oneline` 核对：`a9174fc`→`b03e40f`→`ff3cfc0`→`678c02c`→`f26e65d`→`ebee085`→`3a8a29b`）；
- [ ] push 前询问用户；如用户要求，发起 PR 并在描述中链接 Gitee issue IKH1RA 与三份计划文档；
- [ ] 方案 B 启动提醒：下一步是 `win-keybinding-protocol-plan.md` P0（探针），其子计划届时按本目录同风格生成。

## 回滚

本 SP 无代码变更；如门禁失败，回到对应 SP 修复后重跑，不得在本 SP 内打补丁。
