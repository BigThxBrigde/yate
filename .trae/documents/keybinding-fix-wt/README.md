# Windows Terminal 键位修复（IKH1RA）· 子计划总纲

> 上位文档：`../wt_keybinding_fix_plan.md`（根因与决策）；根治路线见 `../win_keybinding_plan.md`
> 分支 / worktree：`issues/keybinding-fix-wt` @ `d:/Programming/yate-keybinding-fix-wt`
> 状态：**SP1–SP5 自动化部分已实施**（2026-09-26；仅剩 SP5 真机矩阵待用户手动执行）
>
> | SP | 状态 | commit |
> |---|---|---|
> | 计划基线 | ✅ | `a9174fc` docs(keybinding): restore and calibrate |
> | SP1 映射修复 | ✅ 255 定向 passed，pyright 0 | `b03e40f` fix(keymap): map ctrl+underscore to 0x1f |
> | SP2 诊断日志 | ✅ pyright 0 | `ff3cfc0` feat(editor): log unmapped key events |
> | SP2 pilot 守卫 | ⚠️ 150 passed；但反向演练有缺陷：注释 ctrl+p 全局分支后守卫仍绿（vsc 键位下 pilot 走 keymap raw 路径，测不到分支存在性）——缺陷分析与重建见 PLAN_B_v2 §A3 | `678c02c` |
> | SP3 文档标注 | ✅ 全量 1228 passed, 7 skipped | `f26e65d` docs(manual): note terminal compatibility |
> | SP4 文档回填 | ✅ review.md + P2 N8 + 本批状态回写 + issue 回复草稿 | `ebee085` docs(keybinding): backfill IKH1RA disposition |
> | SP5 门禁 | ✅ pyright 全仓 0 诊断 · 全量 1228 passed, 7 skipped · 架构守护 13 passed · 冒烟 88/88 场景 · 917/917 checks · exit 0 | — |
> | SP5 真机矩阵 | ⚠️ **部分不符**（2026-09-26 实测：vim 下仅 ctrl+q 恢复，ctrl+p / ctrl+/ 仍失效）→ 新根因与重排计划见 **[PLAN_B_v2_key_reachability.md](PLAN_B_v2_key_reachability.md)** | — |

> **🧭 2026-09-28 文档-代码核对复核**（上表为 2026-09-26 时点值，本次实测）：
> `python -m pytest tests/ --collect-only` → **1354 tests collected**，`python -m pytest tests/ -q` exit 0；
> `pytest tests/test_architecture.py` → **20 passed**（上表"架构守护 13 passed"为当时值）；
> `python -m pyright yate/ tests/ tools/` → 0 errors / 0 warnings / 0 informations；
> `python -m tools.smoke_test run --fail-only` → **89/89 场景、932/932 checks**（当时 88/88、917/917）。
> 另：SP1 独占的 `yate/editor_view/keys.py` 已随 PB1 整体迁入 `yate/keyproto/legacy.py`（见下表注）。

> **🔄 2026-09-26 Phase B 启动**：Phase B 完成后即可修复物理层键——ctrl+数字（无事件行）、
> ctrl+`↔ctrl+space NUL 碰撞（`editor.py:587` 现状取舍：编辑器聚焦→补全、终端聚焦→关终端）、
> ctrl+e/ctrl+shift+e 区分、alt+digit。执行顺序 PB1（keyproto L0 包）→ PB2.0（XTermParser
> win32-input-mode 帧探测，定轻量协议 or 自建驱动）→ PB2（驱动 chord 交付）→ PB3（`key_protocol`
> 配置）→ PB4（文档）→ PB5（矩阵复测+发布）。步骤见 [PLAN_v3_steps.md](PLAN_v3_steps.md)。
> Phase A 合计 6 commits：`5a73fc7` `1d1f3d8` `34ab059` `beea5e0` `1db6175` `d56e43a`。
>
> **✅ 2026-09-26 Phase B 主体完成**（PB1/PB2/PB3/PB4/PB5-r1/PB6）：
> `5cd97d1` `ce93090` `33f91e5` `c9713df` `54ab508` `b246fa5` `afaf000` `7b08070` `fe4d92c`。
> PB6 起启用 **win32-input-mode（`CSI ?9001h`）无损帧解码**（`keyproto/frames.py`），真机
> 无人值守验收（SendInput 注入真实 WT + YATE_TRACE 断言）**12/12 PASS**：x/down/ctrl+p/
> ctrl+shift+e（与 ctrl+e 区分）/ctrl+1（legacy 无法送达）/ctrl+space（独立命名）/ctrl+\`
> （终端开关）全部到达且单触发，ctrl+q 正常退出。ctrl+space 悖论结论（IME 拦截 + 时间交叠
> 归因）在真机复现实锤。运行细节与抓到的缺陷（key-up 帧误判双触发等）见
> [PLAN_v3_steps.md](PLAN_v3_steps.md) 执行状态表 PB6 行。**剩 PB5 三终端矩阵**：
> WT 已由 harness 覆盖，conhost / VS Code 待人工复测。

## 执行顺序与测试门禁（铁律）

```
SP1 ──► SP2 ──► SP3 ──► SP4 ──► SP5
 映射    派发    文档    回填    总门禁
```

1. **严格串行**：上一个 SP 的「验收标准」全部通过并 git commit 后，才能开始下一个 SP。
2. **每个 SP 自带测试**：SP 内"实施步骤"完成后必须先跑该 SP 的「测试」节命令，全绿才允许提交；
   提交信息按 `type(scope): subject`（英文，见 `.trae/rules/git-commit-message.md`）。
3. **每 SP 一个 commit**：出问题时可精确回滚单步（`git revert <sha>`），禁止跨 SP 混合提交。
4. **禁止顺手改**：只改该 SP「独占文件」清单内的文件；发现清单外的必要改动 → 停下记录到该 SP 的"遗留项"，由总纲统一裁决。

## 环境

- worktree 无独立 `.venv`，统一用主仓解释器（PowerShell，cwd = worktree 根）：
  ```powershell
  d:\Programming\yate\.venv\Scripts\python.exe -m pytest tests\test_app_textual.py -q
  ```
- 类型门禁：`d:\Programming\yate\.venv\Scripts\python.exe -m pyright yate tests tools`
- 手动验证：在 worktree 目录 `.venv\Scripts\` 不存在时用 `d:\Programming\yate\.venv\Scripts\python.exe -m yate`（或先 `python -m venv .venv && pip install -e .[dev]` 建本地环境）。

## 子计划索引

| 文件 | 内容 | 独占文件 |
|---|---|---|
| [SP1_ctrl_slash_mapping.md](SP1_ctrl_slash_mapping.md) | `ctrl+/`（`\x1f`→`ctrl+underscore`）映射修复 + help 显示修复 | `yate/keyproto/legacy.py`（**2026-09-28 核对：原写 `yate/editor_view/keys.py`，该模块已随 PB1 迁入 keyproto 并删除**）、`yate/keymaps/base.py`、两个测试文件 |
| [SP2_dispatch_guards_diag.md](SP2_dispatch_guards_diag.md) | `ctrl+p`/`ctrl+1`/`ctrl+shift+e` pilot 回归守卫 + 未映射键诊断日志（D2） | `yate/editor.py`、`tests/test_app_textual.py` |
| [SP3_manual_terminal_notes.md](SP3_manual_terminal_notes.md) | manual 中 `ctrl+1` 等键的终端兼容性标注（D1=A） | `yate/resources/manual.*.md`、README 键位段 |
| [SP4_docs_backfill.md](SP4_docs_backfill.md) | review.md 回填、P2 N8 关账、Gitee issue 回复草稿 | `.trae/issues/review.md`、`.trae/documents/code-review-fix-plans/P2_nice_to_have_plan.md`、本目录文档 |
| [SP5_gates_matrix.md](SP5_gates_matrix.md) | 全量门禁（pyright/pytest/冒烟）+ 真机验证矩阵 + 计划状态收尾 | `.trae/documents/**`（状态回写） |

> **分支评审（2026-09-27）**：本分支全量 diff 评审报告（2 项发现已闭环 `b21ff37`、
> 门禁实测 1257 passed / 覆盖率 90% / 冒烟 920 checks、按键管线与日志守卫流程图存档）见
> [../../review/2026-09-27-keybinding-branch-review.md](../../review/2026-09-27-keybinding-branch-review.md)
> （**2026-09-28 核对修正**：原链接 `../../issues/review_keybinding_20260927.md` 已失效——
> `.trae/issues/` 目录整体迁至 `.trae/review/`，该文件重命名为 `2026-09-27-keybinding-branch-review.md`）。

## 前置（可选）：SP0 真机取证

若对根因推断有疑，先在真实 WT 下启用 `YATE_TRACE=1` 按 `ctrl+1` / `ctrl+/` / `ctrl+p`，
确认到达的 `event.key` 形态与 `../wt_keybinding_fix_plan.md` §2.1 表格一致，再开工 SP1。
无出入则跳过。

## 已核实的关键事实（实施不再复测）

> **2026-09-28 核对**：本节是**实施前**的根因快照；其中 2、3 两条描述的缺陷**均已修复**（见行内注），
> `ctrl+1` 一条也已由 PB2/PB6 改写。保留原表述作为历史取证，不要按现状理解。

- Textual 8.2.8 `XTermParser`：`b"\x1f"` → `Key("ctrl+underscore")`；`b"\x10"` → `ctrl+p`；`b"\x11"`/`b"\x17"` → `ctrl+q`/`ctrl+w`。
- `textual_key_to_raw("ctrl+underscore")` 当前返回 `None`（`_CTRL_PUNCT` 无此键）→ 键被静默丢弃。
  **（2026-09-28 核对：已修复——`yate/keyproto/legacy.py:28` 已登记 `"underscore": 0x1F`，
  该函数现在返回 `"\x1f"`；注意模块已从 `editor_view/keys.py` 迁入 `keyproto/legacy.py`。）**
- `key_name("\x1f")` 当前返回原始控制字符（`KEY_ALIASES` 无条目）→ help 面板乱码。
  **（2026-09-28 核对：已修复——`yate/keymaps/base.py:85` 已登记 `"\x1f": "ctrl-/"`，现返回 `<ctrl-/>`。）**
- `ctrl+p` 已修（`Editor.handle_key` L624 分支；**2026-09-28 核对：现 `editor.py:696`**）；
  `ctrl+1` 物理不可达（WT 无 kitty 协议 + Textual 不读修饰键）。**（2026-09-28 核对：legacy 路径
  仍然成立；和弦驱动 + win32-input-mode 帧解码（PB2/PB6）后 WT 下已可达，见 `PLAN_v3_steps.md` PB6 行。）**
- `editor.py:73` 已有 `log = tracing.get_logger(__name__)`，D2 诊断日志零新增依赖。
  **（2026-09-28 核对：现 `editor.py:74`。）**
