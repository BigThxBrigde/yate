# doc-conventions（文档命名与引用约定）

本规则固化仓库内各类文档的命名与路径引用约定。新建文档必须遵守；存量文档已于
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
- 方案文档自身也按本规范命名（如 `doc-plans-naming-convention-plan.md`）；
- **单计划体积上限**：单个计划文档不得超过 **1 MB**；超过 1 MB 视为"大计划"，
  必须按本节子计划规范拆分为 `<task>-plans/` 目录（总纲 `overview.md` +
  子计划 `*-plan-<a|b|c...>.md`），不得继续在单一文件内累积。

## 二、审查与评审文档

### 2.1 评审记录（`.trae/reviews/`）

| 对象 | 命名 | 示例 |
|---|---|---|
| 单次评审记录 | `YYYY-MM-DD-<topic>.md`（日期前缀 + 连字符分词主题） | `2026-09-27-ui-refine.md` |
| 目录索引 | `README.md`（reviews 目录保留 README 惯例） | `.trae/reviews/README.md` |
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

## 五、文档内路径引用（相对路径强制）

- `.trae/` 下所有 Markdown（规则、计划、评审记录、agents）正文中引用**仓库内文件**
  时，一律使用**相对路径**，以引用所在文档自身位置为基准：规则文档指向计划文档写
  `../documents/<task>-plan.md`，同目录引用直接写文件名；
- 禁止绝对路径：盘符路径（`d:\...`）、用户目录（`C:\Users\...`）、以 `/` 开头的
  仓库根绝对路径均不得出现；行内代码与 Markdown 链接两种形式同样适用；
- **真实路径脱敏（环境信息）**：文档不得暴露本机真实路径，主要针对加入 PATH 的
  命令与全局安装工具的落盘位置（如 `D:\npm\npm-global\xxx.ps1`）——环境事实用
  可移植写法表达：命令只写命令名（已加入 PATH 的工具直接写 `xxx`），来源概括为
  包名 + 版本或"全局安装"，不写具体目录；本条与上一条互补：上一条约束仓库内
  文件的引用形态，本条约束环境信息脱敏，对命令示例代码块同样适用；
- 外部 URL（`https://...`）不受本节约束；代码块内的可执行命令相对基准是
  仓库根（如 `python -m pytest tests/ -q`），但不得包含本机真实路径（见上条）；
- 新增引用按本节执行；存量文档随下次修改逐步迁移，不做专项清扫。

## 六、通用反例（禁止）

- 禁止模糊/无意义命名：`app-parts`、`app-helpers`、`misc-docs`、`temp`、`old`；
- 禁止与现有规则冲突的后缀（`*-ops`、`*-feature` 已在代码层废止，文档同理）；
- 禁止中英混合文件名；文件名一律 ASCII；
- 禁止日期与主题混排格式（`review-20260926.md` 型已废止，见 §二）；
- 禁止文档内引用仓库文件使用绝对路径（盘符 / 用户目录 / 仓库根，见 §五）；
- 禁止文档内暴露本机真实路径：加入 PATH 的命令、全局安装 CLI 位置等环境信息
  须脱敏为可移植写法（见 §五）。

## 七、与其它规则的关系

- 计划文档的**内容**格式规范见 `plan-before-execute.md`；
- 闭环流程中方案落盘路径见 `task-orchestration.md` §二；
- 分支 / worktree 命名（`<fix|feat|enh|ref>/<task>`）见 `task-orchestration.md` §二.1；
- 提交信息规范见 `git-commit-message.md`。
