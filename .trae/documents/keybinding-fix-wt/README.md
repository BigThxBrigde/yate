# Windows Terminal 键位修复（IKH1RA）· 子计划总纲

> 上位文档：`../wt_keybinding_fix_plan.md`（根因与决策）；根治路线见 `../win_keybinding_plan.md`
> 分支 / worktree：`issues/keybinding-fix-wt` @ `d:/Programming/yate-keybinding-fix-wt`
> 状态：**SP1–SP3 已实施**（2026-09-26；SP4 文档回填随本批提交，SP5 真机矩阵待用户执行）
>
> | SP | 状态 | commit |
> |---|---|---|
> | 计划基线 | ✅ | `a9174fc` docs(keybinding): restore and calibrate |
> | SP1 映射修复 | ✅ 255 定向 passed，pyright 0 | `b03e40f` fix(keymap): map ctrl+underscore to 0x1f |
> | SP2 诊断日志 | ✅ pyright 0 | `ff3cfc0` feat(editor): log unmapped key events |
> | SP2 pilot 守卫 | ✅ 150 passed（含反向演练：注释 ctrl+p 分支守卫捕获缺失） | `678c02c` test(editor): pin global chord dispatch branches |
> | SP3 文档标注 | ✅ 全量 1228 passed, 7 skipped | `f26e65d` docs(manual): note terminal compatibility |
> | SP4 文档回填 | ✅ review.md + P2 N8 + 本批状态回写 | （本 commit） |
> | SP5 门禁+真机矩阵 | ⏳ pyright/pytest/架构守护待终跑；真机矩阵需用户在 WT/conhost/VS Code 手动勾选 | — |

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
| [SP1_ctrl_slash_mapping.md](SP1_ctrl_slash_mapping.md) | `ctrl+/`（`\x1f`→`ctrl+underscore`）映射修复 + help 显示修复 | `yate/editor_view/keys.py`、`yate/keymaps/base.py`、两个测试文件 |
| [SP2_dispatch_guards_diag.md](SP2_dispatch_guards_diag.md) | `ctrl+p`/`ctrl+1`/`ctrl+shift+e` pilot 回归守卫 + 未映射键诊断日志（D2） | `yate/editor.py`、`tests/test_app_textual.py` |
| [SP3_manual_terminal_notes.md](SP3_manual_terminal_notes.md) | manual 中 `ctrl+1` 等键的终端兼容性标注（D1=A） | `yate/resources/manual.*.md`、README 键位段 |
| [SP4_docs_backfill.md](SP4_docs_backfill.md) | review.md 回填、P2 N8 关账、Gitee issue 回复草稿 | `.trae/issues/review.md`、`.trae/documents/code-review-fix-plans/P2_nice_to_have_plan.md`、本目录文档 |
| [SP5_gates_matrix.md](SP5_gates_matrix.md) | 全量门禁（pyright/pytest/冒烟）+ 真机验证矩阵 + 计划状态收尾 | `.trae/documents/**`（状态回写） |

## 前置（可选）：SP0 真机取证

若对根因推断有疑，先在真实 WT 下启用 `YATE_TRACE=1` 按 `ctrl+1` / `ctrl+/` / `ctrl+p`，
确认到达的 `event.key` 形态与 `../wt_keybinding_fix_plan.md` §2.1 表格一致，再开工 SP1。
无出入则跳过。

## 已核实的关键事实（实施不再复测）

- Textual 8.2.8 `XTermParser`：`b"\x1f"` → `Key("ctrl+underscore")`；`b"\x10"` → `ctrl+p`；`b"\x11"`/`b"\x17"` → `ctrl+q`/`ctrl+w`。
- `textual_key_to_raw("ctrl+underscore")` 当前返回 `None`（`_CTRL_PUNCT` 无此键）→ 键被静默丢弃。
- `key_name("\x1f")` 当前返回原始控制字符（`KEY_ALIASES` 无条目）→ help 面板乱码。
- `ctrl+p` 已修（`Editor.handle_key` L624 分支）；`ctrl+1` 物理不可达（WT 无 kitty 协议 + Textual 不读修饰键）。
- `editor.py:73` 已有 `log = tracing.get_logger(__name__)`，D2 诊断日志零新增依赖。
