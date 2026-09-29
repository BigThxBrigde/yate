# doc-naming（文档命名规范）

本规则固化仓库内各类文档的命名约定。新建文档必须遵守；存量文档已于
2026-09-29 统一过一轮（计划文档由下划线分词统一迁移为连字符分词，见
`.trae/documents/doc-plans-naming-convention-plan.md` 执行记录）。

## 一、计划与子计划（`.trae/documents/`）

| 对象 | 命名 | 示例 |
|---|---|---|
| 主计划 | `<task>-plan.md` | `wt-keybinding-fix-plan.md` |
| 子计划目录 | `<task>-plans/` | `fancy-sym-plans/` |
| 子计划文件 | `<task>-<subtask>-plan-<a\|b\|c...>.md` | `app-layering-refactoring-leaf-models-plan-a.md`、`python-312-upgrade-plan-a.md`（subtask 省略） |
| 子计划目录总纲 | `overview.md`（**不用** README.md） | `theme-layer-refactor-plans/overview.md` |

硬性要求：

- `task` / `subtask` 用小写连字符分词，与目录 task 保持一致；
- 波次标记（SP0-SP4、P0-P2、PLAN_B_v2 等）一律转字母序 `a,b,c...`，
  原语义由 subtask 主题或文档内文保留；
- 子计划目录名统一使用连字符 `<task>-plans/` 形态：存量中既有连字符
  `*-plans/` 与下划线 `*_plans/` 两种，下划线形态须迁移为连字符，不得
  新增下划线风格目录；
- 方案文档自身也按本规范命名（如 `doc-plans-naming-convention-plan.md`）。

## 二、审查与评审文档

### 2.1 评审记录（`.trae/review/`）

| 对象 | 命名 | 示例 |
|---|---|---|
| 单次评审记录 | `YYYY-MM-DD-<topic>.md`（日期前缀 + 连字符分词主题） | `2026-09-27-ui-refine.md` |
| 目录索引 | `README.md`（review 目录保留 README 惯例） | `.trae/review/README.md` |
| 历史遗留汇总 | `legacy-issues.md`（已定案保留命名） | — |

同日多次评审以主题区分，不使用 `-2` / `-v2` 序号后缀。
评审记录是**只读事实文档**：只记录发现与核对结论，不放修复排期。

### 2.2 评审修复方案（`.trae/documents/`）

评审发现需要修复时，修复方案按 §一 主计划规范落在 `.trae/documents/` 根，
review 语义并入 `task`：

- 合规格式：`<task>-plan.md`，task 中含 `review` 词根
  （存量合规例：`code-review-fixes-plan.md`、`fancy-sym-review-fixes-plan.md`、
  `vim-keymap-review-plan.md`）；
- **禁止下划线分词**（存量反例 `vim_keymap_review_plan.md` 已随
  `review-vim-keymap` 分支改为 `vim-keymap-review-plan.md`）；
- 评审记录与修复方案必须互相链接（记录 → 方案；方案 → 来源记录），
  但文件各自独立，不合并成一份。

## 三、双语手册（`yate/docs/`）

- 语言后缀显式成对：`<topic>.en.md` + `<topic>.zh.md`
  （如 `yaterc.en.md` / `yaterc.zh.md`）；
- 两份文件必须同时新增、同时更新（双语同步是硬约束，见项目记忆）；
- 文件名主题词用连字符或下划线与既有文件保持一致。

## 四、根级文档（仓库根）

- GitHub 惯例保留英文名默认：`README.md`（英文为主）+ `README.zh.md`；
- `CHANGELOG.md` + `CHANGELOG.zh.md` 同理；
- 根级文件名不得随意改动（CI、pack 脚本、徽章链接均按名引用）。

## 五、通用反例（禁止）

- 禁止模糊/无意义命名：`app-parts`、`app-helpers`、`misc-docs`、`temp`、`old`；
- 禁止与现有规则冲突的后缀（`*-ops`、`*-feature` 已在代码层废止，文档同理）；
- 禁止中英混合文件名；文件名一律 ASCII；
- 禁止日期与主题混排格式（`review-20260926.md` 型已废止，见 §二）。

## 六、与其它规则的关系

- 计划文档的**内容**格式规范见 `plan-before-execute.md`；
- 闭环流程中方案落盘路径见 `task-orchestration.md` §二；
- 分支 / worktree 命名（`<fix|feat|enh|ref>/<task>`）见 `task-orchestration.md` §二.1；
- 提交信息规范见 `git-commit-message.md`。
