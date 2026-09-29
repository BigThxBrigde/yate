# plan-a：旧方案文档改名迁移（docs）

> 所属总纲：[overview.md](overview.md) · wave-1（与 plan-b 并行，文件零重叠）
> 依据：doc-naming.md 新版（连字符强制）：主计划 `<task>-plan.md`、子计划目录
> `<task>-plans/`、子计划 `<task>-<subtask>-plan-<a|b|c...>.md`、总纲 overview.md。

## 一、输入与独占文件

`.trae/documents/editor-refactoring_plans/` 现存 6 份（IKIPP2 五波方案，目录名
既有连字符风格保留）：

| 现名 | 新名 |
|---|---|
| `README.md` | `overview.md` |
| `plan_A_assembly.md` | `editor-refactoring-assembly-plan-a.md` |
| `plan_B_lsp_sync.md` | `editor-refactoring-lsp-sync-plan-b.md` |
| `plan_C_shell.md` | `editor-refactoring-shell-plan-c.md` |
| `plan_D_overlays.md` | `editor-refactoring-overlays-plan-d.md` |
| `plan_E_prompt_flows.md` | `editor-refactoring-prompt-flows-plan-e.md` |

另修正全仓指向旧名的链接文本（预期仅这几份互链；规则文件引用的是
`app-layering-refactoring-plans/`，不受影响）。

## 二、步骤

1. 逐个 `git mv`（保留历史）。
2. 修正 6 份文档内部互链与 `overview.md` 索引表。
3. 全仓 grep 校验旧名残留，命中逐处修正。
4. 提交：`docs(plans): rename editor refactoring plans to the naming convention`。

## 三、验收命令（退出码 1 = 无命中即通过）

```powershell
git grep -n -I "plan_A_assembly|plan_B_lsp_sync|plan_C_shell|plan_D_overlays|plan_E_prompt_flows" -- .trae
git grep -n "editor-refactoring_plans/README" -- .trae
Get-ChildItem .trae/documents/editor-refactoring_plans
```

## 四、风险与回滚

链接遗漏 → 双模式 grep 兜底；误改外部引用 → 独占清单限定；回滚 = 单笔
`git revert`（git mv 保历史）。
