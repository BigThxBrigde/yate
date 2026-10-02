# yate Code Review — Gitee PR #46 评审（remove-inline-default-css 分支）— 2026-10-02

## Gitee PR #46 评审（remove-inline-default-css 分支）— 2026-10-02

> **范围**：PR #46 `enh/remove-inline-default-css` → `master`（issue IKJHPH 修复：
> 12 个 widget 类内联 `DEFAULT_CSS` 外置为 `yate/resources/<class>.tcss`、
> `paths.load_tcss` 进程级 `lru_cache`、`tests/test_app_css.py` 资源化守卫 4 条；
> 评审时点 PR 可见 4 笔提交 `380fccc` / `922e6f4` / `32d2f99` / `6c30674`）。
> 本次登记 **Gitee AI 队友审查**（[原始评论](https://gitee.com/jermaine/yate/pulls/46#note_51431686_conversation_191330840)，2026-10-02 22:31）：
> 结论 **⚠️ 无阻断项，可优化后合并**——功能性与逻辑 / 安全性 / 性能均 ✅ 通过，
> 可维护性 ⚠️ 待优化，风险等级 **low**（0 阻断 / 1 改进）。
> 审查总评：CSS 内容逐字节等价迁移，Textual 类作用域语义不变；`lru_cache`
> 每进程每样式表仅读盘一次；Python 文件零内联 CSS；无注入风险。

### AI 发现逐条登记与处置

- [x] **改进项：AST 守卫未覆盖带类型注解的赋值形式（可维护性）** —
  [`tests/test_app_css.py`](../../tests/test_app_css.py)
  `_default_css_violations` 仅检查 `ast.Assign`；若出现
  `DEFAULT_CSS: str = "inline"`（`ast.AnnAssign`）将被静默放过。审查者建议
  补充 `ast.AnnAssign` 分支以完善守卫覆盖面（原评论附修正示例代码）。

  *核对结论（2026-10-02）：与分支内部评审（code-review-expert）WARNING-1
  及 SUGGESTION-3 属同一发现，评审时已实证三连演练（Assign-inline 拦截 /
  AnnAssign+load_tcss 放行 / AnnAssign-inline 放行）。该守卫盲区**已在分支上
  修复**：commit `5fca69b`（`test(css): also guard annotated default css
  assignments`）将扫描放宽为全模块 `Assign` + `AnnAssign`（带值且目标名为
  `DEFAULT_CSS`），补强后两种内联形态负向演练均拦截（exit 1），还原后
  `tests/test_app_css.py` 6 passed。评审时点该提交尚未推送，故 PR 可见提交
  中不含修复；分支推送后该改进项随 PR 自然闭环。*

  *⏸ 按用户决策登记不修（2026-10-02）——本次登记不产生新的修复动作：
  无需对审查建议另行实施，事实状态以上方核对结论为准。*
