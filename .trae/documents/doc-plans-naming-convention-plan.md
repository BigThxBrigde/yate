# doc_plans_naming_convention_plan

## 目标

统一 `.trae/documents/` 下计划与子计划的命名规范：

- 子计划：`<task>_[subtask]_plan_<a|b|c...>.md`（subtask 视情况省略）；
- 波次标记（SP0-SP4 / P0-P2 / PLAN_B_v2 等）统一转字母序 `a,b,c...`；
- 各子计划目录总纲 `README.md` 一律改名 `overview.md`；
- **目录名不动**（减少引用爆炸）。

## 非目标

- 不改目录名；不合并/改写任何文档内容；
- 不动非计划文件（脚本 `.py` / `.ps1` / `.svg`、回复草稿）；
- 不涉及其它 worktree 分支独有的目录（如 `editor-refactoring_plans/`）。

## 备选方案与否决理由

- **保留 SP/P0 波次标记**：偏离纯字母序规范，用户已否决（2026-09-29 选型）；
- **目录名同步下划线化**：全仓引用更新量翻倍，用户已否决。

## 映射总表（唯一规范来源）

### 根目录（38 个中改 2 个，其余已符合 `<task>_plan.md`）

| 旧名 | 新名 |
|---|---|
| `logging_for_layers_plan.md` | `logging_for_layers_plan.md` |
| `readonly_option_plan.md` | `readonly_option_plan.md` |

### app-layering-refactoring-plans/（task=app_layering_refactoring）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `app_layering_refactoring_leaf_models_plan_a.md` | `app_layering_refactoring_leaf_models_plan_a.md` |
| `app_layering_refactoring_widget_selfhold_plan_b.md` | `app_layering_refactoring_widget_selfhold_plan_b.md` |
| `app_layering_refactoring_functional_tables_plan_c.md` | `app_layering_refactoring_functional_tables_plan_c.md` |
| `app_layering_refactoring_shell_wiring_plan_d.md` | `app_layering_refactoring_shell_wiring_plan_d.md` |
| `app_layering_refactoring_tests_tools_plan_e.md` | `app_layering_refactoring_tests_tools_plan_e.md` |
| `app_layering_refactoring_gate_docs_plan_f.md` | `app_layering_refactoring_gate_docs_plan_f.md` |
| `app_layering_refactoring_pane_model_to_session_plan_g.md` | `app_layering_refactoring_pane_model_to_session_plan_g.md` |

### code-review-fix-plans/（task=code_review_fix）

| 旧名 | 新名 |
|---|---|
| `code_review_fix_critical_plan_a.md` | `code_review_fix_critical_plan_a.md` |
| `code_review_fix_suggestions_plan_b.md` | `code_review_fix_suggestions_plan_b.md` |
| `code_review_fix_nice_to_have_plan_c.md` | `code_review_fix_nice_to_have_plan_c.md` |

### fancy_sym_plans/（task=fancy_sym；roster.svg 不动）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `fancy_sym_sprites_plan_a.md` | `fancy_sym_sprites_plan_a.md` |
| `fancy_sym_rosters_tool_plan_b.md` | `fancy_sym_rosters_tool_plan_b.md` |
| `fancy_sym_config_plan_c.md` | `fancy_sym_config_plan_c.md` |
| `fancy_sym_screen_plan_d.md` | `fancy_sym_screen_plan_d.md` |
| `fancy_sym_docs_plan_e.md` | `fancy_sym_docs_plan_e.md` |
| `fancy_sym_final_plan_f.md` | `fancy_sym_final_plan_f.md` |

### keybinding-fix-wt/（task=keybinding_fix_wt；脚本与 issue_reply_IKH1RA.md 不动）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `keybinding_fix_wt_steps_plan_g.md` | `keybinding_fix_wt_steps_plan_g.md` |
| `keybinding_fix_wt_key_reachability_plan_f.md` | `keybinding_fix_wt_key_reachability_plan_f.md` |
| `keybinding_fix_wt_ctrl_slash_mapping_plan_a.md` | `keybinding_fix_wt_ctrl_slash_mapping_plan_a.md` |
| `keybinding_fix_wt_dispatch_guards_diag_plan_b.md` | `keybinding_fix_wt_dispatch_guards_diag_plan_b.md` |
| `keybinding_fix_wt_manual_terminal_notes_plan_c.md` | `keybinding_fix_wt_manual_terminal_notes_plan_c.md` |
| `keybinding_fix_wt_docs_backfill_plan_d.md` | `keybinding_fix_wt_docs_backfill_plan_d.md` |
| `keybinding_fix_wt_gates_matrix_plan_e.md` | `keybinding_fix_wt_gates_matrix_plan_e.md` |

> 说明：该目录两轮执行（SP1-SP5 → a-e，PLAN_B_v2 → f，PLAN_v3 总步骤 → g），
> 字母位按执行顺序接续；`wt_keybinding_fix_plan.md`（根，已合规范）仍是主计划。

### python-312-upgrade-plans/（task=python_312_upgrade）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `python_312_upgrade_plan_a.md` | `python_312_upgrade_plan_a.md` |
| `python_312_upgrade_plan_b.md` | `python_312_upgrade_plan_b.md` |
| `python_312_upgrade_plan_c.md` | `python_312_upgrade_plan_c.md` |
| `python_312_upgrade_plan_d.md` | `python_312_upgrade_plan_d.md` |
| `python_312_upgrade_plan_e.md` | `python_312_upgrade_plan_e.md` |

### theme-layer-refactor-plans/（task=theme_layer_refactor）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `theme_layer_refactor_baseline_plan_a.md` | `theme_layer_refactor_baseline_plan_a.md` |
| `theme_layer_refactor_decouple_plan_b.md` | `theme_layer_refactor_decouple_plan_b.md` |
| `theme_layer_refactor_guard_docs_plan_c.md` | `theme_layer_refactor_guard_docs_plan_c.md` |
| `theme_layer_refactor_gate_commit_plan_d.md` | `theme_layer_refactor_gate_commit_plan_d.md` |

### theme-ownership-refactoring-plans/（task=theme_ownership_refactoring）

| 旧名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `theme_ownership_refactoring_theme_broadcast_plan_a.md` | `theme_ownership_refactoring_theme_broadcast_plan_a.md` |
| `theme_ownership_refactoring_scrollbar_injection_plan_b.md` | `theme_ownership_refactoring_scrollbar_injection_plan_b.md` |
| `theme_ownership_refactoring_widget_theme_selfhold_plan_c.md` | `theme_ownership_refactoring_widget_theme_selfhold_plan_c.md` |
| `theme_ownership_refactoring_architecture_guards_plan_d.md` | `theme_ownership_refactoring_architecture_guards_plan_d.md` |
| `theme_ownership_refactoring_gate_docs_plan_e.md` | `theme_ownership_refactoring_gate_docs_plan_e.md` |
| `theme_ownership_refactoring_theme_gap_terminal_message_plan_f.md` | `theme_ownership_refactoring_theme_gap_terminal_message_plan_f.md` |

合计 47 个文件重命名（6 个 `README.md` → `overview.md`，41 个子计划/2 个根文件改名）。

## 分步实施

1. **重命名**：按映射表 `git mv`（保留历史）。
2. **引用更新**：对每个旧名全仓 `grep`（yate 仓库全目录，含 `.trae/`、`tests/`、
   `tools/`），把文件名与相对链接逐一替换为新名；相对路径前缀保持原样只换文件名。
3. **验收命令**：
   - 全仓 `grep` 旧名 → 0 命中（`git grep` 实测）；
   - 链接解析脚本：`.trae/reviews/` + 根 CHANGELOG + 全部 documents 目录的
     markdown 相对链接全部可解析（本次扩展扫描范围到 `.trae/documents`）；
   - `git status` 确认全部为 rename。
4. **提交**：`docs(plans): unify plan and subplan naming convention`。

## 风险与回滚

- 风险：内文叙述性提及旧名（非链接）替换后语义生硬——按同词替换即可，属预期；
- 风险：跨分支引用（master 或其它 worktree 的文档指向这些文件名）——改名仅落在本
  分支，合并后其它分支如有旧名引用，由后续各自分支处理（本分支不越界）；
- 回滚：单提交 revert。

## 执行记录（2026-09-29 回填）

- **重命名 62 个文件**（第一轮 46 + 第二轮补漏 16），git 全部识别为 rename；
- **引用更新 85 个文件**（第一轮 77 + 第二轮 8）；
- **验收实测**：
  - `git grep` 50 个旧名模式 → 0 命中；`<dir>/README.md` 形态 → 0 命中；
    唯一残留是 zh changelog 对**历史提交的描述**（"总纲 README 加 plan_SP0-SP4"，
    当时文件确为该名），按历史记录原貌原则不改，本次改名的 changelog 条目另行记录；
  - 链接基线对比（`git archive HEAD` 导出基线跑同款检查）：HEAD 227 条坏链 →
    工作区 220 条，**本次改动零新增**，顺手修复 8 条；
- **偏离计划 3 条**（均已实测核实）：
  1. `code-review-fix-plans/` 原本就没有总纲 README，overview 改名实际 5 个而非 6 个；
  2. 调研漏网 `code-review-fix-plans/P1_subplans/`、`/P2_subplans/`（各 7 个 SP 子计划
     + 1 个总纲），第二轮补充纳入，命名 `code_review_fix_p1|p2_<topic>_plan_<a-g>.md`；
  3. 顺手修复 8 条历史坏链（`../../issues/review.md` 等指向已拆分 review 的相对路径，
     早前按 `.trae/issues/` 字面量 grep 漏掉的形态）→ 定向到拆分后文件
     （`2026-09-16-full-review.md` / `2026-09-27-ui-refine.md` / `reviews/README.md`）；
- **遗留登记**（未动，历史遗留与本次改动无关）：
  `code_review_fix_p2_editor_dispatch_components_plan_f.md` 内
  `../../../tools/smoke_test/scenarios/integration.py` 层级少一层（HEAD 同坏）。
