---
alwaysApply: true
---

# misc-rules（杂项规则）

收录不成体系但必须遵守的环境与工具约束：单条规则不足以独立成文件时登记在此，
按章节编号追加，不另开新规则文件。

## 一、多行文本：按 Shell 环境选择 here-string 或 heredoc

- **Windows（本项目当前环境）**：Shell 解释器是 **PowerShell**（非 bash/cmd）。
  PowerShell 不支持 `<<'EOF'` / `<<EOF` heredoc 语法，直接使用会报：

  ```text
  ParserError: Missing file specification after redirection operator.
  ```

  多行字符串（典型场景：`git commit -m` 的多行提交信息）必须改用 here-string：

  - `@'...'@`：单引号形式，内容原样保留，不插值（首选，提交信息用这个）；
  - `@"..."@`：双引号形式，支持 `$var` 插值。

  ```powershell
  # 错误：在 PowerShell 里写 bash heredoc，直接 ParserError
  git commit -m "$(cat <<'EOF'
  commit message here
  EOF
  )"

  # 正确：PowerShell here-string
  git commit -m @'
  commit message here
  '@
  ```

  注意：here-string 的结束标记 `@'` / `"@` 必须**顶行书写**（行首不能有空格），
  否则不被识别为结束标记。

- **Linux/macOS（bash/zsh 等 POSIX shell）**：heredoc 是正常语法，可照常使用
  `<<'EOF' ... EOF`。

## 二、Python 代码的测试验证直接用 Python 脚本

对 Python 代码做测试 / 验证时，直接写 Python 脚本执行，不要把验证逻辑硬塞进
PowerShell 命令行拼接（§一 的 PowerShell 语法限制因此大多可以绕开）：

- 解释器统一用项目虚拟环境的 `.venv\Scripts\python.exe`；
- 正式回归跑 **`pytest tests/ -q -n auto`**（并行口径，`pytest-xdist` 已随 `[dev]` 安装）；
  需要单进程排查时序问题时用 `-n 1`，两者结果必须一致；
- 一次性探针/冒烟用临时脚本（验证完删除）或 `python -c "..."` 短表达式。

## 三、纯文档变更的验证豁免

`task-orchestration.md` §二 的收尾门禁（pyright + pytest + 架构测试 + 覆盖率）
默认适用于所有变更，但对**纯文档修改**给予豁免：

- **可豁免**：本次变更只涉及 Markdown / 纯文本文档（`.trae/` 下的规则、计划、
  评审记录，`README*.md`、`CHANGELOG*.md`、`yate/docs/` 双语手册等），且不改变
  任何可执行行为。此时**无需运行测试与门禁**，在收尾汇报中说明"纯文档变更，
  按 §三 豁免测试"即可；
- **不可豁免**：变更涉及代码、配置、脚本、依赖、数据或任何非文档内容（包括：
  文档里内嵌的可执行代码块变更、构建/打包配置、`.py`/`.toml`/`.json`/`.bat` 等
  文件），一律按常规流程执行相应层级的测试与验证，豁免不适用；
- **混合变更**：同一批改动中既有文档又有代码/配置/脚本时，以**最高风险**判定，
  视为不可豁免，跑全量门禁；
- 豁免只免除"运行测试"这一步，**不免除**其余硬性要求：规则加载（总纲 §一）、
  文档命名与相对路径引用（`doc-conventions.md`）、提交信息格式
  （`git-commit-message.md`）、以及如实汇报变更内容。

## 四、代码注释与代码内注解文档一律英文

仓库内一切代码文件的注释与代码内注解文档必须使用英文，包括：

- **注释**：`.py` 的 `#`、`.lua` 的 `--`，以及一切脚本/配置文件内的注释；
- **代码内注解文档**：docstring、模块头部说明块（如 Lua 的 `--[[ ... ]]`
  头注释）、随代码分发的示例模板（`yate/extensions/*.py.example`、
  `lua.example` 等）内的注释与示例字符串；
- 依据：代码（含随包模板）面向国际化用户分发，须与代码库既有的全英文
  注释面保持一致。

**不受本条约束**：面向用户的文档（`yate/docs/*.en.md` / `*.zh.md`、
`yate/resources/manual.*.md` 等）仍按 `doc-conventions.md` 的双语同步规则
各自使用中英文。

## 五、Trae memory 定期维护（每半月一轮）

Trae 为项目维护跨会话 memory，位于 `~/.trae-cn/memory/projects/<project-slug>/`，
含 `project_memory.md`（项目规则沉淀）与按日分目录的
`session_memory_*.jsonl` / `topics.md`（对话级记录）。该目录只增不减，会持续
膨胀并拖慢每次会话的检索，须定期整理。

- **周期**：每月 1 日与 16 日前后各执行一轮；用户说"整理 memory"、"清理
  session"、"精简 memory"等时立即执行，不受周期限制。
- **`project_memory.md` 整理**（整体重写，不是往末尾追加）：
  - 删除：已完成任务的验收流水账（"手册必须记载 X"类条目）、彼此重复的碎条目、
    已失效的临时状态（如"分支领先 N 提交"、过期计划的波次安排、已解除的禁用项）；
  - 合并：同一主题的多条碎目合并为单条结构化描述，按"硬约束 / 架构规则 /
    打包 CI / 流程纪律 / 编码约定 / Lessons Learned"分节；
  - **保留红线**：删除任何条目前自问"该信息能否从仓库（代码、`yate/docs/`
    手册、CHANGELOG、`.trae/` 规则）恢复"——能恢复或已失效才可删；仍有效且
    仓库不可查的一律保留，**Lessons Learned 全量保留，一条不删**；
  - 汇报：完成后列出删除/合并摘要（删了哪几类、为什么），供用户抽查。
- **session 清理**：删除早于最近 30 天的日期目录（整目录连同内部文件删除）；
  删除前抽查这些日期的 `topics.md` 是否含未沉淀的结论性信息，有则先并入
  `project_memory.md` 再删。
- **操作方式**：批量删文件用 DeleteFile 工具，空目录用 PowerShell
  `Remove-Item -Recurse -Force`；执行前后各统计一次文件数与总体积，用表格
  向用户汇报前后对比。
