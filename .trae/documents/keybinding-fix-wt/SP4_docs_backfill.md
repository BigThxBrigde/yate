# SP4 — 文档回填与 Issue 关账

> 前置：SP1–SP3 已提交
> 预估：30min　|　独占文件：`.trae/issues/review.md`、`.trae/documents/code-review-fix-plans/P2_nice_to_have_plan.md`、`.trae/documents/keybinding-fix-wt/*.md`

## 目标

四处文档与代码实际状态对齐：review.md、P2 计划 N8、本子计划集、Gitee issue 回复草稿。

## 实施步骤

### 步骤 4.1　`.trae/issues/review.md`

历史问题区新增条目「Windows Terminal 键位失效（IKH1RA）」：

- 现象：WT 下 `ctrl+p`/`ctrl+1`/`ctrl+/` 失效；
- 根因：`\x1f` 命名漂移（`ctrl+underscore` 未登记）+ conhost/Textual 双丢修饰（`ctrl+1` 无 legacy 编码）；
- 处置：`ctrl+p` 随 `9fa5ac8` 重构修复；`ctrl+/` 由 SP1 修复；`ctrl+1` 文档化为 CSI-u-only（SP3），
  根治走 `win_keybinding_plan.md` 方案 B；
- 附实测数字（pytest/pyright 通过数，取 SP5 实际值）。

### 步骤 4.2　P2 计划 N8 关账

`.trae/documents/code-review-fix-plans/P2_nice_to_have_plan.md` 中 N8：
状态 ⏸ → ✅；撤销备注「待 KeyBinding 在 WT 重构后彻底修复」；
链接本子计划集与 `wt_keybinding_fix_plan.md`；注明 `ctrl+1` 部分转为方案 B 范畴。

### 步骤 4.3　子计划集状态回写

- `README.md` 状态：待实施 → 已实施（附各 SP commit sha）；
- 各 SP 文件勾选验收标准复选框（用实际结果，不预勾）。

### 步骤 4.4　Gitee issue 回复草稿

写入 `keybinding-fix-wt/issue_reply_IKH1RA.md`（新建，中文）：
现象确认 → 三键分别的根因（一段话，引用 Textual 命名事实）→ 修复版本/commit → `ctrl+1` 的替代路径与后续根治计划 → 致谢。
（草稿仅供人工粘贴到 Gitee，不自动发布。）

## 测试

纯文档；无。交叉检查四个文档对「三键状态」的口径完全一致（✅已修 / ✅已修 / 📄文档化+根治排期）。

## 验收标准

- [ ] 四处口径一致；N8 无悬挂引用；
- [ ] 所有 commit sha 真实存在（`git log --oneline` 核对）。

## 回滚

单 commit revert。
